"""Bounded experiment descriptions. No model-generated shell or external URL is accepted."""
import ast
import hashlib
import json
import re
from backend.incidents.bundle import safe_path, validate_files


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def experiment(value, tables, *, expectations=True):
    if not isinstance(value, dict) or not isinstance(value.get('name'), str) or not 1 <= len(value['name']) <= 160 or type(value.get('concurrent')) is not bool:
        raise ValueError('Experiment needs a name and an explicit concurrency choice.')
    requests = value.get('requests')
    if not isinstance(requests, list) or not 1 <= len(requests) <= 4:
        raise ValueError('An experiment can send one to four local requests.')
    for request in requests:
        if not isinstance(request, dict) or set(request) != {'method', 'path', 'body'} or request['method'] not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}:
            raise ValueError('Invalid experiment request.')
        path = request['path']
        if not isinstance(path, str) or not path.startswith('/') or path.startswith('//') or any(c in path for c in ('\\', '\r', '\n', '#')) or len(path) > 250:
            raise ValueError('Experiments can address only paths in this sandbox application.')
        if len(json.dumps(request['body'], allow_nan=False)) > 2000:
            raise ValueError('Experiment request body is too large.')
    if expectations:
        statuses = value.get('expected_statuses')
        checks = value.get('db_checks')
        if not isinstance(statuses, list) or len(statuses) != len(requests) or any(type(s) is not int or not 100 <= s <= 599 for s in statuses):
            raise ValueError('Each test request needs a source-grounded expected status.')
        if not isinstance(checks, list) or len(checks) > 8:
            raise ValueError('Invalid database checks.')
        for check in checks:
            if not isinstance(check, dict) or set(check) != {'table', 'column', 'expected'} or check['table'] not in tables or not re.fullmatch(r'[A-Za-z_]\w{0,49}', check['column']) or len(json.dumps(check['expected'], allow_nan=False)) > 1500:
                raise ValueError('Database checks must reference the declared tables and columns.')
    return value


def validate_scenario(value, files):
    validate_files(files)
    if not isinstance(value, dict) or not isinstance(value.get('title'), str) or not 1 <= len(value['title']) <= 180 or not isinstance(value.get('description'), str) or not 1 <= len(value['description']) <= 1800:
        raise ValueError('The incident needs a clear symptom and expected behavior.')
    if value.get('entrypoint') not in files or not value['entrypoint'].endswith('.py') or type(value.get('port')) is not int or not 1024 <= value['port'] <= 65535:
        raise ValueError('Choose a real Python entrypoint and a port from 1024 to 65535.')
    database, tables = value.get('database'), value.get('tables')
    if not isinstance(database, str) or (database and not safe_path(database).endswith(('.db', '.sqlite', '.sqlite3'))):
        raise ValueError('Only a sandbox-local SQLite database is supported.')
    if not isinstance(tables, list) or len(tables) > 5 or any(not isinstance(t, str) or not re.fullmatch(r'[A-Za-z_]\w{0,49}', t) for t in tables) or (tables and not database):
        raise ValueError('Declare at most five SQLite tables.')
    mutation = value.get('mutation')
    if not isinstance(mutation, dict) or set(mutation) != {'path', 'before', 'after'} or mutation['path'] not in files or not mutation['path'].endswith('.py'):
        raise ValueError('The controlled change must reference an uploaded Python file.')
    before, after = mutation['before'], mutation['after']
    # Models see line-numbered excerpts with LF. Preserve the upload's CRLF bytes
    # when applying that same exact multi-line block; no code content is rewritten.
    source = files[mutation['path']]
    if '\r\n' in source and source.count('\n') == source.count('\r\n') and isinstance(before,str) and isinstance(after,str):
        before = before.replace('\r\n','\n').replace('\n','\r\n')
        after = after.replace('\r\n','\n').replace('\n','\r\n')
        mutation['before'], mutation['after'] = before, after
    if not all(isinstance(s, str) and 0 < len(s) <= 4000 for s in (before, after)) or before == after or files[mutation['path']].count(before) != 1:
        raise ValueError('The controlled change must replace one unique exact source block.')
    broken = {**files, mutation['path']: files[mutation['path']].replace(before, after, 1)}
    validate_files(broken)
    ast.parse(files[mutation['path']]); ast.parse(broken[mutation['path']])
    experiment(value.get('reproduction'), tables)
    regressions = value.get('regressions')
    if not isinstance(regressions, list) or not 1 <= len(regressions) <= 3:
        raise ValueError('Provide one to three regression checks.')
    for test in regressions:
        experiment(test, tables)
    return broken


def validate_observations(result, files, tests):
    if not isinstance(result, dict) or result.get('kind') != 'execution' or result.get('files_sha256') != digest(files):
        raise ValueError('Execution did not match the submitted project snapshot.')
    rows = result.get('experiments')
    if not isinstance(rows, list) or len(rows) != len(tests):
        raise ValueError('Execution returned an incomplete experiment set.')
    # The host recomputes pass/fail from actual observations, never from a submitted score.
    for row, test in zip(rows, tests):
        if not isinstance(row, dict) or row.get('name') != test['name'] or not isinstance(row.get('responses'), list) or len(row['responses']) != len(test['requests']):
            raise ValueError('Execution returned incomplete HTTP observations.')
        for response, spec in zip(row['responses'], test['requests']):
            if response.get('method') != spec['method'] or response.get('path') != spec['path'] or type(response.get('status')) is not int or not 0 <= response['status'] <= 599:
                raise ValueError('Execution returned invalid request observations.')
        traces = []
        for point in row.get('trace', [])[:180]:
            if isinstance(point, dict) and point.get('path') in files and type(point.get('line')) is int and 1 <= point['line'] <= len(files[point['path']].splitlines()):
                traces.append({**point, 'source': files[point['path']].splitlines()[point['line'] - 1]})
        row['trace'] = traces
        row['passed'] = bool(not row.get('error') and sorted(r.get('status', 0) for r in row['responses']) == sorted(test.get('expected_statuses', []))) if 'expected_statuses' in test else None
        checks = []
        for check in test.get('db_checks', []):
            snapshot = row.get('database_after', {}).get(check['table'], {})
            actual = snapshot.get('count') if check['column'] == '_count' else [r.get(check['column']) for r in snapshot.get('rows', [])]
            equal = json.dumps(actual, sort_keys=True) == json.dumps(check['expected'], sort_keys=True)
            passed = not snapshot.get('error') and not snapshot.get('truncated') and equal
            checks.append({**check, 'actual': actual, 'passed': bool(passed)})
            if row['passed'] is not None:
                row['passed'] = row['passed'] and bool(passed)
        row['checks'] = checks
    result['passed'] = all(row['passed'] is True for row in rows) if all('expected_statuses' in t for t in tests) else None
    result['observation_notice'] = 'Actual sandbox HTTP, SQLite and line-trace observations; finite checks are not proof over every input.'
    return result
