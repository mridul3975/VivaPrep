"""Atomic shared guest budgets and bounded session creation; no raw IP storage."""
import hashlib
import hmac
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from threading import Lock
from flask import current_app, request
from backend.database import database_enabled, get_database, StudyConflict

events = {}
lock = Lock()
DEFAULTS = {'sessions': 200, 'questions': 60, 'answers': 180, 'transcriptions': 30}


def setting(name, default):
    try:
        return max(0, min(10000, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def network_bucket():
    # Use the actual peer; deployments can configure a trusted proxy explicitly.
    peer = request.remote_addr or 'unknown'
    return hmac.new(str(current_app.secret_key).encode(), peer.encode(), hashlib.sha256).hexdigest()


@contextmanager
def guest_reservation(action):
    today = datetime.now(timezone.utc).date()
    token, bucket = uuid.uuid4().hex, network_bucket() if action == 'sessions' else 'ai'
    maximum = setting('GUEST_DAILY_' + action.upper() + '_LIMIT', DEFAULTS[action])
    per_network = setting('GUEST_SESSIONS_PER_NETWORK', 10)
    # Without an explicitly trusted client-IP chain on Render, its shared proxy
    # must not accidentally receive the small per-network limit for all visitors.
    if os.getenv('RENDER') == 'true' and setting('TRUSTED_PROXY_HOPS', 0) == 0:
        per_network = maximum
    message = ('Guest access is busy for this network today. Sign in with Google or try again tomorrow.' if action == 'sessions'
               else 'Today’s shared guest AI allowance is used up. You can still use the free Python example, or sign in with Google.')
    persistent = database_enabled()
    if persistent:
        with get_database().connection() as conn:
            conn.execute('SELECT pg_advisory_xact_lock(72901832)')
            conn.execute('DELETE FROM repoviva.guest_events WHERE period < %s', (today,))
            row = conn.execute('SELECT count(*) AS total,count(*) FILTER(WHERE bucket=%s) AS network FROM repoviva.guest_events WHERE period=%s AND action=%s', (bucket, today, action)).fetchone()
            if row['total'] >= maximum or (action == 'sessions' and row['network'] >= per_network):
                raise StudyConflict(message, 429)
            conn.execute('INSERT INTO repoviva.guest_events(id,period,bucket,action) VALUES(%s,%s,%s,%s)', (token,today,bucket,action))
    else:
        with lock:
            for key in list(events):
                if events[key][0] != today:
                    del events[key]
            current = [value for value in events.values() if value[2] == action]
            if len(current) >= maximum or (action == 'sessions' and sum(value[1] == bucket for value in current) >= per_network):
                raise StudyConflict(message, 429)
            events[token] = (today,bucket,action)
    try:
        yield
    except Exception:
        if persistent:
            with get_database().connection() as conn:
                conn.execute('DELETE FROM repoviva.guest_events WHERE id=%s', (token,))
        else:
            with lock:
                events.pop(token, None)
        raise
