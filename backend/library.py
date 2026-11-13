"""History reads, owned restoration and content-addressed upload reuse."""
import time
import uuid
from flask import Blueprint, g, jsonify, request, session
from psycopg.types.json import Jsonb
from backend.database import database_enabled, get_database, public_question, StudyConflict

library = Blueprint("library", __name__)
PAGE_SIZE = 20


def practice_snapshot(conn, owner, practice_id):
    practice = conn.execute("SELECT last_turn_id FROM repoviva.practice_sets WHERE id=%s AND owner=%s", (practice_id, owner)).fetchone()
    if not practice:
        raise StudyConflict("Practice not found.", 404)
    turns = conn.execute("SELECT id,payload FROM repoviva.turns WHERE practice_id=%s AND owner=%s ORDER BY position", (practice_id, owner)).fetchall()
    children = {row['payload']['parent_turn_id']: row for row in turns if row['payload'].get('parent_turn_id')}
    turns = [item for row in turns if not row['payload'].get('parent_turn_id') for item in ([row,children[row['id']]] if row['id'] in children else [row])]
    attempts = conn.execute("SELECT DISTINCT ON(a.turn_id) a.turn_id,a.answer,a.feedback FROM repoviva.attempts a JOIN repoviva.turns t ON t.id=a.turn_id WHERE t.practice_id=%s AND a.owner=%s ORDER BY a.turn_id,a.created_at DESC,a.id DESC", (practice_id, owner)).fetchall()
    drafts = conn.execute("SELECT d.turn_id,d.answer,d.speech_review FROM repoviva.drafts d JOIN repoviva.turns t ON t.id=d.turn_id WHERE t.practice_id=%s AND d.owner=%s", (practice_id, owner)).fetchall()
    return {"practice_id": practice_id, "questions": [public_question(row["id"], row["payload"]) for row in turns],
            "results": {row["turn_id"]: row["feedback"] for row in attempts}, "answers": {row["turn_id"]: row["answer"] for row in attempts},
            "drafts": {row["turn_id"]: row["answer"] for row in drafts}, 'speech_reviews': {row['turn_id']:row['speech_review'] for row in drafts if row['speech_review']}, "resume_turn_id": practice["last_turn_id"]}


def restored_document(owner, source_id):
    store = get_database()
    document = store.source(owner, source_id)
    if not document:
        raise StudyConflict("Material not found.", 404)
    return {**document, "saved_practice": store.current_practice(owner, source_id)}


def reuse_upload(owner, revision, kind, filename):
    with get_database().connection() as conn:
        conn.execute("SELECT id FROM repoviva.users WHERE id=%s FOR NO KEY UPDATE", (owner,))
        source = conn.execute("SELECT id,document FROM repoviva.sources WHERE owner=%s AND document->>'revision'=%s AND document->>'kind'=%s ORDER BY active DESC,last_opened_at DESC,id LIMIT 1", (owner, revision, kind)).fetchone()
        if not source:
            return None
        document = source["document"]
        aliases = list(document.get("aliases", []))
        if filename != document["filename"] and filename not in aliases and len(aliases) < 20:
            document = {**document, "aliases": [*aliases, filename]}
        conn.execute("UPDATE repoviva.sources SET active=false WHERE owner=%s AND active AND id<>%s", (owner, source["id"]))
        conn.execute("UPDATE repoviva.sources SET active=true,last_opened_at=now(),document=%s WHERE id=%s AND owner=%s", (Jsonb(document), source["id"], owner))
    return {**restored_document(owner, source["id"]), "reused": True}


def save_upload(owner, document):
    # Check again under the same user lock after extraction: simultaneous uploads
    # may both extract, but only one new source is inserted.
    with get_database().connection() as conn:
        conn.execute("SELECT id FROM repoviva.users WHERE id=%s FOR NO KEY UPDATE", (owner,))
        existing = conn.execute("SELECT id FROM repoviva.sources WHERE owner=%s AND document->>'revision'=%s AND document->>'kind'=%s LIMIT 1", (owner, document["revision"], document["kind"])).fetchone()
        if existing:
            source_id = existing["id"]
        else:
            source_id = document["source_id"]
        if not existing and owner.startswith('guest:') and not document.get('prepared_example'):
            if conn.execute("SELECT count(*) AS n FROM repoviva.sources WHERE owner=%s AND NOT(document ? 'prepared_example')", (owner,)).fetchone()['n'] >= 5:
                raise StudyConflict('Guest storage holds up to five files. Delete an older file from History or sign in with Google.', 429)
        conn.execute("UPDATE repoviva.sources SET active=false WHERE owner=%s AND active AND id<>%s", (owner, source_id))
        if existing:
            conn.execute("UPDATE repoviva.sources SET active=true,last_opened_at=now() WHERE id=%s AND owner=%s", (source_id, owner))
        else:
            document = {**document, "expires_in_seconds": None}
            conn.execute("INSERT INTO repoviva.sources(id,owner,document) VALUES(%s,%s,%s)", (source_id, owner, Jsonb(document)))
    return {**restored_document(owner, source_id), "reused": bool(existing)}


def activate(owner, source_id, practice_id=None):
    with get_database().connection() as conn:
        conn.execute("SELECT id FROM repoviva.users WHERE id=%s FOR NO KEY UPDATE", (owner,))
        if not conn.execute("SELECT id FROM repoviva.sources WHERE id=%s AND owner=%s", (source_id, owner)).fetchone():
            raise StudyConflict("Material not found.", 404)
        if practice_id is not None and not conn.execute("SELECT id FROM repoviva.practice_sets WHERE id=%s AND source_id=%s AND owner=%s", (practice_id, source_id, owner)).fetchone():
            raise StudyConflict("Practice not found.", 404)
        conn.execute("UPDATE repoviva.sources SET active=false WHERE owner=%s AND active AND id<>%s", (owner, source_id))
        conn.execute("UPDATE repoviva.sources SET active=true,last_opened_at=now(),selected_practice_id=%s WHERE id=%s AND owner=%s", (practice_id, source_id, owner))
    return restored_document(owner, source_id)


def offset():
    try:
        value = int(request.args.get("offset", "0"))
        if not 0 <= value <= 100000:
            raise ValueError
        return value
    except ValueError:
        raise StudyConflict("Invalid history page.", 400)


def require_storage():
    if not database_enabled():
        raise StudyConflict("Saved history requires the PostgreSQL connection. Temporary development mode has no saved library.", 503)


@library.get("/history/documents")
def documents():
    require_storage()
    owner, start = g.user["id"], offset()
    query = request.args.get("q", "").strip()[:120]
    with get_database().connection() as conn:
        rows = conn.execute("""WITH grouped AS (
            SELECT (array_agg(id ORDER BY active DESC,last_opened_at DESC,id))[1] AS id,array_agg(id) AS ids,
                max(last_opened_at) AS last_opened_at,bool_or(active) AS active
            FROM repoviva.sources WHERE owner=%s AND (document->>'filename' ILIKE %s OR COALESCE(document->'aliases','[]')::text ILIKE %s)
            GROUP BY COALESCE(document->>'revision',id),document->>'kind')
            SELECT g.id,g.last_opened_at,g.active,s.document->>'filename' AS filename,s.document->>'kind' AS kind,
                (SELECT count(*) FROM repoviva.practice_sets p WHERE p.owner=%s AND p.source_id=ANY(g.ids)) AS practice_count
            FROM grouped g JOIN repoviva.sources s ON s.id=g.id AND s.owner=%s
            ORDER BY g.last_opened_at DESC,g.id LIMIT %s OFFSET %s""", (owner, f"%{query}%", f"%{query}%", owner, owner, PAGE_SIZE + 1, start)).fetchall()
    return jsonify({"documents": [{**row, "last_opened_at": row["last_opened_at"].isoformat()} for row in rows[:PAGE_SIZE]], "next_offset": start + PAGE_SIZE if len(rows) > PAGE_SIZE else None})


@library.get("/history/documents/<source_id>")
def document_history(source_id):
    require_storage()
    owner, start = g.user["id"], offset()
    with get_database().connection() as conn:
        source = conn.execute("SELECT document FROM repoviva.sources WHERE id=%s AND owner=%s", (source_id, owner)).fetchone()
        if not source:
            raise StudyConflict("Material not found.", 404)
        doc = source["document"]
        ids = conn.execute("SELECT id FROM repoviva.sources WHERE owner=%s AND (id=%s OR (document->>'revision'=%s AND document->>'kind'=%s))", (owner, source_id, doc["revision"], doc["kind"])).fetchall()
        rows = conn.execute("""SELECT p.id,p.source_id,p.created_at,count(t.id) AS questions,count(a.id) AS answered,
            COALESCE(sum(a.earned),0) AS earned,COALESCE(sum(a.possible),0) AS possible
            FROM repoviva.practice_sets p LEFT JOIN repoviva.turns t ON t.practice_id=p.id AND t.owner=%s
            LEFT JOIN LATERAL (SELECT id,earned,possible FROM repoviva.attempts WHERE turn_id=t.id AND owner=%s ORDER BY created_at DESC,id DESC LIMIT 1) a ON true
            WHERE p.owner=%s AND p.source_id=ANY(%s) GROUP BY p.id ORDER BY p.created_at DESC,p.id DESC LIMIT %s OFFSET %s""", (owner, owner, owner, [row["id"] for row in ids], PAGE_SIZE + 1, start)).fetchall()
    sets = [{"id": row["id"], "source_id": row["source_id"], "created_at": row["created_at"].isoformat(), "questions": row["questions"], "answered": row["answered"],
             "score": round(100 * float(row["earned"]) / float(row["possible"])) if row["questions"] == row["answered"] and row["possible"] else None} for row in rows[:PAGE_SIZE]]
    return jsonify({"source_id": source_id, "filename": doc["filename"], "kind": doc["kind"], "practice_sets": sets, "next_offset": start + PAGE_SIZE if len(rows) > PAGE_SIZE else None})


@library.post("/sources/<source_id>/activate")
def activate_source(source_id):
    require_storage()
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or ("practice_id" in data and not isinstance(data["practice_id"], str)):
        raise StudyConflict("Send a valid practice selection.", 400)
    document = activate(g.user["id"], source_id, data.get("practice_id"))
    session["active_source_id"] = source_id
    return jsonify(document)


@library.post("/sources/<source_id>/close")
def close_source(source_id):
    require_storage()
    with get_database().connection() as conn:
        if not conn.execute("UPDATE repoviva.sources SET active=false WHERE id=%s AND owner=%s RETURNING id", (source_id, g.user["id"])).fetchone():
            raise StudyConflict("Material not found.", 404)
    if session.get("active_source_id") == source_id:
        session.pop("active_source_id", None)
    return "", 204


@library.post("/history/practice-sets/<practice_id>/retry")
def retry_practice(practice_id):
    require_storage()
    owner = g.user["id"]
    store = get_database()
    with store.connection() as conn:
        practice = conn.execute("SELECT source_id FROM repoviva.practice_sets WHERE id=%s AND owner=%s", (practice_id, owner)).fetchone()
        if not practice:
            raise StudyConflict("Practice not found.", 404)
        rows = conn.execute("SELECT payload FROM repoviva.turns WHERE practice_id=%s AND owner=%s AND NOT(payload ? 'parent_turn_id') ORDER BY position", (practice_id, owner)).fetchall()
    activate(owner, practice["source_id"], practice_id)
    # Retrying an archived Boolean demo starts the current explanatory version;
    # the old questions and scores stay untouched in that historical practice.
    from backend import example
    if rows and all(row['payload']['question_package'].get('prepared_example') in {'prime-v1', example.QUESTION_VERSION} for row in rows):
        template = rows[0]['payload']
        rows = [{'payload': {**template, 'question': package['question'], 'question_package': {**package, 'language': template['question_package'].get('language', 'en')},
                             'snippet': next(item for item in template['snippets'] if str(item['id']) == package['rubric'][0]['snippet_id'])}}
                for package in example.question_set(template['snippets'], min(len(rows), 3), template['question_package'].get('language', 'en'))]
    records = {uuid.uuid4().hex: {**row["payload"], "created": time.monotonic(), "busy": False} for row in rows}
    if not records:
        raise StudyConflict("This practice has no saved questions.", 409)
    store.save_questions(owner, practice["source_id"], records)
    session["active_source_id"] = practice["source_id"]
    return jsonify(restored_document(owner, practice["source_id"]))


@library.put("/history/turns/<turn_id>/draft")
def save_draft(turn_id):
    require_storage()
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("answer"), str) or len(data["answer"]) > 4000:
        raise StudyConflict("Draft must be text up to 4,000 characters.", 400)
    from backend.speech.review import resolve_review
    speech = resolve_review(g.user['id'],turn_id,data.get('speech_review'))
    with get_database().connection() as conn:
        turn = conn.execute("SELECT practice_id,busy_until>now() AS busy FROM repoviva.turns WHERE id=%s AND owner=%s FOR UPDATE", (turn_id, g.user["id"])).fetchone()
        if not turn:
            raise StudyConflict("Question not found.", 404)
        if turn["busy"]:
            raise StudyConflict("This answer is being reviewed. Please wait.", 409)
        conn.execute("INSERT INTO repoviva.drafts(turn_id,owner,answer,speech_review) VALUES(%s,%s,%s,%s) ON CONFLICT(turn_id) DO UPDATE SET answer=EXCLUDED.answer,speech_review=EXCLUDED.speech_review,updated_at=now()", (turn_id, g.user["id"], data["answer"],Jsonb(speech) if speech else None))
        conn.execute("UPDATE repoviva.practice_sets SET last_turn_id=%s WHERE id=%s AND owner=%s", (turn_id, turn["practice_id"], g.user["id"]))
    return jsonify({"saved": True})


@library.delete("/history/documents/<source_id>")
def delete_document(source_id):
    require_storage()
    owner = g.user["id"]
    with get_database().connection() as conn:
        conn.execute("SELECT id FROM repoviva.users WHERE id=%s FOR NO KEY UPDATE", (owner,))
        row = conn.execute("SELECT document FROM repoviva.sources WHERE id=%s AND owner=%s", (source_id, owner)).fetchone()
        if not row:
            raise StudyConflict("Material not found.", 404)
        ids = conn.execute("DELETE FROM repoviva.sources WHERE owner=%s AND (id=%s OR (document->>'revision'=%s AND document->>'kind'=%s)) RETURNING id", (owner, source_id, row["document"]["revision"], row["document"]["kind"])).fetchall()
    deleted = [row["id"] for row in ids]
    if session.get("active_source_id") in deleted:
        session.pop("active_source_id", None)
    return jsonify({"deleted_ids": deleted})
