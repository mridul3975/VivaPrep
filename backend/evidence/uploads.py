import time
import uuid
from copy import deepcopy
from threading import Lock

from flask import Blueprint, jsonify, request, session
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from backend.evidence.documents import DocumentError, MAX_FILE_BYTES, extract_document


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
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != session.get("source_owner"):
            return None
        return deepcopy(source["document"])


def next_source_snippet(source_id):
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != session.get("source_owner"):
            return None
        document = source["document"]
        index = source.get("next_snippet", 0) % len(document["snippets"])
        source["next_snippet"] = index + 1
        return deepcopy(document["snippets"][index]), document["revision"]


def next_source_evidence(source_id):
    """Select a bounded packet of real uploaded chunks, rotating across sets."""
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != session.get("source_owner"):
            return None
        document = source["document"]
        snippets = document["snippets"]
        start = source.get("next_snippet", 0) % len(snippets)
        selected, used = [], 0
        for offset in range(len(snippets)):
            index = (start + offset) % len(snippets)
            size = len("\n".join(snippets[index]["content"]))
            if size > 12000 or used + size > 12000:
                continue
            selected.append(deepcopy(snippets[index]))
            used += size
            source["next_snippet"] = index + 1
            if len(selected) == 5:
                break
        if not selected:
            raise DocumentError("The evidence sections are too long. Upload material with shorter sections or lines.", 422)
        return selected, document["revision"]


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

    owner = session.setdefault("source_owner", uuid.uuid4().hex)
    with sources_lock:
        _expire_sources()
        previous = [key for key, item in sources.items() if item["owner"] == owner]
        if len(sources) - len(previous) >= MAX_SOURCES:
            return jsonify({"error": "Upload storage is full. Please retry later."}), 503
        for key in previous:
            del sources[key]
        source_id = uuid.uuid4().hex
        for number, snippet in enumerate(document["snippets"], 1):
            snippet["id"] = f"{source_id}:{number}"
        document.update({"source_id": source_id, "expires_in_seconds": SOURCE_TTL_SECONDS})
        sources[source_id] = {"owner": owner, "created": time.monotonic(), "document": document}
    session["active_source_id"] = source_id
    return jsonify(document), 201


@uploads.get("/sources/current")
def current_source():
    source_id = session.get("active_source_id")
    if not source_id:
        return "", 204
    document = owned_source(source_id)
    if document is None:
        return jsonify({"error": "Your upload expired or was replaced. Upload the file again."}), 404
    return jsonify(document)


@uploads.get("/sources/<source_id>")
def get_source(source_id):
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != session.get("source_owner"):
            return jsonify({"error": "Upload not found or expired. Please upload the file again."}), 404
        return jsonify(source["document"])


@uploads.delete("/sources/<source_id>")
def delete_source(source_id):
    with sources_lock:
        _expire_sources()
        source = sources.get(source_id)
        if source is None or source["owner"] != session.get("source_owner"):
            return jsonify({"error": "Upload not found or expired."}), 404
        del sources[source_id]
    if session.get("active_source_id") == source_id:
        session.pop("active_source_id", None)
    return "", 204
