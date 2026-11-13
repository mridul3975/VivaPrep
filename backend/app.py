import os
import secrets
import time
import uuid
import wave
from io import BytesIO
from pathlib import Path
from threading import Lock
from datetime import timedelta
from contextlib import nullcontext
from backend import example
from backend.languages import language_choice

from flask import Flask, g, jsonify, request, send_from_directory, session
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

from backend.interview.question_generator import QuestionGenerationError, generate_question_set
from backend.interview.evaluator import EvaluationError
from backend.interview.grading import grade_answer
from backend.evidence.retrieve import retrieve
from backend.evidence.uploads import uploads, next_source_evidence, owned_source
from backend.evidence.documents import DocumentError
from backend.speech.transcriber import TranscriptionError, transcribe_wav
from backend.speech.review import store_review, resolve_review, debug_context, store_debug_review
from backend.auth import auth, protect_study_routes
from backend.database import database_enabled, get_database, DatabaseUnavailable, StudyConflict, public_question
from backend.account import account, allowance, UsageLimit, quota_error
from backend.library import library
from backend.debugging import debugging
from backend.viva import viva
from backend.evaluation import evaluation

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
API_VERSION = "study-v2"

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

app = Flask(__name__, static_folder=None)
app.secret_key = os.getenv("SESSION_SECRET") or secrets.token_hex(32)
try:
    trusted_hops = max(0, min(10, int(os.getenv('TRUSTED_PROXY_HOPS', '0'))))
except ValueError:
    trusted_hops = 0
if trusted_hops:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=trusted_hops, x_proto=0, x_host=0, x_port=0, x_prefix=0)
app.config.update(SESSION_COOKIE_NAME="repoviva_session", SESSION_COOKIE_HTTPONLY=True,
                  SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE") == "1",
                  PERMANENT_SESSION_LIFETIME=timedelta(hours=24), SESSION_REFRESH_EACH_REQUEST=False)
app.register_blueprint(auth)
app.before_request(protect_study_routes)
app.register_blueprint(uploads)
app.register_blueprint(account)
app.register_blueprint(library)
app.register_blueprint(debugging)
app.register_blueprint(viva)
app.register_blueprint(evaluation)
app.register_error_handler(UsageLimit, quota_error)
turns = {}
turns_lock = Lock()
TURN_TTL_SECONDS = 3600
MAX_TURNS = 100
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 30


@app.get("/")
def frontend_index():
    if not (FRONTEND_DIST / "index.html").is_file():
        return jsonify({"error": "Frontend build missing. Run npm run build in frontend/."}), 503
    return send_from_directory(FRONTEND_DIST, "index.html", max_age=0)


@app.get("/assets/<path:filename>")
def frontend_asset(filename):
    response = send_from_directory(FRONTEND_DIST / "assets", filename, max_age=31536000)
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return response


@app.get("/favicon.svg")
def frontend_favicon():
    return send_from_directory(FRONTEND_DIST, "favicon.svg")


@app.get('/fonts/<path:filename>')
def frontend_fonts(filename):
    return send_from_directory(FRONTEND_DIST / 'fonts', filename, max_age=86400)


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found."}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    response = jsonify({"error": "Method not allowed."})
    response.status_code = 405
    if error.valid_methods:
        response.headers["Allow"] = ", ".join(error.valid_methods)
    return response


@app.get("/health")
def health():
    if database_enabled():
        get_database().check()
    return jsonify({"status": "ok", "api_version": API_VERSION,
                    "storage_mode": "postgresql" if database_enabled() else "memory"})


@app.errorhandler(DatabaseUnavailable)
def database_unavailable(error):
    app.logger.warning("PostgreSQL request unavailable (%s)", type(error.__cause__).__name__)
    return jsonify({"error": "Saved data is temporarily unavailable. Please retry.", "error_code": "database_unavailable"}), 503


@app.errorhandler(StudyConflict)
def study_conflict(error):
    return jsonify({"error": str(error)}), error.status


@app.after_request
def api_headers(response):
    if request.path in ("/health", "/retrieve", "/questions", "/answers", "/transcriptions", "/profile") or request.path.startswith(("/sources", "/auth/", "/history", "/debug/")):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-RepoViva-API"] = API_VERSION
    return response


@app.post("/retrieve")
def retrieve_snippets():
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not isinstance(data.get("question"), str):
        return jsonify({"error": "JSON must contain a string question"}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400

    source_id = data.get("source_id", session.get("active_source_id"))
    if "source_id" in data and (not isinstance(source_id, str) or not source_id.strip()):
        return jsonify({"error": "source_id must be a non-empty string."}), 400
    if not source_id:
        return jsonify({"error": "Upload your study material first."}), 400
    document = owned_source(source_id)
    if document is None:
        return jsonify({"error": "Upload not found or expired. Please upload the file again."}), 404
    records = document["snippets"]
    results = retrieve(question, records)

    return jsonify({
        "question": question,
        "source_id": source_id,
        "results": results,
    })


@app.post("/questions")
def generate_questions():
    data = request.get_json(silent=True)
    if data is None and (request.is_json or request.content_length):
        return jsonify({"error": "Expected a JSON object."}), 400
    if data is not None and not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object."}), 400
    data = data or {}
    source_id = data.get("source_id", session.get("active_source_id"))
    if "source_id" in data and (not isinstance(source_id, str) or not source_id.strip()):
        return jsonify({"error": "source_id must be a non-empty string."}), 400
    if not source_id:
        return jsonify({"error": "Upload your study material before generating questions."}), 400
    language = language_choice(data.get("language", "en"))
    count = data.get("count", 3)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 3:
        return jsonify({"error": "Question count must be between 1 and 3."}), 400
    document = owned_source(source_id)
    if document is None:
        return jsonify({"error": "Upload not found or expired. Please upload the file again."}), 404
    if example.is_example(document) and database_enabled():
        previous = get_database().current_practice(g.user['id'], source_id)
        if previous:
            with get_database().connection() as conn:
                prepared = conn.execute("SELECT bool_and(payload->'question_package'->>'prepared_example'=%s) AS prepared FROM repoviva.turns WHERE practice_id=%s AND owner=%s", (example.QUESTION_VERSION,previous['practice_id'],g.user['id'])).fetchone()['prepared']
            if prepared and all(item.get('language', 'en') == language for item in previous['questions']):
                return jsonify({'api_version': API_VERSION, 'source_id': source_id, 'source_revision': document['revision'], 'practice_id': previous['practice_id'], 'questions': previous['questions'][:count]})
    elif example.is_example(document):
        with turns_lock:
            existing = {key: turn for key, turn in turns.items() if turn['owner'] == g.user['id'] and turn['source_id'] == source_id and turn['question_package'].get('prepared_example') == example.QUESTION_VERSION and turn['question_package'].get('language', 'en') == language and time.monotonic() - turn['created'] < TURN_TTL_SECONDS}
        if len(existing) >= count:
            return jsonify({'api_version': API_VERSION, 'source_id': source_id, 'source_revision': document['revision'], 'practice_id': None, 'questions': [public_question(key, turn) for key, turn in list(existing.items())[:count]]})
    try:
        with nullcontext() if example.is_example(document) else allowance("questions"):
            selected = next_source_evidence(source_id)
            if selected is None:
                raise StudyConflict("Upload not found or expired. Please upload the file again.", 404)
            snippets, revision = selected
            packages = example.question_set(snippets, count, language) if example.is_example(document) else (generate_question_set(snippets, count=count, language=language) if language != 'en' else generate_question_set(snippets, count=count))
            now, records = time.monotonic(), {}
            for package in packages:
                package['language'] = language
                turn_id = uuid.uuid4().hex
                primary_id = package["rubric"][0]["snippet_id"]
                primary = next(item for item in snippets if str(item["id"]) == primary_id)
                records[turn_id] = {"question": package["question"], "question_package": package,
                                    "snippet": primary, "snippets": snippets, "created": now, "busy": False,
                                    "source_id": source_id, "revision": revision, "owner": g.user["id"]}
            practice_id = None
            if database_enabled():
                practice_id = get_database().save_questions(g.user["id"], source_id, records)
            else:
                with turns_lock:
                    expired = [key for key, turn in turns.items() if now - turn["created"] >= TURN_TTL_SECONDS and not turn["busy"]]
                    for key in expired:
                        del turns[key]
                    if len(turns) + len(packages) > MAX_TURNS:
                        raise StudyConflict("Too many active turns. Please try again later.", 503)
                    turns.update(records)
    except DocumentError as error:
        return jsonify({"error": str(error)}), error.status
    except QuestionGenerationError as e:
        app.logger.warning("Question generation failed: %s", e.__cause__ or e)
        return jsonify({"error": str(e), "error_code": e.code}), e.http_status

    public_questions = [public_question(turn_id, turn) for turn_id, turn in records.items()]
    return jsonify({"api_version": API_VERSION, "source_id": source_id, "source_revision": revision,
                    "practice_id": practice_id, "questions": public_questions}), 200


@app.post("/answers")
def submit_answer():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object."}), 400
    turn_id, answer = data.get("turn_id"), data.get("answer")
    if (
        not isinstance(turn_id, str)
        or not turn_id.strip()
        or not isinstance(answer, str)
        or not answer.strip()
    ):
        return jsonify({"error": "A turn ID and a non-empty answer are required."}), 400
    answer = answer.strip()
    if len(answer) > 4000:
        return jsonify({"error": "Answer must be at most 4,000 characters."}), 400

    persistent = database_enabled()
    attempt_saved = False
    if persistent:
        turn, lease = get_database().claim_turn(g.user["id"], turn_id)
    else:
        with turns_lock:
            turn = turns.get(turn_id)
            if turn is not None and turn.get("owner") != g.user["id"]:
                return jsonify({"error": "Turn not found or expired. Start a new question."}), 404
            if turn is None or time.monotonic() - turn["created"] >= TURN_TTL_SECONDS:
                if turn is not None and not turn["busy"]:
                    del turns[turn_id]
                return jsonify({"error": "Turn not found or expired. Start a new question."}), 404
            if turn["busy"]:
                return jsonify({"error": "This answer is already being evaluated."}), 409
            turn["busy"] = True

    try:
        speech_review = resolve_review(g.user['id'],turn_id,data.get('speech_review'),require_confirmed=True)
        prepared = turn['question_package'].get('prepared_example') == 'prime-v1'
        with nullcontext() if prepared else allowance("answers"):
            result = example.grade(turn['question_package'], answer, turn['snippets']) if prepared else grade_answer(turn["question_package"], answer, turn["snippets"])
            payload = {"turn_id": turn_id, "source_id": turn["source_id"], "question": turn["question"], 'language': turn['question_package'].get('language', 'en'),
                       "evidence": turn["snippet"], "evidence_snippets": turn["snippets"], **result}
            if speech_review:
                payload['speech_review'] = {**speech_review,'final_answer':answer,'corrections_made':answer != speech_review['original_transcript']}
            if persistent:
                get_database().save_attempt(g.user["id"], turn_id, lease, answer, payload)
                attempt_saved = True
    except EvaluationError as error:
        app.logger.warning("Answer evaluation failed: %s", error.__cause__ or error)
        if error.code.startswith("provider_"):
            return jsonify({"error": str(error), "error_code": error.code}), error.http_status
        return jsonify({"error": "Unable to evaluate the answer. Please try again."}), 502
    finally:
        if persistent and not attempt_saved:
            get_database().release_turn(g.user["id"], turn_id, lease)
        elif not persistent:
            with turns_lock:
                turn["busy"] = False
    return jsonify(payload), 200


@app.get("/history")
def practice_history():
    return jsonify({"attempts": get_database().history(g.user["id"]) if database_enabled() else []})


@app.post("/transcriptions")
def transcribe_upload():
    # Allow multipart headers in addition to the bounded audio payload.
    request.max_content_length = MAX_AUDIO_BYTES + 64 * 1024
    if request.content_length and request.content_length > request.max_content_length:
        return jsonify({"error": "Audio must be at most 10 MiB."}), 413
    try:
        upload = request.files.get("audio_file")
        if upload is None or not upload.filename:
            return jsonify({"error": "Upload a WAV file using the audio_file field."}), 400
        filename = secure_filename(upload.filename)
        if Path(filename).suffix.lower() != ".wav":
            return jsonify({"error": "Only WAV recordings are supported. Upload a WAV file."}), 415
        try:
            audio = upload.stream.read(MAX_AUDIO_BYTES + 1)
        finally:
            upload.close()
    except RequestEntityTooLarge:
        return jsonify({"error": "Audio must be at most 10 MiB."}), 413

    if not audio:
        return jsonify({"error": "The audio file is empty."}), 400
    if len(audio) > MAX_AUDIO_BYTES:
        return jsonify({"error": "Audio must be at most 10 MiB."}), 413

    try:
        with wave.open(BytesIO(audio), "rb") as recording:
            frames = recording.getnframes()
            duration = frames / recording.getframerate()
            if frames == 0:
                return jsonify({"error": "The recording contains no audio frames."}), 400
            if duration > MAX_AUDIO_SECONDS:
                return jsonify({"error": "Recordings must be at most 30 seconds."}), 400
            expected_bytes = frames * recording.getnchannels() * recording.getsampwidth()
            if len(recording.readframes(frames)) != expected_bytes:
                return jsonify({"error": "The WAV recording is incomplete."}), 400
    except (wave.Error, EOFError):
        return jsonify({"error": "Upload a valid uncompressed WAV recording."}), 415

    try:
        with allowance("transcriptions"):
            turn_id = request.form.get('turn_id')
            debug_run_id = request.form.get('debug_run_id')
            debug_field = request.form.get('debug_field')
            if (turn_id and debug_run_id) or (debug_field and not debug_run_id):
                raise StudyConflict('Choose one question or debugging exercise for the recording.', 400)
            evidence = None
            if debug_run_id:
                evidence = debug_context(g.user['id'], debug_run_id, debug_field)
            if turn_id:
                if database_enabled():
                    with get_database().connection() as conn:
                        row = conn.execute('SELECT payload FROM repoviva.turns WHERE id=%s AND owner=%s', (turn_id,g.user['id'])).fetchone()
                    evidence = row['payload']['snippets'] if row else None
                else:
                    with turns_lock:
                        row = turns.get(turn_id)
                        evidence = row['snippets'] if row and row['owner'] == g.user['id'] else None
                if evidence is None:
                    raise StudyConflict('Question not found. Return to your current practice.',404)
            transcript = transcribe_wav(audio, filename)
            if (turn_id or debug_run_id) and len(transcript) > 4000:
                raise TranscriptionError('Transcript exceeds the answer limit')
            review = store_review(g.user['id'],turn_id,transcript,evidence) if turn_id else None
            if debug_run_id:
                review = store_debug_review(g.user['id'], debug_run_id, debug_field, transcript, evidence)
    except TranscriptionError:
        app.logger.warning("Audio transcription failed")
        return jsonify({"error": "Unable to transcribe this recording. Please retry or type your answer."}), 502

    return jsonify({"transcript": transcript, **({'speech_review':review} if review else {})}), 200
    


if __name__ == "__main__":
    # Local development reloads code without exposing Flask's interactive debugger.
    # Gunicorn imports app directly, so its production reload=False still applies.
    app.run(debug=False, use_reloader=True)
