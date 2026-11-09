import os
import time
import uuid
import wave
from io import BytesIO
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from backend.interview.question_generator import QuestionGenerationError, generate_question
from backend.interview.evaluator import EvaluationError, evaluate_answer
from backend.evidence.read import read
from backend.evidence.retrieve import retrieve
from backend.speech.transcriber import TranscriptionError, transcribe_wav

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = PROJECT_ROOT / "samples" / "read.py"
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

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
turns = {}
turns_lock = Lock()
TURN_TTL_SECONDS = 3600
MAX_TURNS = 100
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_AUDIO_SECONDS = 60


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
    return jsonify({"status": "ok"})


@app.post("/retrieve")
def retrieve_snippets():
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not isinstance(data.get("question"), str):
        return jsonify({"error": "JSON must contain a string question"}), 400

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400

    records = read(str(SAMPLE_PATH))
    results = retrieve(question, records)

    return jsonify({
        "question": question,
        "results": results,
    })


@app.post("/questions")
def generate_questions():
    records = read(str(SAMPLE_PATH))
    
    ## Validate the records

    if not records:
        return jsonify({"error": "No records found"}), 400

    # Select the first snippet for question generation
    snippet = records[0]

    try:
        question = generate_question(snippet)
    except QuestionGenerationError as e:
        app.logger.error(f"Question generation failed: {e}")
        return jsonify({"error": "Unable to generate a question at this time. Please try again later."}), 502

    turn_id = uuid.uuid4().hex
    with turns_lock:
        now = time.monotonic()
        expired = [key for key, turn in turns.items() if now - turn["created"] >= TURN_TTL_SECONDS and not turn["busy"]]
        for key in expired:
            del turns[key]
        if len(turns) >= MAX_TURNS:
            return jsonify({"error": "Too many active turns. Please try again later."}), 503
        turns[turn_id] = {"question": question, "snippet": snippet, "created": now, "busy": False}

    return jsonify({
        "turn_id": turn_id,
        "question": question,
        "evidence": {
            "snippet": snippet,
            "path": snippet["path"],
            "start_line": snippet["start_line"],
            "end_line": snippet["end_line"],
            "content": snippet["content"]
        }
    }), 200


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

    with turns_lock:
        turn = turns.get(turn_id)
        if turn is None or time.monotonic() - turn["created"] >= TURN_TTL_SECONDS:
            if turn is not None and not turn["busy"]:
                del turns[turn_id]
            return jsonify({"error": "Turn not found or expired. Start a new question."}), 404
        if turn["busy"]:
            return jsonify({"error": "This answer is already being evaluated."}), 409
        turn["busy"] = True

    try:
        claims = evaluate_answer(turn["question"], answer, turn["snippet"])
    except EvaluationError:
        app.logger.warning("Answer evaluation failed")
        return jsonify({"error": "Unable to evaluate the answer. Please try again."}), 502
    finally:
        with turns_lock:
            turn["busy"] = False
    return jsonify({
        "turn_id": turn_id,
        "question": turn["question"],
        "claims": claims,
        "evidence": turn["snippet"],
    }), 200


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
                return jsonify({"error": "Recordings must be at most 60 seconds."}), 400
            expected_bytes = frames * recording.getnchannels() * recording.getsampwidth()
            if len(recording.readframes(frames)) != expected_bytes:
                return jsonify({"error": "The WAV recording is incomplete."}), 400
    except (wave.Error, EOFError):
        return jsonify({"error": "Upload a valid uncompressed WAV recording."}), 415

    try:
        transcript = transcribe_wav(audio, filename)
    except TranscriptionError:
        app.logger.warning("Audio transcription failed")
        return jsonify({"error": "Unable to transcribe this recording. Please retry or type your answer."}), 502

    return jsonify({"transcript": transcript}), 200
    


if __name__ == "__main__":
    app.run(debug=False)
