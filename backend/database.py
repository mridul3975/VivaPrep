"""PostgreSQL persistence. Configured database failures never fall back to memory."""
import hashlib
import logging
import os
import time
import uuid
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import psycopg
from flask import current_app, has_app_context
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool, PoolTimeout


class DatabaseUnavailable(RuntimeError):
    pass


class StudyConflict(RuntimeError):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def database_url():
    if has_app_context() and "DATABASE_URL_OVERRIDE" in current_app.config:
        return current_app.config["DATABASE_URL_OVERRIDE"]
    return os.getenv("DATABASE_URL", "").strip()


def database_enabled():
    return bool(database_url())


def public_question(turn_id, turn):
    return {"turn_id": turn_id, "source_id": turn["source_id"], "question": turn["question"],
            'parent_turn_id': turn.get('parent_turn_id'), 'parent_answer': turn.get('parent_answer'),
            "evidence": turn["snippet"], "evidence_snippets": turn["snippets"]}


@lru_cache(maxsize=4)
def _store(url):
    return PostgresStore(url)


def get_database(*, migration=False):
    url = database_url()
    # Neon pulls both URLs: application traffic uses PgBouncer, while schema
    # changes use the direct endpoint. Test overrides always remain isolated.
    if migration and not (has_app_context() and "DATABASE_URL_OVERRIDE" in current_app.config):
        url = os.getenv("DATABASE_URL_UNPOOLED", "").strip() or url
    if not url:
        raise DatabaseUnavailable("PostgreSQL is not configured.")
    return _store(url)


def close_pools():
    for pool in PostgresStore.pools:
        pool.close()
    PostgresStore.pools.clear()
    _store.cache_clear()


class PostgresStore:
    pools = []

    def __init__(self, url):
        if not url.startswith(("postgres://", "postgresql://")):
            raise DatabaseUnavailable("DATABASE_URL must be a PostgreSQL connection URL.")
        # Pool reconnect logs can include connection metadata; expose only safe errors.
        logging.getLogger("psycopg.pool").setLevel(logging.CRITICAL)
        try:
            self.pool = ConnectionPool(url, min_size=0, max_size=5, timeout=20,
                                       kwargs={"connect_timeout": 15, "row_factory": dict_row},
                                       check=ConnectionPool.check_connection, open=True)
        except (psycopg.Error, ValueError) as error:
            raise DatabaseUnavailable("PostgreSQL could not be configured.") from error
        self.pools.append(self.pool)

    @contextmanager
    def connection(self):
        try:
            with self.pool.connection() as conn:
                yield conn
        except (psycopg.Error, PoolTimeout) as error:
            raise DatabaseUnavailable("Saved data is temporarily unavailable. Please retry.") from error

    def migrate(self):
        with self.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(72901831)")
            conn.execute("CREATE SCHEMA IF NOT EXISTS repoviva")
            conn.execute("CREATE TABLE IF NOT EXISTS repoviva.schema_migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())")
            for path in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                version = int(path.name.split("_")[0])
                if conn.execute("SELECT 1 FROM repoviva.schema_migrations WHERE version = %s", (version,)).fetchone():
                    continue
                conn.execute(path.read_text(encoding="utf-8"), prepare=False)
                conn.execute("INSERT INTO repoviva.schema_migrations(version) VALUES (%s)", (version,))

    def check(self):
        with self.connection() as conn:
            row = conn.execute("SELECT max(version) AS version FROM repoviva.schema_migrations").fetchone()
            expected = max(int(path.name.split("_")[0]) for path in (Path(__file__).parent / "migrations").glob("*.sql"))
            if row["version"] != expected:
                raise DatabaseUnavailable("Database migrations need to be applied.")

    @staticmethod
    def _session_hash(session_id):
        return hashlib.sha256(session_id.encode()).hexdigest()

    def save_login(self, user, session_id, expires_at, old_session_id=None, guest_owner=None):
        with self.connection() as conn:
            conn.execute("INSERT INTO repoviva.users(id, email, name) VALUES (%s,%s,%s) ON CONFLICT(id) DO UPDATE SET email=EXCLUDED.email, name=EXCLUDED.name, last_sign_in=now()", (user["id"], user["email"], user["name"]))
            if guest_owner:
                if not guest_owner.startswith('guest:'):
                    raise ValueError('Only guest work can be transferred')
                conn.execute('SELECT id FROM repoviva.users WHERE id=%s FOR UPDATE', (guest_owner,))
                if conn.execute('SELECT 1 FROM repoviva.sources WHERE owner=%s AND active', (user['id'],)).fetchone():
                    conn.execute('UPDATE repoviva.sources SET active=false WHERE owner=%s', (guest_owner,))
                for table in ('sources', 'practice_sets', 'turns', 'attempts', 'drafts', 'debug_runs', 'api_usage', 'transcript_reviews'):
                    conn.execute(f'UPDATE repoviva.{table} SET owner=%s WHERE owner=%s', (user['id'], guest_owner))
                conn.execute("UPDATE repoviva.turns SET payload=jsonb_set(payload,'{owner}',to_jsonb(%s::text)) WHERE owner=%s AND payload->>'owner'=%s", (user['id'],user['id'],guest_owner))
                conn.execute('DELETE FROM repoviva.users WHERE id=%s', (guest_owner,))
            conn.execute("DELETE FROM repoviva.login_sessions WHERE expires_at <= %s", (time.time(),))
            if old_session_id:
                conn.execute("DELETE FROM repoviva.login_sessions WHERE token_hash=%s", (self._session_hash(old_session_id),))
            conn.execute("INSERT INTO repoviva.login_sessions(token_hash, owner, expires_at) VALUES (%s,%s,%s)", (self._session_hash(session_id), user["id"], expires_at))

    def identity(self, session_id):
        if not isinstance(session_id, str) or not session_id:
            return None, None
        with self.connection() as conn:
            row = conn.execute("SELECT u.id, u.email, u.name, s.expires_at FROM repoviva.login_sessions s JOIN repoviva.users u ON u.id=s.owner WHERE s.token_hash=%s AND s.expires_at>%s", (self._session_hash(session_id), time.time())).fetchone()
        return ({key: row[key] for key in ("id", "email", "name")}, row["expires_at"]) if row else (None, None)

    def logout(self, session_id):
        if session_id:
            with self.connection() as conn:
                conn.execute("DELETE FROM repoviva.login_sessions WHERE token_hash=%s", (self._session_hash(session_id),))

    def replace_source(self, owner, document):
        document = {**document, "expires_in_seconds": None}
        with self.connection() as conn:
            conn.execute("SELECT id FROM repoviva.users WHERE id=%s FOR NO KEY UPDATE", (owner,))
            conn.execute("UPDATE repoviva.sources SET active=false WHERE owner=%s AND active", (owner,))
            conn.execute("INSERT INTO repoviva.sources(id,owner,document) VALUES (%s,%s,%s)", (document["source_id"], owner, Jsonb(document)))
        return document

    def source(self, owner, source_id=None):
        with self.connection() as conn:
            if source_id:
                row = conn.execute("SELECT document FROM repoviva.sources WHERE id=%s AND owner=%s AND active", (source_id, owner)).fetchone()
            else:
                row = conn.execute("SELECT document FROM repoviva.sources WHERE owner=%s AND active", (owner,)).fetchone()
        return row["document"] if row else None

    def remove_source(self, owner, source_id):
        with self.connection() as conn:
            return bool(conn.execute("DELETE FROM repoviva.sources WHERE id=%s AND owner=%s RETURNING id", (source_id, owner)).fetchone())

    def next_evidence(self, owner, source_id, select_packet):
        with self.connection() as conn:
            row = conn.execute("SELECT document, next_snippet FROM repoviva.sources WHERE id=%s AND owner=%s AND active FOR UPDATE", (source_id, owner)).fetchone()
            if not row:
                return None
            selected, next_index = select_packet(row["document"], row["next_snippet"])
            conn.execute("UPDATE repoviva.sources SET next_snippet=%s WHERE id=%s AND owner=%s", (next_index, source_id, owner))
            return selected, row["document"]["revision"]

    def save_questions(self, owner, source_id, records):
        practice_id = uuid.uuid4().hex
        with self.connection() as conn:
            if not conn.execute("SELECT id FROM repoviva.sources WHERE id=%s AND owner=%s AND active FOR UPDATE", (source_id, owner)).fetchone():
                raise StudyConflict("Your material changed while questions were generated. Please generate a new set.")
            conn.execute("INSERT INTO repoviva.practice_sets(id,owner,source_id) VALUES (%s,%s,%s)", (practice_id, owner, source_id))
            for position, (turn_id, turn) in enumerate(records.items()):
                conn.execute("INSERT INTO repoviva.turns(id,owner,practice_id,position,payload) VALUES (%s,%s,%s,%s,%s)", (turn_id, owner, practice_id, position, Jsonb(turn)))
            conn.execute("UPDATE repoviva.sources SET selected_practice_id=%s,last_opened_at=now() WHERE id=%s AND owner=%s", (practice_id, source_id, owner))
        return practice_id

    def claim_turn(self, owner, turn_id):
        token = uuid.uuid4().hex
        with self.connection() as conn:
            row = conn.execute("UPDATE repoviva.turns SET busy_until=now()+interval '120 seconds', lease_token=%s WHERE id=%s AND owner=%s AND (busy_until IS NULL OR busy_until<now()) RETURNING payload", (token, turn_id, owner)).fetchone()
            if row:
                return row["payload"], token
            exists = conn.execute("SELECT id FROM repoviva.turns WHERE id=%s AND owner=%s", (turn_id, owner)).fetchone()
            raise StudyConflict("This answer is already being evaluated." if exists else "Turn not found. Start a new question.", 409 if exists else 404)

    def release_turn(self, owner, turn_id, token):
        with self.connection() as conn:
            conn.execute("UPDATE repoviva.turns SET busy_until=NULL,lease_token=NULL WHERE id=%s AND owner=%s AND lease_token=%s", (turn_id, owner, token))

    def save_attempt(self, owner, turn_id, token, answer, feedback):
        score = feedback["score"]
        with self.connection() as conn:
            if not conn.execute("SELECT id FROM repoviva.turns WHERE id=%s AND owner=%s AND lease_token=%s FOR UPDATE", (turn_id, owner, token)).fetchone():
                raise StudyConflict("The evaluation session changed. Please submit your answer again.")
            conn.execute("INSERT INTO repoviva.attempts(id,owner,turn_id,answer,feedback,earned,possible,percentage) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", (uuid.uuid4().hex, owner, turn_id, answer, Jsonb(feedback), score["earned"], score["possible"], score["percentage"]))
            conn.execute("DELETE FROM repoviva.drafts WHERE turn_id=%s AND owner=%s", (turn_id, owner))
            conn.execute("UPDATE repoviva.turns SET busy_until=NULL,lease_token=NULL WHERE id=%s AND owner=%s AND lease_token=%s", (turn_id, owner, token))

    def current_practice(self, owner, source_id):
        with self.connection() as conn:
            practice = conn.execute("SELECT p.id FROM repoviva.practice_sets p JOIN repoviva.sources s ON s.id=p.source_id WHERE p.owner=%s AND p.source_id=%s AND s.owner=%s AND s.active AND (s.selected_practice_id IS NULL OR s.selected_practice_id=p.id) ORDER BY p.created_at DESC,p.id DESC LIMIT 1", (owner, source_id, owner)).fetchone()
            if not practice:
                return None
            from backend.library import practice_snapshot
            return practice_snapshot(conn, owner, practice["id"])

    def history(self, owner):
        with self.connection() as conn:
            rows = conn.execute("SELECT a.id,a.turn_id,a.answer,a.earned,a.possible,a.percentage,a.created_at,t.payload->>'question' AS question,s.document->>'filename' AS filename FROM repoviva.attempts a JOIN repoviva.turns t ON t.id=a.turn_id JOIN repoviva.practice_sets p ON p.id=t.practice_id JOIN repoviva.sources s ON s.id=p.source_id WHERE a.owner=%s ORDER BY a.created_at DESC,a.id DESC LIMIT 100", (owner,)).fetchall()
        return [{**row, "created_at": row["created_at"].isoformat(),
                 **{key: float(row[key]) if row[key] is not None else None for key in ("earned", "possible", "percentage")}} for row in rows]


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    import argparse
    parser = argparse.ArgumentParser(description="Apply RepoViva's versioned PostgreSQL migrations.")
    parser.add_argument("command", choices=["migrate", "check"])
    args = parser.parse_args()
    try:
        store = get_database(migration=args.command == "migrate")
        store.migrate() if args.command == "migrate" else store.check()
        print("PostgreSQL migrations applied." if args.command == "migrate" else "PostgreSQL connection and schema verified.")
    except DatabaseUnavailable:
        raise SystemExit("PostgreSQL is unavailable. Check DATABASE_URL and database access; no connection details were printed.")
    finally:
        close_pools()


if __name__ == "__main__":
    main()
