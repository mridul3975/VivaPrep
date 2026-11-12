"""Owned, source-derived debugging practice. Submitted code is never run by Flask."""
import hashlib
import json
import uuid
from contextlib import nullcontext
from flask import Blueprint, current_app, g, jsonify, request
from psycopg.types.json import Jsonb
from backend.database import get_database, StudyConflict
from backend.library import require_storage
from backend.account import allowance
from backend.interview.debug_generator import SOURCE_SCENARIO_ID, generate_debug_challenge, source_excerpt
from backend.interview.provider import ProviderError
from backend.interview.debug_checker import check_solution, matches_reference
from backend import example

debugging = Blueprint('debugging', __name__, url_prefix='/debug')


@debugging.errorhandler(413)
def oversized_run(error):
    return jsonify({'error': 'This debugging save is too large. Shorten the code or explanations and retry.'}), 413


def source_scenario(row):
    exercise = row['state'].get('scenario')
    if row['scenario_id'] != SOURCE_SCENARIO_ID or not isinstance(exercise, dict) or not exercise.get('source'):
        raise StudyConflict('This old sample exercise has been retired. Open Debug to create an exercise from your own source file.', 410)
    return exercise


def public_run(row):
    state = row['state']
    exercise = source_scenario(row)
    hints = state['challenge_hints']
    report = state.get('test_result')
    current = report and report.get('code_sha256') == hashlib.sha256(state['code'].encode()).hexdigest()
    tests_passed = bool(exercise['tests'] and current and all(item['passed'] for item in report['results']))
    solution = state.get('solution_result')
    solution_current = bool(solution and solution.get('code_sha256') == hashlib.sha256(state['code'].encode()).hexdigest())
    solved = tests_passed or bool(solution_current and solution['verdict'] == 'correct')
    public_state = {key: value for key, value in state.items() if key not in {'scenario', 'challenge_hints'}}
    return {'id': row['id'], 'source_id': row['source_id'], 'created_at': row['created_at'].isoformat(),
            'updated_at': row['updated_at'].isoformat(), **public_state, 'scenario': exercise,
            'hints': hints[:state.get('hints_revealed', 0)], 'total_hints': len(hints),
            'tests_current': bool(current), 'tests_passed': tests_passed,
            'solution_current': solution_current, 'solution_passed': solved,
            'complete': bool(solved and state.get('hypothesis', '').strip() and state.get('explanation', '').strip()),
            'verification': ('Browser-executed practice tests; saved results are client observations, not a server-certified assessment.'
                             if exercise.get('execution_mode', 'javascript') == 'javascript'
                             else 'Source comparison or AI code review. Runtime behavior has not been verified by this application.')}


def same_json(actual, expected):
    """JSON numbers compare numerically; booleans never equal 0 or 1."""
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return actual == expected
    if type(actual) is not type(expected):
        return False
    if isinstance(actual, list):
        return len(actual) == len(expected) and all(same_json(a, b) for a, b in zip(actual, expected))
    if isinstance(actual, dict):
        return actual.keys() == expected.keys() and all(same_json(actual[k], expected[k]) for k in actual)
    return actual == expected


def owned(conn, run_id, lock=False):
    row = conn.execute('SELECT * FROM repoviva.debug_runs WHERE id=%s AND owner=%s' + (' FOR UPDATE' if lock else ''), (run_id, g.user['id'])).fetchone()
    if not row:
        raise StudyConflict('Debugging practice not found.', 404)
    return row


@debugging.get('/challenges')
def challenges():
    return jsonify({'challenges': [], 'requires_source': True})


@debugging.route('/runs', methods=['GET', 'POST'])
def runs():
    require_storage()
    with get_database().connection() as conn:
        if request.method == 'GET':
            rows = conn.execute('SELECT * FROM repoviva.debug_runs WHERE owner=%s AND scenario_id=%s ORDER BY updated_at DESC,id LIMIT 20', (g.user['id'], SOURCE_SCENARIO_ID)).fetchall()
            return jsonify({'runs': [{**{key: value for key, value in public_run(row).items() if key in {'id','created_at','updated_at','complete','tests_passed','solution_passed'}}, 'title': row['state']['scenario']['title'], 'filename': row['state']['scenario']['project']} for row in rows]})
    data = request.get_json(silent=True)
    source_id = data.get('source_id') if isinstance(data, dict) else None
    if not isinstance(source_id, str) or not source_id.strip():
        raise StudyConflict('Upload or select your project source file before starting Debug.', 400)
    with get_database().connection() as conn:
        source = conn.execute('SELECT document FROM repoviva.sources WHERE id=%s AND owner=%s', (source_id, g.user['id'])).fetchone()
        if not source:
            raise StudyConflict('Material not found.', 404)
        document = source['document']
        if example.is_example(document):
            previous = conn.execute('SELECT * FROM repoviva.debug_runs WHERE owner=%s AND source_id=%s AND scenario_id=%s ORDER BY created_at DESC LIMIT 1', (g.user['id'],source_id,SOURCE_SCENARIO_ID)).fetchone()
            if previous:
                return jsonify(public_run(previous)), 200
    try:
        source_excerpt(document, data.get('snippet_id'))
    except ValueError as error:
        raise StudyConflict(str(error), 400) from error
    try:
        with nullcontext() if example.is_example(document) else allowance('questions'):
            exercise = example.challenge(document) if example.is_example(document) else generate_debug_challenge(document, data.get('snippet_id'))
            hints = exercise.pop('_hints')
            with get_database().connection() as conn:
                conn.execute('SELECT id FROM repoviva.users WHERE id=%s FOR NO KEY UPDATE', (g.user['id'],))
                if not conn.execute('SELECT id FROM repoviva.sources WHERE id=%s AND owner=%s', (source_id, g.user['id'])).fetchone():
                    raise StudyConflict('Material was deleted while the challenge was being generated. Upload it again.', 404)
                if conn.execute('SELECT count(*) AS n FROM repoviva.debug_runs WHERE owner=%s AND scenario_id=%s', (g.user['id'], SOURCE_SCENARIO_ID)).fetchone()['n'] >= 100:
                    raise StudyConflict('You have 100 saved debugging runs. Delete an older run before starting another.', 409)
                run_id = uuid.uuid4().hex
                state = {'code': exercise['starter_code'], 'hypothesis': '', 'explanation': '', 'hints_revealed': 0, 'scenario': exercise, 'challenge_hints': hints}
                row = conn.execute('INSERT INTO repoviva.debug_runs(id,owner,source_id,scenario_id,state) VALUES(%s,%s,%s,%s,%s) RETURNING *', (run_id,g.user['id'],source_id,SOURCE_SCENARIO_ID,Jsonb(state))).fetchone()
    except (ProviderError, ValueError, KeyError, TypeError) as error:
        current_app.logger.warning('Project debugging generation failed: %s', type(error).__name__)
        if isinstance(error, ProviderError) and error.status_code == 429:
            return jsonify({'error': 'The AI provider is temporarily rate limited. Wait a moment and retry.'}), 503
        return jsonify({'error': 'Could not create a source-matched debugging exercise. Choose a section with a complete function and retry. No sample exercise was substituted.'}), 502
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
        source_scenario(row)
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
                tests = state['scenario']['tests']
                if not tests or not isinstance(report, dict) or report.get('tested_code') != state['code'] or not isinstance(report.get('results'), list) or len(report['results']) != len(tests):
                    raise StudyConflict('Test results must match the current code and full test suite.', 400)
                results = []
                for item, test in zip(report['results'], tests):
                    try:
                        actual_size = len(json.dumps(item.get('actual'), allow_nan=False)) if isinstance(item, dict) else 4001
                    except (ValueError, TypeError):
                        raise StudyConflict('Test observations must contain finite JSON values.', 400)
                    if not isinstance(item, dict) or 'actual' not in item or item.get('id') != test['id'] or type(item.get('passed')) is not bool or not isinstance(item.get('error', ''), str) or len(item.get('error', '')) > 160 or actual_size > 4000:
                        raise StudyConflict('Invalid test observations.', 400)
                    actual, error = item.get('actual'), item.get('error', '')
                    # Recompute verdicts from observations, never accept the posted pass flag.
                    results.append({'id': test['id'], 'actual': actual, 'error': error, 'passed': not error and same_json(actual, test['expected'])})
                state['test_result'] = {'code_sha256': hashlib.sha256(state['code'].encode()).hexdigest(), 'results': results}
            row = conn.execute('UPDATE repoviva.debug_runs SET state=%s,updated_at=now() WHERE id=%s AND owner=%s RETURNING *', (Jsonb(state),run_id,g.user['id'])).fetchone()
    return jsonify(public_run(row))


@debugging.post('/runs/<run_id>/check')
def check(run_id):
    require_storage()
    request.max_content_length = 96 * 1024
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {'code'} or not isinstance(data['code'], str) or not data['code'].strip() or len(data['code']) > 12000:
        raise StudyConflict('Send a non-empty solution of at most 12000 characters.', 400)
    code = data['code']
    fingerprint = hashlib.sha256(code.encode()).hexdigest()
    with get_database().connection() as conn:
        row = owned(conn, run_id)
        exercise = source_scenario(row)
        if row['state']['code'] != code:
            raise StudyConflict('Your code changed. Save it and check again.', 409)
        previous = row['state'].get('solution_result')
        if previous and previous.get('code_sha256') == fingerprint:
            return jsonify(public_run(row))
    direct = matches_reference(code, exercise['reference_code'], exercise['language']) or code.replace('\r\n', '\n').strip('\n') == exercise['starter_code'].replace('\r\n', '\n').strip('\n')
    try:
        # Release the database connection during the provider call. Direct comparisons are free.
        with nullcontext() if direct else allowance('answers'):
            result = check_solution(code, exercise)
            with get_database().connection() as conn:
                row = owned(conn, run_id, True)
                if row['state']['code'] != code:
                    raise StudyConflict('Your code changed during the check. Check the latest version again.', 409)
                state = {**row['state'], 'solution_result': {**result, 'code_sha256': fingerprint}}
                row = conn.execute('UPDATE repoviva.debug_runs SET state=%s,updated_at=now() WHERE id=%s AND owner=%s RETURNING *', (Jsonb(state), run_id, g.user['id'])).fetchone()
    except (ProviderError, ValueError, KeyError, TypeError) as error:
        current_app.logger.warning('Debug solution review failed: %s', type(error).__name__)
        return jsonify({'error': 'Solution review is temporarily unavailable. Your code is saved; retry shortly. No score was assigned.'}), 503 if isinstance(error, ProviderError) and error.status_code == 429 else 502
    return jsonify(public_run(row))


@debugging.post('/runs/<run_id>/hint')
def hint(run_id):
    require_storage()
    with get_database().connection() as conn:
        row = owned(conn, run_id, True)
        source_scenario(row)
        state = {**row['state'], 'hints_revealed': min(len(row['state']['challenge_hints']), row['state'].get('hints_revealed', 0) + 1)}
        row = conn.execute('UPDATE repoviva.debug_runs SET state=%s,updated_at=now() WHERE id=%s AND owner=%s RETURNING *', (Jsonb(state),run_id,g.user['id'])).fetchone()
    return jsonify(public_run(row))
