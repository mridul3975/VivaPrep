"""Owned, persisted one-step viva follow-ups. Uses the submitted server-side answer."""
import time
import uuid
from contextlib import nullcontext
from flask import Blueprint, g, jsonify, request, current_app
from psycopg.types.json import Jsonb
from backend.database import get_database, StudyConflict, public_question
from backend.library import require_storage
from backend.account import allowance
from backend.interview.followup import generate_followup
from backend.interview.provider import ProviderError
from backend import example

viva = Blueprint('viva', __name__, url_prefix='/viva')


@viva.post('/turns/<turn_id>/follow-up')
def follow_up(turn_id):
    require_storage()
    request.max_content_length = 1024
    if request.content_length and request.get_json(silent=True) != {}:
        raise StudyConflict('The follow-up uses your saved answer. Send no extra fields.', 400)
    store = get_database()
    with store.connection() as conn:
        row = conn.execute('SELECT payload FROM repoviva.turns WHERE id=%s AND owner=%s', (turn_id,g.user['id'])).fetchone()
        if not row:
            raise StudyConflict('Question not found.', 404)
        if row['payload'].get('parent_turn_id'):
            raise StudyConflict('This short viva has one follow-up per original question. Continue to the next question.', 400)
        cached = conn.execute("SELECT id,payload FROM repoviva.turns WHERE owner=%s AND payload->>'parent_turn_id'=%s", (g.user['id'],turn_id)).fetchone()
        if cached:
            return jsonify(public_question(cached['id'],cached['payload']))
    parent, lease = store.claim_turn(g.user['id'],turn_id)
    try:
        with store.connection() as conn:
            attempt = conn.execute('SELECT answer FROM repoviva.attempts WHERE turn_id=%s AND owner=%s ORDER BY created_at DESC,id DESC LIMIT 1', (turn_id,g.user['id'])).fetchone()
        if not attempt:
            raise StudyConflict('Submit your answer before asking a follow-up.', 409)
        prepared = parent['question_package'].get('prepared_example') in {'prime-v1', example.QUESTION_VERSION}
        with nullcontext() if prepared else allowance('questions'):
            package = example.followup(parent,attempt['answer']) if prepared else generate_followup(parent,attempt['answer'])
            primary = next(item for item in parent['snippets'] if item['id'] == package['rubric'][0]['snippet_id'])
            payload = {**parent, 'question':package['question'], 'question_package':package, 'snippet':primary,
                       'parent_turn_id':turn_id, 'parent_answer':attempt['answer'], 'created':time.monotonic(), 'busy':False}
            child_id = uuid.uuid4().hex
            with store.connection() as conn:
                root = conn.execute('SELECT practice_id FROM repoviva.turns WHERE id=%s AND owner=%s AND lease_token=%s FOR UPDATE', (turn_id,g.user['id'],lease)).fetchone()
                if not root:
                    raise StudyConflict('The session changed during generation. Retry.', 409)
                conn.execute('SELECT id FROM repoviva.practice_sets WHERE id=%s FOR UPDATE', (root['practice_id'],))
                position = conn.execute('SELECT coalesce(max(position),-1)+1 AS n FROM repoviva.turns WHERE practice_id=%s', (root['practice_id'],)).fetchone()['n']
                conn.execute('INSERT INTO repoviva.turns(id,owner,practice_id,position,payload) VALUES(%s,%s,%s,%s,%s)', (child_id,g.user['id'],root['practice_id'],position,Jsonb(payload)))
                conn.execute('UPDATE repoviva.practice_sets SET last_turn_id=%s WHERE id=%s', (child_id,root['practice_id']))
    except (ProviderError, ValueError, KeyError, TypeError) as error:
        current_app.logger.warning('Viva follow-up failed: %s', type(error).__name__)
        return jsonify({'error':'Could not create a source-grounded follow-up. Your answer and feedback are saved; retry or continue to the next question.'}), 503 if isinstance(error,ProviderError) and error.status_code == 429 else 502
    finally:
        store.release_turn(g.user['id'],turn_id,lease)
    return jsonify(public_question(child_id,payload)), 201
