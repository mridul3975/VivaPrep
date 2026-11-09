import time
import uuid
from copy import deepcopy
from threading import Lock

from flask import Blueprint, g, jsonify, request, session
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from backend.evidence.documents import DocumentError, MAX_FILE_BYTES, extract_document
from backend.database import database_enabled, get_database


uploads = Blueprint("sources", __name__)
sources = {}
sources_lock = Lock()
SOURCE_TTL_SECONDS = 3600
MAX_SOURCES = 20


@uploads.after_request
def do_not_cache_uploads(response):
    response.headers["Cache-Control"] = "no-store"
    return response


def _expire_sources():
    now = time.monotonic()
    for key in list(sources):
        if now - sources[key]["created"] >= SOURCE_TTL_SECONDS:
            del sources[key]


def owned_source(source_id):
    """Return a snapshot only when this browser session owns the live upload."""
    if database_enabled():
        return get_database().source(g.user["id"], source_id)
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != g.user["id"]:
            return None
        return deepcopy(source["document"])


def next_source_snippet(source_id):
    if database_enabled():
        def select_one(document, start):
            snippets = document["snippets"]
            return [snippets[start % len(snippets)]], start + 1
        result = get_database().next_evidence(g.user["id"], source_id, select_one)
        return (result[0][0], result[1]) if result else None
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != g.user["id"]:
            return None
        document = source["document"]
        index = source.get("next_snippet", 0) % len(document["snippets"])
        source["next_snippet"] = index + 1
        return deepcopy(document["snippets"][index]), document["revision"]


def next_source_evidence(source_id):
    """Select a bounded packet of real uploaded chunks, rotating across sets."""
    if database_enabled():
        return get_database().next_evidence(g.user["id"], source_id, _select_packet)
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != g.user["id"]:
            return None
        document = source["document"]
        selected, source["next_snippet"] = _select_packet(document, source.get("next_snippet", 0))
        return selected, document["revision"]


def _select_packet(document, start):
    snippets = document["snippets"]
    start %= len(snippets)
    selected, used, next_index = [], 0, start
    for offset in range(len(snippets)):
        index = (start + offset) % len(snippets)
        text = "\n".join(snippets[index]["content"])
        if not text.strip() or len(text) > 12000 or used + len(text) > 12000:
            continue
        selected.append(deepcopy(snippets[index]))
        used += len(text)
        next_index = index + 1
        if len(selected) == 5:
            break
    if not selected:
        raise DocumentError("The evidence sections are too long. Upload material with shorter sections or lines.", 422)
    return selected, next_index


@uploads.post("/sources")
def upload_source():
    request.max_content_length = MAX_FILE_BYTES + 64 * 1024
    if request.content_length and request.content_length > request.max_content_length:
        return jsonify({"error": "Uploaded files must be at most 5 MiB."}), 413
    try:
        files = request.files.getlist("source_file")
        if len(files) != 1 or not files[0].filename:
            return jsonify({"error": "Upload one file using the source_file field."}), 400
        upload = files[0]
        try:
            filename = secure_filename(upload.filename)
            if not filename:
                return jsonify({"error": "The file needs a readable filename and extension."}), 400
            data = upload.stream.read(MAX_FILE_BYTES + 1)
        finally:
            upload.close()
        document = extract_document(filename, data)
    except RequestEntityTooLarge:
        return jsonify({"error": "Uploaded files must be at most 5 MiB."}), 413
    except DocumentError as error:
        return jsonify({"error": str(error)}), error.status

    owner = g.user["id"]
    source_id = uuid.uuid4().hex
    for number, snippet in enumerate(document["snippets"], 1):
        snippet["id"] = f"{source_id}:{number}"
    document.update({"source_id": source_id, "expires_in_seconds": SOURCE_TTL_SECONDS})
    if database_enabled():
        document = get_database().replace_source(owner, document)
        session["active_source_id"] = source_id
        return jsonify(document), 201
    with sources_lock:
        _expire_sources()
        previous = [key for key, item in sources.items() if item["owner"] == owner]
        if len(sources) - len(previous) >= MAX_SOURCES:
            return jsonify({"error": "Upload storage is full. Please retry later."}), 503
        for key in previous:
            del sources[key]
        sources[source_id] = {"owner": owner, "created": time.monotonic(), "document": document}
    session["active_source_id"] = source_id
    return jsonify(document), 201


@uploads.get("/sources/current")
def current_source():
    if database_enabled():
        store = get_database()
        document = store.source(g.user["id"])
        if document is None:
            session.pop("active_source_id", None)
            return "", 204
        if session.get("active_source_id") != document["source_id"]:
            session["active_source_id"] = document["source_id"]
        return jsonify({**document, "saved_practice": store.current_practice(g.user["id"], document["source_id"])})
    source_id = session.get("active_source_id")
    if not source_id:
        with sources_lock:
            _expire_sources()
            source_id = next((key for key, value in sources.items() if value["owner"] == g.user["id"]), None)
        if not source_id:
            return "", 204
        session["active_source_id"] = source_id
    document = owned_source(source_id)
    if document is None:
        return jsonify({"error": "Your upload expired or was replaced. Upload the file again."}), 404
    return jsonify(document)


@uploads.get("/sources/<source_id>")
def get_source(source_id):
    if database_enabled():
        document = get_database().source(g.user["id"], source_id)
        if document is None:
            return jsonify({"error": "Upload not found."}), 404
        return jsonify(document)
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != g.user["id"]:
            return jsonify({"error": "Upload not found or expired. Please upload the file again."}), 404
        return jsonify(source["document"])


@uploads.delete("/sources/<source_id>")
def delete_source(source_id):
    if database_enabled():
        if not get_database().remove_source(g.user["id"], source_id):
            return jsonify({"error": "Upload not found."}), 404
        if session.get("active_source_id") == source_id:
            session.pop("active_source_id", None)
        return "", 204
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != g.user["id"]:
            return jsonify({"error": "Upload not found or expired."}), 404
        del sources[source_id]
    if session.get("active_source_id") == source_id:
        session.pop("active_source_id", None)
    return "", 204
