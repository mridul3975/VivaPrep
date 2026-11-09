"""Authenticated local test clients; never a public authentication bypass."""
import secrets
import time

from backend.auth import auth_lock, auth_sessions
from backend.database import database_enabled, get_database


def authenticated_client(app, user_id=None):
    # Legacy feature/provider harnesses explicitly exercise temporary storage.
    # PostgreSQL integration tests override this with their isolated test URL.
    app.config.setdefault("DATABASE_URL_OVERRIDE", "")
    client = app.test_client()
    session_id, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    user = {"id": user_id or f"google:test-{secrets.token_hex(8)}",
            "email": "student@example.test", "name": "Test student"}
    with app.app_context():
        if database_enabled():
            get_database().save_login(user, session_id, time.time() + 3600)
        else:
            with auth_lock:
                auth_sessions[session_id] = {"user": user, "expires_at": time.time() + 3600}
    with client.session_transaction() as state:
        state["auth_session_id"] = session_id
        state["csrf_token"] = csrf
    client.environ_base["HTTP_X_CSRF_TOKEN"] = csrf
    return client
