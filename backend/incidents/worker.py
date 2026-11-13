"""Trusted harness, executed INSIDE the remote VM, never on the Flask host."""
import concurrent.futures
import hashlib
import http.client
import json
import os
from pathlib import Path
import resource
import signal
import sqlite3
import subprocess
import sys
import threading
import time


def restrict_child():
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024 * 1024, 2 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (96, 96))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    os.setgroups([]); os.setgid(65534); os.setuid(65534)


def snapshot(folder, scenario):
    result = {}
    if not scenario['database']:
        return result
    database = folder / scenario['database']
    for table in scenario['tables']:
        try:
            # Never create the database as a side effect of observation.
            with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=.5) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute('SELECT * FROM "' + table + '" LIMIT 51').fetchall()
                truncated = len(rows) > 50
                bounded = []
                for row in rows[:50]:
                    values = {}
                    for key, value in dict(row).items():
                        if isinstance(value, bytes):
                            value, truncated = {'binary_bytes': len(value)}, True
                        elif isinstance(value, str) and len(value) > 800:
                            value, truncated = value[:800], True
                        values[key] = value
                    bounded.append(values)
                result[table] = {'count': len(rows), 'rows': bounded, 'truncated': truncated}
        except sqlite3.Error:
            result[table] = {'error': 'Table is unavailable in this snapshot', 'rows': []}
    return result


def request(port, spec, barrier=None):
    if barrier:
        barrier.wait(timeout=3)
    start = time.monotonic()
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        body = None if spec['body'] is None else json.dumps(spec['body'])
        connection.request(spec['method'], spec['path'], body, {'Content-Type': 'application/json'})
        response = connection.getresponse()
        text = response.read(4097).decode('utf-8', errors='replace')
        return {'method': spec['method'], 'path': spec['path'], 'body': spec['body'], 'status': response.status, 'response': text[:4096], 'truncated': len(text) > 4096, 'milliseconds': round((time.monotonic() - start) * 1000)}
    except (OSError, http.client.HTTPException) as error:
        return {'method': spec['method'], 'path': spec['path'], 'body': spec['body'], 'status': 0, 'response': '', 'error': type(error).__name__, 'milliseconds': round((time.monotonic() - start) * 1000)}
    finally:
        connection.close()


def run(payload):
    files, scenario = payload['files'], payload['scenario']
    result = {'kind': 'execution', 'files_sha256': hashlib.sha256(json.dumps(files, sort_keys=True, ensure_ascii=False).encode()).hexdigest(), 'experiments': []}
    for index, test in enumerate(payload['experiments']):
        folder = Path('/work') / ('case-' + str(index))
        folder.mkdir(mode=0o755)
        os.chown(folder, 65534, 65534)
        for name, text in files.items():
            path = folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            path.chmod(0o644)
            for parent in [path, *path.parents]:
                if parent == Path('/work'):
                    break
                os.chown(parent, 65534, 65534)
        log_file = Path('/work') / ('app-' + str(index) + '.log')
        row = {'name': test['name'], 'concurrent': test['concurrent']}
        with log_file.open('w+') as log:
            process = subprocess.Popen([sys.executable, '/runner/launch.py', scenario['entrypoint']], cwd=folder, env={'PATH': '/usr/local/bin:/usr/bin:/bin', 'PORT': str(scenario['port']), 'HOME': str(folder), 'PYTHONUNBUFFERED': '1'}, stdout=log, stderr=log, start_new_session=True, preexec_fn=restrict_child)
            try:
                ready = False
                for _ in range(40):
                    probe = request(scenario['port'], {'method': 'GET', 'path': '/health', 'body': None})
                    if probe['status']:
                        ready = True
                        break
                    if process.poll() is not None:
                        break
                    time.sleep(.1)
                row['database_before'] = snapshot(folder, scenario)
                if not ready:
                    row['error'] = 'Application did not start. Check the Python entrypoint, port and sandbox template dependencies.'
                    row['responses'] = [dict(request, status=0, response='', error='Application unavailable') for request in test['requests']]
                elif test['concurrent']:
                    barrier = threading.Barrier(len(test['requests']))
                    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                        row['responses'] = list(pool.map(lambda spec: request(scenario['port'], spec, barrier), test['requests']))
                else:
                    row['responses'] = [request(scenario['port'], spec) for spec in test['requests']]
                row['database_after'] = snapshot(folder, scenario)
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=3)
            log.seek(0)
            text = log.read(30000)
            traces, messages = [], []
            for line in text.splitlines():
                if line.startswith('RVTRACE:'):
                    try:
                        point = json.loads(line[8:])
                        if point['path'] in files and type(point['line']) is int and 1 <= point['line'] <= len(files[point['path']].splitlines()):
                            traces.append(point)
                    except (ValueError, KeyError, TypeError):
                        pass
                else:
                    messages.append(line)
            row['trace'] = traces[:180]
            row['logs'] = '\n'.join(messages)[:6000]
        result['experiments'].append(row)
    return result


if __name__ == '__main__':
    payload = json.loads(Path('/runner/input.json').read_text())
    Path('/runner/output.json').write_text(json.dumps(run(payload), ensure_ascii=False))
