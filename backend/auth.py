"""Google-only sign-in and revocable, short-lived application sessions."""
import os
import secrets
import time
from hmac import compare_digest
from threading import Lock

from flask import Blueprint, g, jsonify, request, session
from google.auth import exceptions as google_errors
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from backend.database import database_enabled, get_database

auth = Blueprint("auth", __name__, url_prefix="/auth")
auth_sessions = {}
auth_lock = Lock()
AUTH_TTL_SECONDS = 3600
MAX_AUTH_SESSIONS = 1000


def _expire_sessions():
    now = time.time()
    for key in list(auth_sessions):
        if auth_sessions[key]["expires_at"] <= now:
            del auth_sessions[key]


def current_identity():
    if database_enabled():
        user, expires_at = get_database().identity(session.get("auth_session_id"))
        if user:
            return user, expires_at
        session.pop("auth_session_id", None)
        session.pop("active_source_id", None)
        return None, None
    with auth_lock:
        _expire_sessions()
        record = auth_sessions.get(session.get("auth_session_id"))
        if record:
            return {**record["user"]}, record["expires_at"]
    session.pop("auth_session_id", None)
    session.pop("active_source_id", None)
    return None, None


def _session_payload():
    user, expires_at = current_identity()
    return {
        "user": user,
        "expires_at": expires_at,
        "expires_in_seconds": max(0, expires_at - time.time()) if expires_at is not None else None,
        "csrf_token": session.setdefault("csrf_token", secrets.token_urlsafe(32)),
        "nonce": session.setdefault("google_nonce", secrets.token_urlsafe(32)),
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", "").strip() or None,
        "storage_mode": "postgresql" if database_enabled() else "memory",
    }


def _valid_csrf():
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token", "")
    return isinstance(expected, str) and bool(expected) and compare_digest(expected.encode(), supplied.encode())


def protect_study_routes():
    endpoint = request.endpoint or ""
    if endpoint not in {"retrieve_snippets", "generate_questions", "submit_answer", "transcribe_upload", "practice_history"} and not endpoint.startswith("sources."):
        return None
    user, _ = current_identity()
    if user is None:
        return jsonify({"error": "Sign in with Google to continue.", "error_code": "authentication_required"}), 401
    g.user = user
    if request.method not in {"GET", "HEAD", "OPTIONS"} and not _valid_csrf():
        return jsonify({"error": "Your session changed. Reload the page and retry.", "error_code": "invalid_csrf"}), 403
    return None


@auth.get("/session")
def get_session():
    return jsonify(_session_payload())


@auth.errorhandler(413)
def oversized_credential(error):
    return jsonify({"error": "The sign-in request is too large. Please try again."}), 413


@auth.post("/google")
def google_sign_in():
    request.max_content_length = 16 * 1024
    if not _valid_csrf():
        return jsonify({"error": "Reload the page before signing in.", "error_code": "invalid_csrf"}), 403
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        return jsonify({"error": "Google sign-in is not configured yet."}), 503
    data = request.get_json(silent=True)
    credential = data.get("credential") if isinstance(data, dict) else None
    if not isinstance(credential, str) or not credential.strip() or len(credential) > 12000:
        return jsonify({"error": "A Google sign-in credential is required."}), 400
    try:
        transport = google_requests.Request()
        claims = id_token.verify_oauth2_token(
            credential, lambda **kwargs: transport(timeout=8, **kwargs), audience=client_id,
        )
        nonce = claims.get("nonce")
        expected_nonce = session.get("google_nonce")
        if not isinstance(nonce, str) or not isinstance(expected_nonce, str) or not compare_digest(nonce, expected_nonce):
            raise ValueError("Wrong sign-in nonce")
        subject, email = claims.get("sub"), claims.get("email")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError("Missing Google identity")
        if claims.get("email_verified") is not True or not isinstance(email, str) or not email or len(email) > 320:
            raise ValueError("Unverified email")
        expires_at = min(time.time() + AUTH_TTL_SECONDS, float(claims["exp"]))
        if expires_at <= time.time():
            raise ValueError("Expired identity")
    except google_errors.TransportError:
        return jsonify({"error": "Could not reach Google. Please try signing in again."}), 503
    except (ValueError, TypeError, KeyError, google_errors.GoogleAuthError):
        return jsonify({"error": "Google sign-in could not be verified. Please try again."}), 401

    user = {"id": f"google:{subject}", "email": email,
            "name": str(claims.get("name") or email).strip()[:100]}
    new_session_id = secrets.token_urlsafe(32)
    if database_enabled():
        get_database().save_login(user, new_session_id, expires_at, session.get("auth_session_id"))
    else:
        with auth_lock:
            _expire_sessions()
            old_session_id = session.get("auth_session_id")
            if len(auth_sessions) - int(old_session_id in auth_sessions) >= MAX_AUTH_SESSIONS:
                return jsonify({"error": "Sign-in is busy. Please try again shortly."}), 503
            auth_sessions.pop(old_session_id, None)
            auth_sessions[new_session_id] = {"user": user, "expires_at": expires_at}
    # Rotate the cookie, CSRF token and nonce; never retain the Google credential.
    session.clear()
    session["auth_session_id"] = new_session_id
    session.permanent = True
    return jsonify(_session_payload())


@auth.post("/logout")
def sign_out():
    if not _valid_csrf():
        return jsonify({"error": "Reload the page before signing out.", "error_code": "invalid_csrf"}), 403
    if database_enabled():
        get_database().logout(session.get("auth_session_id"))
    else:
        with auth_lock:
            auth_sessions.pop(session.get("auth_session_id"), None)
    session.clear()
    return jsonify(_session_payload())
