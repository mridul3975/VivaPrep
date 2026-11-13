"""Owned incident projects, reviewed experiment plans and bounded remote jobs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
import os
import uuid
from flask import Blueprint, current_app, g, jsonify, request
from psycopg.types.json import Jsonb
from backend.account import allowance
from backend.database import get_database, StudyConflict
from backend.library import require_storage
from backend.incidents import demo, runtime
from backend.incidents.bundle import read_project, validate_files
from backend.incidents.contracts import digest, validate_scenario
from backend.incidents.intelligence import generate_incident, investigation
from backend.interview.provider import ProviderError

incidents = Blueprint('incidents', __name__, url_prefix='/incidents')
executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='incident')
log = logging.getLogger(__name__)


def limit(name, default):
    try:
        return max(0, min(1000, int(os.getenv(name, str(default)))))
    except ValueError:
        return default


def usage(conn, owner):
    day = datetime.now(timezone.utc).date()
    maximum = limit('GUEST_INCIDENT_LIMIT', 3) if owner.startswith('guest:') else limit('DAILY_INCIDENT_LIMIT', 10)
    used = conn.execute('SELECT count(*) AS n FROM repoviva.incident_usage WHERE owner=%s AND period=%s', (owner, day)).fetchone()['n']
    return {'used': used, 'limit': maximum, 'remaining': max(0, maximum-used), 'reset_timezone': 'UTC'}


def reserve(conn, owner):
    # Cross-thread/process atomic admission and shared provider-spend ceiling.
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('repoviva_incident_admission'))")
    day = datetime.now(timezone.utc).date()
    quota = usage(conn, owner)
    total = conn.execute('SELECT count(*) AS n FROM repoviva.incident_usage WHERE period=%s', (day,)).fetchone()['n']
    if not quota['remaining']:
        raise StudyConflict('Your incident-run allowance is used up for today. Saved work is still available.', 429)
    if total >= limit('SHARED_INCIDENT_LIMIT', 30):
        raise StudyConflict('The shared incident-run allowance is used up for today. Please try tomorrow.', 429)
    active = conn.execute('SELECT owner FROM repoviva.incident_labs WHERE busy_until>now()').fetchall()
    if any(row['owner'] == owner for row in active) or len(active) >= 2:
        raise StudyConflict('An isolated experiment is already running. Wait for it to finish, then retry.', 409)
    token = uuid.uuid4().hex
    conn.execute('INSERT INTO repoviva.incident_usage(id,owner,period) VALUES(%s,%s,%s)', (token,owner,day))
    return token


def owned(conn, lab_id, owner=None, lock=False):
    row = conn.execute('SELECT * FROM repoviva.incident_labs WHERE id=%s AND owner=%s' + (' FOR UPDATE' if lock else ''), (lab_id,owner or g.user['id'])).fetchone()
    if not row:
        raise StudyConflict('Incident project not found.', 404)
    return row


def public(row):
    state = row['state']
    latest = state.get('latest')
    current = bool(latest and latest.get('code_sha256') == digest(state['files']))
    return {'id': row['id'], 'title': row['title'], 'updated_at': row['updated_at'].isoformat(), **state,
            'current_execution': current, 'solved': bool(current and latest.get('scope') == 'repair' and latest.get('passed') is True)}


def ready(row):
    if row['busy_until'] and row['busy_until'] > datetime.now(timezone.utc):
        raise StudyConflict('Wait for the current sandbox job to finish.', 409)
    if not row['state'].get('scenario'):
        raise StudyConflict('This project has no validated incident yet. Start another project or retry its setup.', 409)


def submit(app, lab_id, owner, token, prepare=False, experiments=None, scope=None):
    def work():
        with app.app_context():
            try:
                with get_database().connection() as conn:
                    row = conn.execute('SELECT * FROM repoviva.incident_labs WHERE id=%s AND lease_token=%s',(lab_id,token)).fetchone()
                    if not row:
                        return
                state = row['state']
                if prepare:
                    scenario = demo.scenario() if state['prepared'] else generate_incident(state['original_files'])
                    broken = validate_scenario(scenario, state['original_files'])
                    reference = runtime.execute(state['original_files'], scenario, [scenario['reproduction'], *scenario['regressions']])
                    if reference['passed'] is not True:
                        raise ValueError('The original project did not pass its proposed checks. No controlled incident was certified.')
                    failure = runtime.execute(broken, scenario, [scenario['reproduction']])
                    if failure['passed'] is not False or any(r.get('error') or any(response.get('status', 0) == 0 for response in r['responses']) for r in failure['experiments']):
                        raise ValueError('The proposed failure could not be reproduced in the running app.')
                    state.update(files=broken, scenario=scenario, baseline=reference, broken_evidence=failure, status='ready', error='')
                    title = scenario['title']
                else:
                    evidence = runtime.execute(state['files'], state['scenario'], experiments)
                    evidence.update(code_sha256=digest(state['files']), scope=scope, id=uuid.uuid4().hex)
                    state.update(latest=evidence, status='ready', error='')
                    state['executions'] = [*state.get('executions', []), evidence][-6:]
                    title = row['title']
                with get_database().connection() as conn:
                    conn.execute('UPDATE repoviva.incident_labs SET state=%s,title=%s,lease_token=NULL,busy_until=NULL,updated_at=now() WHERE id=%s AND lease_token=%s', (Jsonb(state),title,lab_id,token))
            except Exception as error:
                log.warning('Incident job failed: %s', type(error).__name__)
                message = (str(error) if isinstance(error, runtime.RuntimeUnavailable) else
                    'The AI provider is rate limited. Your project is saved; retry shortly.' if isinstance(error, ProviderError) and error.status_code == 429 else
                    'Could not validate a reproducible incident for this project. Check its entrypoint, local data and dependencies. No test result or replacement project was invented.' if prepare else
                    'The experiment could not finish. Your code and previous execution evidence are saved. Retry when the isolated runner is available.')
                with get_database().connection() as conn:
                    conn.execute("UPDATE repoviva.incident_labs SET state=jsonb_set(jsonb_set(state,'{status}',%s),'{error}',%s),lease_token=NULL,busy_until=NULL,updated_at=now() WHERE id=%s AND lease_token=%s", (Jsonb('error' if prepare else 'ready'),Jsonb(message),lab_id,token))
                    # Refund the personal allowance without erasing the shared
                    # provider-attempt ledger; failed jobs can still consume VM credits.
                    conn.execute('UPDATE repoviva.incident_usage SET owner=NULL WHERE id=%s', (token,))
    try:
        executor.submit(work)
    except RuntimeError as error:
        with get_database().connection() as conn:
            conn.execute('UPDATE repoviva.incident_labs SET lease_token=NULL,busy_until=NULL WHERE id=%s AND owner=%s AND lease_token=%s', (lab_id,owner,token))
            conn.execute('DELETE FROM repoviva.incident_usage WHERE id=%s AND owner=%s', (token,owner))
        raise StudyConflict('The incident worker is restarting. Retry shortly.', 503) from error


@incidents.route('', methods=['GET', 'POST'])
def projects():
    require_storage()
    owner = g.user['id']
    if request.method == 'GET':
        with get_database().connection() as conn:
            rows = conn.execute('SELECT id,title,updated_at,state->>\'status\' AS status FROM repoviva.incident_labs WHERE owner=%s ORDER BY updated_at DESC LIMIT 30', (owner,)).fetchall()
            return jsonify({'labs': [{**r, 'updated_at': r['updated_at'].isoformat()} for r in rows], 'runner_available': runtime.available(), 'usage': usage(conn, owner)})
    if not runtime.available():
        raise StudyConflict('Running incidents is not enabled on this server yet. Your other code practice remains available.', 503)
    request.max_content_length = 1100 * 1024
    data = request.get_json(silent=True) if request.is_json else None
    prepared = isinstance(data, dict) and data.get('example') is True
    try:
        if prepared:
            files = demo.project()
        elif isinstance(data, dict) and isinstance(data.get('source_id'), str):
            with get_database().connection() as conn:
                source = conn.execute('SELECT document FROM repoviva.sources WHERE id=%s AND owner=%s', (data['source_id'],owner)).fetchone()
            if not source:
                raise StudyConflict('Uploaded source not found.', 404)
            document = source['document']
            if document.get('kind') != 'text' or not document['filename'].endswith('.py'):
                raise ValueError('Choose a runnable Python HTTP app or upload a project ZIP.')
            files = validate_files({document['filename']: '\n'.join(line for snippet in document['snippets'] for line in snippet['content'])})
        else:
            upload = request.files.get('project_file')
            if not upload or not upload.filename:
                raise ValueError('Upload a Python HTTP app or project ZIP.')
            try:
                files = read_project(upload.read(1024 * 1024 + 1), upload.filename)
            finally:
                upload.close()
    except ValueError as error:
        raise StudyConflict(str(error), 400) from error
    lab_id = uuid.uuid4().hex
    state = {'status': 'preparing', 'prepared': prepared, 'files': files, 'original_files': files, 'conversation': [], 'executions': [], 'error': ''}
    with get_database().connection() as conn:
        token = reserve(conn, owner)
        if conn.execute('SELECT count(*) AS n FROM repoviva.incident_labs WHERE owner=%s', (owner,)).fetchone()['n'] >= 30:
            raise StudyConflict('Delete an older incident project before starting another.', 409)
        row = conn.execute("INSERT INTO repoviva.incident_labs(id,owner,title,state,lease_token,busy_until) VALUES(%s,%s,%s,%s,%s,now()+interval '180 seconds') RETURNING *", (lab_id,owner,'Preparing booking incident' if prepared else 'Preparing uploaded project',Jsonb(state),token)).fetchone()
    submit(current_app._get_current_object(), lab_id, owner, token, prepare=True)
    return jsonify(public(row)), 202


@incidents.route('/<lab_id>', methods=['GET', 'PATCH', 'DELETE'])
def project(lab_id):
    require_storage()
    request.max_content_length = 300 * 1024
    with get_database().connection() as conn:
        row = owned(conn, lab_id, lock=True)
        if row['busy_until'] and row['busy_until'] <= datetime.now(timezone.utc):
            state = {**row['state'], 'status': 'ready' if row['state'].get('scenario') else 'error', 'error': 'Execution was interrupted. Your saved work remains; retry the experiment.'}
            row = conn.execute('UPDATE repoviva.incident_labs SET state=%s,busy_until=NULL,lease_token=NULL WHERE id=%s RETURNING *', (Jsonb(state),lab_id)).fetchone()
        if request.method == 'GET':
            return jsonify(public(row))
        if request.method == 'DELETE':
            if row['busy_until'] and row['busy_until'] > datetime.now(timezone.utc):
                raise StudyConflict('Wait for the active sandbox job before deleting this incident.',409)
            conn.execute('DELETE FROM repoviva.incident_labs WHERE id=%s AND owner=%s', (lab_id,g.user['id']))
            return '', 204
        ready(row)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or 'files' not in data or set(data) - {'files','instruction_draft'} or not isinstance(data['files'], dict) or set(data['files']) != set(row['state']['files']):
            raise StudyConflict('Save the existing project files; file paths cannot be added or removed in a patch.', 400)
        instruction = data.get('instruction_draft', row['state'].get('instruction_draft'))
        if instruction is not None and (not isinstance(instruction,dict) or set(instruction) != {'text','original','reviewed'} or not isinstance(instruction['text'],str) or len(instruction['text'])>4000 or (instruction['original'] is not None and (not isinstance(instruction['original'],str) or len(instruction['original'])>4000)) or type(instruction['reviewed']) is not bool):
            raise StudyConflict('Invalid investigation draft.',400)
        try:
            validate_files(data['files'])
        except ValueError as error:
            raise StudyConflict(str(error),400) from error
        state = {**row['state'], 'files': data['files'], 'instruction_draft': instruction, 'plan': None}
        row = conn.execute('UPDATE repoviva.incident_labs SET state=%s,updated_at=now() WHERE id=%s AND owner=%s RETURNING *', (Jsonb(state),lab_id,g.user['id'])).fetchone()
        return jsonify(public(row))


@incidents.post('/<lab_id>/plan')
def plan(lab_id):
    require_storage()
    request.max_content_length = 16 * 1024
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('instruction'), str) or not 1 <= len(data['instruction'].strip()) <= 4000:
        raise StudyConflict('Write or record an investigation instruction.',400)
    if data.get('original_transcript') is not None and (not isinstance(data['original_transcript'],str) or len(data['original_transcript']) > 4000 or data.get('reviewed') is not True):
        raise StudyConflict('Review and confirm the transcript before planning an experiment.',400)
    with get_database().connection() as conn:
        row = owned(conn,lab_id); ready(row)
    state, version = row['state'], digest(row['state']['files'])
    deterministic = data['instruction'].casefold().strip().rstrip('.!') in {'test my fix','test the fix','test fix','meri fix test karo','repeat the request','replay the incident','repeat','dobara run karo','show the failing trace','show trace','show the trace','trace dikhao'}
    from contextlib import nullcontext
    try:
        with nullcontext() if deterministic else allowance('answers'):
            proposal = investigation(data['instruction'],state)
            proposal.update(id=uuid.uuid4().hex, code_sha256=version, instruction=data['instruction'], original_transcript=data.get('original_transcript'), reviewed=data.get('reviewed', False))
            with get_database().connection() as conn:
                current = owned(conn,lab_id,lock=True); ready(current)
                if digest(current['state']['files']) != version:
                    raise StudyConflict('The code changed while this plan was prepared. Review a new plan.',409)
                state = {**current['state'], 'plan': proposal, 'conversation': [*current['state'].get('conversation',[]),proposal][-16:]}
                row = conn.execute('UPDATE repoviva.incident_labs SET state=%s,updated_at=now() WHERE id=%s AND owner=%s RETURNING *', (Jsonb(state),lab_id,g.user['id'])).fetchone()
    except (ProviderError, ValueError, TypeError, KeyError) as error:
        log.warning('Incident planning failed: %s',type(error).__name__)
        raise StudyConflict('Could not prepare a source-grounded experiment. Your code and previous evidence are saved; retry or use Replay incident.',503 if isinstance(error,ProviderError) and error.status_code==429 else 502) from error
    return jsonify(public(row))


@incidents.post('/<lab_id>/execute')
def execute(lab_id):
    require_storage()
    data = request.get_json(silent=True)
    with get_database().connection() as conn:
        row = owned(conn,lab_id,lock=True); ready(row)
        state = row['state']; proposal = state.get('plan')
        if not isinstance(data,dict) or not proposal or data.get('plan_id') != proposal['id'] or proposal['code_sha256'] != digest(state['files']):
            raise StudyConflict('Review a plan for the current code before running it.',409)
        action, scenario = proposal['action'], state['scenario']
        if action not in {'replay','test_fix','experiment'}:
            raise StudyConflict('This response does not request an experiment.',400)
        if not runtime.available():
            raise StudyConflict('The isolated runner is unavailable. Your patch and earlier evidence are saved.',503)
        token = reserve(conn,g.user['id'])
        tests = [scenario['reproduction'], *scenario['regressions']] if action == 'test_fix' else [scenario['reproduction']] if action=='replay' else [proposal['experiment']]
        state = {**state,'status':'running','error':''}
        row = conn.execute("UPDATE repoviva.incident_labs SET state=%s,lease_token=%s,busy_until=now()+interval '90 seconds',updated_at=now() WHERE id=%s AND owner=%s RETURNING *",(Jsonb(state),token,lab_id,g.user['id'])).fetchone()
    submit(current_app._get_current_object(),lab_id,g.user['id'],token,experiments=tests,scope='repair' if action=='test_fix' else 'incident' if action=='replay' else 'experiment')
    return jsonify(public(row)),202
