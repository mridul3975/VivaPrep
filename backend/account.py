"""Owned profile details and atomic daily application allowances."""
import logging
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from threading import Lock

from flask import Blueprint, g, jsonify, request
from psycopg.types.json import Jsonb
from backend.database import database_enabled, get_database

account = Blueprint("account", __name__)
DEFAULTS = {"questions": ("DAILY_QUESTION_LIMIT", 10), "answers": ("DAILY_REVIEW_LIMIT", 30), "transcriptions": ("DAILY_TRANSCRIPTION_LIMIT", 10)}
memory_usage, memory_profiles = {}, {}
memory_lock = Lock()


def limits():
    result = {}
    for action, (setting, default) in DEFAULTS.items():
        try:
            result[action] = max(0, min(10000, int(os.getenv(setting, str(default)))))
        except ValueError:
            result[action] = default
    return result


def period():
    today = datetime.now(timezone.utc).date()
    return today, datetime.combine(today + timedelta(days=1), datetime.min.time(), timezone.utc)


def usage(owner):
    today, reset = period()
    if database_enabled():
        with get_database().connection() as conn:
            rows = conn.execute("SELECT action,count(*) AS used FROM repoviva.api_usage WHERE owner=%s AND period=%s GROUP BY action", (owner, today)).fetchall()
        counts = {row["action"]: row["used"] for row in rows}
    else:
        with memory_lock:
            counts = {action: sum(1 for item in memory_usage.values() if item == (owner, today, action)) for action in DEFAULTS}
    return {"reset_at": reset.isoformat(), "reset_timezone": "UTC", "allowances": {
        action: {"limit": limit, "used": counts.get(action, 0), "remaining": max(0, limit - counts.get(action, 0))}
        for action, limit in limits().items()}}


class UsageLimit(Exception):
    def __init__(self, action):
        self.action = action


def quota_error(error):
    names = {"questions": "question sets", "answers": "answer reviews", "transcriptions": "transcriptions"}
    response = jsonify({"error": f"Your daily allowance for {names[error.action]} is used up. Check Profile for the reset time.", "error_code": "daily_allowance_exceeded", "action": error.action, "usage": usage(g.user["id"])})
    response.status_code = 429
    response.headers["Retry-After"] = str(max(1, int((period()[1] - datetime.now(timezone.utc)).total_seconds())))
    return response


@contextmanager
def allowance(action):
    owner, today = g.user["id"], period()[0]
    token, limit = uuid.uuid4().hex, limits()[action]
    persistent = database_enabled()
    if persistent:
        with get_database().connection() as conn:
            conn.execute("SELECT id FROM repoviva.users WHERE id=%s FOR NO KEY UPDATE", (owner,))
            count = conn.execute("SELECT count(*) AS used FROM repoviva.api_usage WHERE owner=%s AND period=%s AND action=%s", (owner, today, action)).fetchone()["used"]
            if count >= limit:
                raise UsageLimit(action)
            conn.execute("INSERT INTO repoviva.api_usage(id,owner,period,action) VALUES(%s,%s,%s,%s)", (token, owner, today, action))
    else:
        with memory_lock:
            for key in list(memory_usage):
                if memory_usage[key][1] != today:
                    del memory_usage[key]
            if sum(1 for item in memory_usage.values() if item == (owner, today, action)) >= limit:
                raise UsageLimit(action)
            memory_usage[token] = (owner, today, action)
    try:
        yield
    except Exception:
        # Reserve before calling the provider. Known failures refund the use;
        # interrupted calls with an unknown outcome remain counted.
        try:
            if persistent:
                with get_database().connection() as conn:
                    conn.execute("DELETE FROM repoviva.api_usage WHERE id=%s AND owner=%s", (token, owner))
            else:
                with memory_lock:
                    memory_usage.pop(token, None)
        except Exception:
            logging.getLogger(__name__).warning("Could not release an unsuccessful usage reservation.")
        raise


@account.route("/profile", methods=["GET", "PATCH"])
def profile():
    owner = g.user["id"]
    if request.method == "PATCH":
        request.max_content_length = 8 * 1024
        data = request.get_json(silent=True)
        allowed = {"display_name": 80, "institution": 120, "course": 120, "study_year": 40}
        if not isinstance(data, dict) or not data or set(data) - set(allowed):
            return jsonify({"error": "Send only display name, institution, course and study year."}), 400
        if any(not isinstance(value, str) or len(value.strip()) > allowed[key] for key, value in data.items()):
            return jsonify({"error": "Profile details must be text within the field limits."}), 400
        data = {key: value.strip() for key, value in data.items()}
        if database_enabled():
            with get_database().connection() as conn:
                conn.execute("UPDATE repoviva.users SET profile=profile || %s WHERE id=%s", (Jsonb(data), owner))
        else:
            with memory_lock:
                memory_profiles.setdefault(owner, {}).update(data)
    if database_enabled():
        with get_database().connection() as conn:
            row = conn.execute("SELECT name,email,profile,created_at FROM repoviva.users WHERE id=%s", (owner,)).fetchone()
        details, joined = row["profile"], row["created_at"].isoformat()
    else:
        with memory_lock:
            details = dict(memory_profiles.get(owner, {}))
        row, joined = g.user, None
    return jsonify({"name": row["name"], "email": row["email"], "details": details, "joined_at": joined,
                    "usage": usage(owner), "storage_mode": "postgresql" if database_enabled() else "memory"})
