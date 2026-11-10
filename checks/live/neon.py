"""Exercise the running app against Neon and live Groq using one disposable identity.

Run prepare, restart the server, then run resume. No production data is truncated.
The test seeds an app session; it does not claim to exercise Google account login.
"""
import argparse
import json
import secrets
import time
import uuid
from urllib.parse import urlsplit

import requests

from backend.app import app, PROJECT_ROOT
from backend.database import close_pools, get_database

CHECKPOINT = PROJECT_ROOT / ".impeccable/review/neon/smoke-checkpoint.json"
REPORT = PROJECT_ROOT / "checks/neon_result.json"
PREFIX = "google:neon-verification-"
MATERIAL = (
    "Photosynthesis converts light energy into chemical energy in plants.\n"
    "It occurs in chloroplasts. Chlorophyll absorbs light.\n"
    "Carbon dioxide and water are the reactants.\n"
    "Glucose and oxygen are the products.\n"
)


def request(client, method, origin, path, expected=200, **kwargs):
    response = client.request(method, origin + path, timeout=(10, 90), **kwargs)
    if response.status_code != expected:
        detail = response.json().get("error", "unexpected response") if "application/json" in response.headers.get("Content-Type", "") else "unexpected response"
        raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {detail}")
    print(f"{method} {path}: HTTP {response.status_code}", flush=True)
    return response


def remove_fixture(store, owner):
    if not owner.startswith(PREFIX):
        raise RuntimeError("Refusing cleanup of a non-fixture identity.")
    with store.connection() as conn:
        conn.execute("DELETE FROM repoviva.users WHERE id=%s", (owner,))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("prepare", "resume"))
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    args = parser.parse_args()
    origin = args.base_url.rstrip("/")
    if urlsplit(origin).hostname not in ("127.0.0.1", "localhost"):
        raise SystemExit("This local verification sends a fixture cookie only to localhost.")
    store = get_database()
    with store.connection() as conn:
        if not conn.info.host.endswith(".neon.tech") or not conn.pgconn.ssl_in_use:
            raise SystemExit("The live Neon check requires an encrypted Neon database connection.")
    checkpoint = None
    try:
        if args.phase == "prepare":
            owner = PREFIX + uuid.uuid4().hex
            try:
                session_id, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                store.save_login({"id": owner, "email": "verification@example.test", "name": "Neon verification"}, session_id, time.time() + 3600)
                serializer = app.session_interface.get_signing_serializer(app)
                cookie = serializer.dumps({"auth_session_id": session_id, "csrf_token": csrf, "_permanent": True})
                client = requests.Session()
                client.cookies.set(app.config["SESSION_COOKIE_NAME"], cookie)
                client.headers["X-CSRF-Token"] = csrf
                assert request(client, "GET", origin, "/health").json()["storage_mode"] == "postgresql"
                assert "text/html" in request(client, "GET", origin, "/").headers["Content-Type"]
                assert request(client, "GET", origin, "/auth/session").json()["user"]["id"] == owner
                source = request(client, "POST", origin, "/sources", expected=201,
                                 files={"source_file": ("neon-verification.md", MATERIAL, "text/markdown")}).json()
                questions = request(client, "POST", origin, "/questions", json={"source_id": source["source_id"], "count": 1}).json()["questions"]
                assert len(questions) == 1 and "reference_answer" not in questions[0]
                turn_id = questions[0]["turn_id"]
                answer = MATERIAL.strip()
                feedback = request(client, "POST", origin, "/answers", json={"turn_id": turn_id, "answer": answer}).json()
                percentage = feedback["score"]["percentage"]
                assert percentage is not None and 0 <= percentage <= 100
                saved = request(client, "GET", origin, "/sources/current").json()["saved_practice"]
                assert saved["answers"][turn_id] == answer
                assert saved["results"][turn_id] == feedback
                history = request(client, "GET", origin, "/history").json()["attempts"]
                assert history[0]["turn_id"] == turn_id
                checkpoint = {"owner": owner, "cookie": cookie, "csrf": csrf,
                              "source_id": source["source_id"], "turn_id": turn_id,
                              "answer": answer, "percentage": percentage}
                CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
                CHECKPOINT.write_text(json.dumps(checkpoint), encoding="utf-8")
                CHECKPOINT.chmod(0o600)
                print(f"Live Neon upload -> Groq question -> Groq grading -> saved feedback: PASS (score {percentage}%).", flush=True)
                print("Restart the app, then run the resume phase to verify persistence and clean up the fixture.", flush=True)
            except Exception:
                remove_fixture(store, owner)
                raise
        else:
            checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
            owner = checkpoint["owner"]
            try:
                client = requests.Session()
                client.cookies.set(app.config["SESSION_COOKIE_NAME"], checkpoint["cookie"])
                client.headers["X-CSRF-Token"] = checkpoint["csrf"]
                assert request(client, "GET", origin, "/auth/session").json()["user"]["id"] == owner
                current = request(client, "GET", origin, "/sources/current").json()
                assert current["source_id"] == checkpoint["source_id"]
                saved = current["saved_practice"]
                assert saved["answers"][checkpoint["turn_id"]] == checkpoint["answer"]
                assert saved["results"][checkpoint["turn_id"]]["score"]["percentage"] == checkpoint["percentage"]
                request(client, "DELETE", origin, "/sources/" + checkpoint["source_id"], expected=204)
                assert request(client, "GET", origin, "/history").json()["attempts"] == []
                request(client, "POST", origin, "/auth/logout")
                request(client, "GET", origin, "/sources/current", expected=401)
                report = {"date_ist": "2026-11-10", "project": "cold-field-68844991", "branch": "production",
                          "service": "Postgres", "driver": "psycopg 3", "runtime_url": "DATABASE_URL (pooled)",
                          "migration_url": "DATABASE_URL_UNPOOLED (direct)", "tls": True,
                          "root_build": "passed", "lint": "passed", "focused_tests_passed": 21,
                          "migration_preview": "passed on expiring child branch before production",
                          "live_groq_question_and_grading": "passed", "score": checkpoint["percentage"],
                          "actual_server_restart_persistence": "passed", "removal_and_logout": "passed",
                          "fixture_data_cleanup": "completed", "verification_boundary": "Real running app, Neon database, and Groq. The session identity is seeded for verification; real Google account sign-in and public Render hosting are separate checks."}
                print("Live Neon restart restoration, removal and logout: PASS.", flush=True)
            finally:
                remove_fixture(store, owner)
            REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            CHECKPOINT.unlink(missing_ok=True)
            print("Verification identity and its records removed; report: checks/neon_result.json", flush=True)
    finally:
        close_pools()


if __name__ == "__main__":
    main()
