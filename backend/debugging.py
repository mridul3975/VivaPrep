"""Curated, reproducible debugging practice. Submitted code is never run by Flask."""
import hashlib
import uuid
from flask import Blueprint, g, jsonify, request
from psycopg.types.json import Jsonb
from backend.database import get_database, StudyConflict
from backend.library import require_storage

debugging = Blueprint('debugging', __name__, url_prefix='/debug')


@debugging.errorhandler(413)
def oversized_run(error):
    return jsonify({'error': 'This debugging save is too large. Shorten the code or explanations and retry.'}), 413


SCENARIO_ID = 'recording-duration-v1'
STARTER = '''function validateRecording(durationMs, minSeconds) {
  if (!Number.isFinite(durationMs) || !Number.isFinite(minSeconds)
      || durationMs < 0 || minSeconds <= 0) {
    return false;
  }

  const durationSeconds = durationMs / 1000;
  return durationSeconds >= minSeconds * 1000;
}'''
TESTS = [
    {'id': 'exact-30', 'name': 'A 30-second recording meets a 30-second minimum', 'args': [30000, 30], 'expected': True},
    {'id': 'under-30', 'name': '29.999 seconds is too short', 'args': [29999, 30], 'expected': False},
    {'id': 'above-30', 'name': 'A 45-second recording is accepted', 'args': [45000, 30], 'expected': True},
    {'id': 'short', 'name': 'A 1-second recording is rejected', 'args': [1000, 30], 'expected': False},
    {'id': 'different-minimum', 'name': 'A 10-second recording meets a 10-second minimum', 'args': [10000, 10], 'expected': True},
    {'id': 'zero', 'name': 'An empty recording is rejected', 'args': [0, 30], 'expected': False},
    {'id': 'negative', 'name': 'Negative durations are rejected', 'args': [-1000, 30], 'expected': False},
    {'id': 'invalid', 'name': 'Text is not a duration', 'args': ['30000', 30], 'expected': False},
    {'id': 'missing', 'name': 'Missing durations are rejected', 'args': [None, 30], 'expected': False},
    {'id': 'invalid-minimum', 'name': 'A non-positive minimum is rejected', 'args': [30000, 0], 'expected': False},
]
HINTS = [
    'Write down the units of durationMs, minSeconds and durationSeconds. Which two values are compared?',
    'Trace the failing input: durationMs = 30000 and minSeconds = 30. Evaluate each side of the final comparison.',
    'Both sides of the comparison must use the same unit. Keep the boundary inclusive and preserve the invalid-input checks.',
]


def scenario():
    return {'id': SCENARIO_ID, 'title': 'A 30-second recording is rejected as too short',
            'project': 'SpeakSpin example', 'language': 'JavaScript', 'starter_code': STARTER, 'tests': TESTS,
            'contract': 'validateRecording(durationMs, minSeconds) must return a boolean. Durations arrive in milliseconds; the minimum is in seconds. Accept recordings at or above the minimum. Reject invalid inputs.',
            'provenance': 'A deliberately broken, isolated recording validator inspired by SpeakSpin. It is a practice copy, not a detected defect in your live application.'}


def public_run(row):
    state = row['state']
    report = state.get('test_result')
    current = report and report.get('code_sha256') == hashlib.sha256(state['code'].encode()).hexdigest()
    tests_passed = bool(current and all(item['passed'] for item in report['results']))
    return {'id': row['id'], 'source_id': row['source_id'], 'created_at': row['created_at'].isoformat(),
            'updated_at': row['updated_at'].isoformat(), **state, 'scenario': scenario(),
            'hints': HINTS[:state.get('hints_revealed', 0)], 'total_hints': len(HINTS),
            'tests_current': bool(current), 'tests_passed': tests_passed,
            'complete': bool(tests_passed and state.get('hypothesis', '').strip() and state.get('explanation', '').strip()),
            'verification': 'Browser-executed practice tests; saved results are client observations, not a server-certified assessment.'}


def owned(conn, run_id, lock=False):
    row = conn.execute('SELECT * FROM repoviva.debug_runs WHERE id=%s AND owner=%s' + (' FOR UPDATE' if lock else ''), (run_id, g.user['id'])).fetchone()
    if not row:
        raise StudyConflict('Debugging practice not found.', 404)
    return row


@debugging.get('/challenges')
def challenges():
    return jsonify({'challenges': [scenario()]})


@debugging.route('/runs', methods=['GET', 'POST'])
def runs():
    require_storage()
    with get_database().connection() as conn:
        if request.method == 'GET':
            rows = conn.execute('SELECT * FROM repoviva.debug_runs WHERE owner=%s ORDER BY updated_at DESC,id LIMIT 20', (g.user['id'],)).fetchall()
            return jsonify({'runs': [{key: value for key, value in public_run(row).items() if key in {'id','created_at','updated_at','complete','tests_passed'}} for row in rows]})
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or data.get('scenario_id') != SCENARIO_ID:
            raise StudyConflict('Choose an available debugging challenge.', 400)
        context = None
        source_id = data.get('source_id')
        if source_id is not None:
            if not isinstance(source_id, str) or not source_id:
                raise StudyConflict('Choose a valid source file.', 400)
            source = conn.execute('SELECT document FROM repoviva.sources WHERE id=%s AND owner=%s', (source_id, g.user['id'])).fetchone()
            if not source:
                raise StudyConflict('Material not found.', 404)
            document = source['document']
            if document['kind'] != 'text':
                raise StudyConflict('Attach a source or text file for project context.', 400)
            snippets = document['snippets']
            matching = next((item for item in snippets if any(word in '\n'.join(item['content']).lower() for word in ('duration','recording','elapsed'))), snippets[0])
            context = {'filename': document['filename'], 'revision': document['revision'], 'snippet': matching}
        conn.execute('SELECT id FROM repoviva.users WHERE id=%s FOR NO KEY UPDATE', (g.user['id'],))
        if conn.execute('SELECT count(*) AS n FROM repoviva.debug_runs WHERE owner=%s', (g.user['id'],)).fetchone()['n'] >= 100:
            raise StudyConflict('You have 100 saved debugging runs. Delete an older run before starting another.', 409)
        run_id = uuid.uuid4().hex
        state = {'code': STARTER, 'hypothesis': '', 'explanation': '', 'hints_revealed': 0, 'context': context}
        row = conn.execute('INSERT INTO repoviva.debug_runs(id,owner,source_id,scenario_id,state) VALUES(%s,%s,%s,%s,%s) RETURNING *', (run_id,g.user['id'],source_id,SCENARIO_ID,Jsonb(state))).fetchone()
    return jsonify(public_run(row)), 201


@debugging.route('/runs/<run_id>', methods=['GET', 'PATCH', 'DELETE'])
def run(run_id):
    require_storage()
    request.max_content_length = 48 * 1024
    with get_database().connection() as conn:
        row = owned(conn, run_id, request.method != 'GET')
        if request.method == 'DELETE':
            conn.execute('DELETE FROM repoviva.debug_runs WHERE id=%s AND owner=%s', (run_id,g.user['id']))
            return '', 204
        if request.method == 'PATCH':
            data = request.get_json(silent=True)
            fields = {'code': 12000, 'hypothesis': 4000, 'explanation': 4000}
            if not isinstance(data, dict) or not data or set(data) - {*fields, 'test_result'}:
                raise StudyConflict('Send valid code, explanation or test results.', 400)
            state = {**row['state']}
            for key, maximum in fields.items():
                if key in data:
                    if not isinstance(data[key], str) or len(data[key]) > maximum:
                        raise StudyConflict(f'{key} must be text of at most {maximum} characters.', 400)
                    state[key] = data[key]
            if 'test_result' in data:
                report = data['test_result']
                if not isinstance(report, dict) or report.get('tested_code') != state['code'] or not isinstance(report.get('results'), list) or len(report['results']) != len(TESTS):
                    raise StudyConflict('Test results must match the current code and full test suite.', 400)
                results = []
                for item, test in zip(report['results'], TESTS):
                    if not isinstance(item, dict) or item.get('id') != test['id'] or type(item.get('passed')) is not bool or (item.get('actual') is not None and type(item['actual']) is not bool) or not isinstance(item.get('error', ''), str) or len(item.get('error', '')) > 160:
                        raise StudyConflict('Invalid test observations.', 400)
                    actual, error = item.get('actual'), item.get('error', '')
                    # Recompute verdicts from observations, never accept the posted pass flag.
                    results.append({'id': test['id'], 'actual': actual, 'error': error, 'passed': not error and actual is test['expected']})
                state['test_result'] = {'code_sha256': hashlib.sha256(state['code'].encode()).hexdigest(), 'results': results}
            row = conn.execute('UPDATE repoviva.debug_runs SET state=%s,updated_at=now() WHERE id=%s AND owner=%s RETURNING *', (Jsonb(state),run_id,g.user['id'])).fetchone()
    return jsonify(public_run(row))


@debugging.post('/runs/<run_id>/hint')
def hint(run_id):
    require_storage()
    with get_database().connection() as conn:
        row = owned(conn, run_id, True)
        state = {**row['state'], 'hints_revealed': min(3, row['state'].get('hints_revealed', 0) + 1)}
        row = conn.execute('UPDATE repoviva.debug_runs SET state=%s,updated_at=now() WHERE id=%s AND owner=%s RETURNING *', (Jsonb(state),run_id,g.user['id'])).fetchone()
    return jsonify(public_run(row))
