"""Opt-in live evaluation. No production records or private learner material are used."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import wave
from datetime import datetime, timezone
from unittest.mock import patch

from dotenv import load_dotenv
from backend.interview import provider
from backend.interview.grading import grade_answer
from backend.interview.debug_checker import check_solution
from backend.speech.transcriber import transcribe_wav
from backend.speech.review import suggested_checks
from evaluation.metrics import assessment_outcome, word_errors

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / 'evaluation'
FILES = ['evaluation/dataset.json', 'evaluation/baseline.json', 'evaluation/run.py', 'evaluation/metrics.py',
         'evaluation/run-repairs.cjs', 'backend/app.py', 'backend/database.py', 'backend/library.py', 'backend/account.py',
         'backend/auth.py', 'backend/interview/grading.py', 'backend/interview/debug_checker.py',
         'backend/interview/provider.py', 'backend/languages.py', 'backend/speech/review.py',
         'backend/speech/transcriber.py', 'frontend/src/debug/runner.ts']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def package(dataset, source_id, language='en'):
    source = dataset['sources'][source_id]
    lines = source['code'].splitlines()
    snippet = {'id': source_id + ':1', 'path': source['path'], 'start_line': 1, 'end_line': len(lines), 'content': lines}
    rubric = [{**item, 'snippet_id': snippet['id'], 'quote': '\n'.join(lines[item['line_start'] - 1:item['line_end']])} for item in source['rubric']]
    return {'question': source['question'], 'reference_answer': source['reference_answer'], 'rubric': rubric, 'language': language}, [snippet]


def baseline_assessment(spec, question, answer, snippets):
    statuses = ['met', 'partial', 'missed', 'contradicted', 'unverified']
    schema = provider.object_schema({'summary': {'type': 'string'}, 'criteria': {'type': 'array', 'items': provider.object_schema({
        'id': {'type': 'string', 'enum': [r['id'] for r in question['rubric']]}, 'status': {'type': 'string', 'enum': statuses}, 'explanation': {'type': 'string'}})},
        'claims': {'type': 'array', 'items': provider.object_schema({'claim': {'type': 'string'}, 'label': {'type': 'string', 'enum': ['supported', 'contradicted', 'unverified']},
        'explanation': {'type': 'string'}, **provider.citation_properties(snippets, nullable=True)})}})
    prompt = spec['assessment'] + '\n' + json.dumps({'question': question, 'student_answer': answer, 'source': provider.source_packet(snippets)}, ensure_ascii=False)
    return provider.json_completion(spec['system'], prompt, schema, 'baseline_assessment')


def baseline_repair(spec, code, exercise):
    schema = provider.object_schema({'verdict': {'type': 'string', 'enum': ['correct', 'incorrect', 'uncertain']}, 'explanation': {'type': 'string'}})
    # No expected verdict or test output is supplied to either reviewer.
    prompt = spec['repair'] + '\n' + json.dumps({'language': exercise['language'], 'contract': exercise['contract'],
        'reference': exercise['reference_code'], 'broken': exercise['starter_code'], 'student_solution': code})
    return provider.json_completion(spec['system'], prompt, schema, 'baseline_repair')


class RecordedCalls:
    def __init__(self, minimum_gap):
        self.minimum_gap = minimum_gap
        self.last_started = 0
        self.calls = []
        self.original = provider.json_completion

    def __call__(self, system, prompt, schema, name, timeout=45):
        time.sleep(max(0, self.minimum_gap - (time.monotonic() - self.last_started)))
        self.last_started = time.monotonic()
        row = {'system': system, 'prompt': prompt, 'schema': schema, 'response_name': name}
        self.calls.append(row)
        started = time.monotonic()
        try:
            response = self.original(system, prompt, schema, name, timeout)
            row['response'] = response
            return response
        except Exception as error:
            row['error'] = type(error).__name__
            row['http_status'] = getattr(error, 'status_code', None)
            raise
        finally:
            row['seconds'] = round(time.monotonic() - started, 3)


def observed(function, calls):
    before = len(calls.calls)
    start = time.monotonic()
    try:
        result = function()
        return {'status': 'ok', **result, 'seconds': round(time.monotonic() - start, 3), 'calls': calls.calls[before:]}
    except Exception as error:
        # Never publish arbitrary exception strings, credentials, headers or session cookies.
        return {'status': 'error', 'error_type': type(error).__name__, 'http_status': getattr(error, 'status_code', None),
                'seconds': round(time.monotonic() - start, 3), 'calls': calls.calls[before:]}


def assessment(case, dataset, spec, calls):
    question, snippets = package(dataset, case['source'], case['language'])
    functions = {'repoviva': lambda: grade_answer(question, case['answer'], snippets),
                 'baseline': lambda: baseline_assessment(spec, question, case['answer'], snippets)}
    # Alternate first system to limit systematic timing/quota-order advantage.
    order = ['repoviva', 'baseline'] if int(case['id'][1:]) % 2 else ['baseline', 'repoviva']
    row = {'id': case['id'], 'expected': case['expected_label'], 'expected_points': case['expected_points'], 'order': order}
    for name in order:
        def run(name=name):
            result = functions[name]()
            return {**assessment_outcome(result), 'feedback': result}
        row[name] = observed(run, calls)
    return row


def repair(case, dataset, spec, calls):
    family = dataset['repair_families'][case['family']]
    exercise = {key: family[key] for key in ('language', 'contract', 'reference_code', 'starter_code')}
    functions = {'repoviva': lambda: check_solution(family[case['variant']], exercise),
                 'baseline': lambda: baseline_repair(spec, family[case['variant']], exercise)}
    row = {'id': case['id'], 'expected': case['expected']}
    order = ['repoviva', 'baseline'] if int(case['id'][1:]) % 2 else ['baseline', 'repoviva']
    row['order'] = order
    for name in order:
        def run(name=name):
            result = functions[name]()
            if result.get('verdict') not in {'correct', 'incorrect', 'uncertain'}:
                raise ValueError('Invalid repair verdict')
            return {'label': result['verdict'], 'feedback': result}
        row[name] = observed(run, calls)
    return row


def speech(case, dataset):
    import requests
    import re
    folder = HERE / 'audio'
    folder.mkdir(exist_ok=True)
    wav = folder / (case['id'] + '.wav')
    # Stock synthetic voice only. No user recordings or private file contents.
    if not wav.exists():
        response = requests.post('https://api.vachana.ai/api/v1/tts/inference', headers={'X-API-Key-ID': os.environ['VACHANA_API_KEY']},
            json={'text': case['spoken'], 'voice': 'Yashraj', 'model': 'timbre-v3.0', 'language': 'auto',
                  'audio_config': {'sample_rate': 48000, 'container': 'wav'}}, timeout=60)
        if not response.ok:
            raise RuntimeError('Synthetic speech generation failed')
        # Timbre streams a WAV header; normalize sizes for the upload validator.
        raw = folder / (case['id'] + '.raw.wav')
        raw.write_bytes(response.content)
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            raise RuntimeError('ffmpeg is required to normalize synthetic speech')
        try:
            subprocess.run([ffmpeg, '-v', 'error', '-y', '-i', str(raw), '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], check=True, capture_output=True, timeout=30)
        finally:
            raw.unlink(missing_ok=True)
    with wave.open(str(wav)) as stream:
        seconds = stream.getnframes() / stream.getframerate()
        if not 0 < seconds <= 30:
            raise ValueError('Synthetic sample is outside the app audio limit')
    transcript = transcribe_wav(wav.read_bytes(), wav.name)
    _, snippets = package(dataset, case['source'])
    checks = suggested_checks(transcript, snippets)
    def found(alternatives):
        return any(re.search(r'(?<!\w)' + re.escape(term.casefold()) + r'(?!\w)', transcript.casefold()) for term in alternatives)
    return {'transcript': transcript, 'word_errors': word_errors(case['reference'], transcript), 'seconds': round(seconds, 3),
            'audio_sha256': sha(wav), 'audio': 'audio/' + wav.name, 'checks': checks,
            'missing_protected_groups': [alternatives for alternatives in case['protected'] if not found(alternatives)],
            'proposed_correction': case['intended_correction'], 'learner_correction': None,
            'review_status': 'Synthetic script reference; human listening and learner correction not yet collected'}


def reliability(case, dataset):
    """Fresh, uniquely named fixture identity; delete only its own rows, never truncate."""
    from backend.app import app
    from backend.database import PostgresStore
    from checks.auth_fixtures import authenticated_client
    import uuid
    url = os.getenv('TEST_DATABASE_URL')
    if not url:
        return {'status': 'skipped', 'reason': 'Requires an isolated TEST_DATABASE_URL named repoviva_test'}
    store = PostgresStore(url)
    with store.connection() as conn:
        if conn.execute('SELECT current_database() AS name').fetchone()['name'] != 'repoviva_test':
            raise RuntimeError('Refusing evaluation reliability checks on a non-test database')
    store.migrate()
    owner = 'google:evaluation-' + uuid.uuid4().hex
    try:
        with patch.dict(app.config, {'DATABASE_URL_OVERRIDE': url}):
            client = authenticated_client(app, owner)
            question, snippets = package(dataset, 'shipping')
            with client.post('/sources', data={'source_file': (io.BytesIO(dataset['sources']['shipping']['code'].encode()), 'shipping.py')}) as response:
                assert response.status_code == 201
                source_id = response.get_json()['source_id']
            def generated(real_snippets, count=1):
                updated = {**question, 'rubric': [{**r, 'snippet_id': real_snippets[0]['id']} for r in question['rubric']]}
                return [updated]
            with patch('backend.app.generate_question_set', side_effect=generated):
                response = client.post('/questions', json={'source_id': source_id, 'count': 1})
            assert response.status_code == 200
            turn_id = response.get_json()['questions'][0]['turn_id']
            draft = '500 includes equality and returns 0; 499 falls through to 40.'
            assert client.put('/history/turns/' + turn_id + '/draft', json={'answer': draft}).status_code == 200
            before = client.get('/profile').get_json()['usage']['allowances']
            if case['fault'] == 'silence':
                buf = io.BytesIO()
                with wave.open(buf, 'wb') as stream:
                    stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000); stream.writeframes(b'\x00\x00' * 32000)
                # Live Prisma, not an invented silence transcript. No automatic submission.
                with client.post('/transcriptions', data={'audio_file': (io.BytesIO(buf.getvalue()), 'silence.wav'), 'turn_id': turn_id}) as response:
                    code, payload = response.status_code, response.get_json()
                no_usable_transcript = code == 502 and not payload.get('transcript')
            else:
                if case['fault'] == 'provider_failure':
                    failure = patch('backend.interview.grading.json_completion', side_effect=provider.ProviderError('Injected outage'))
                elif case['fault'] == 'malformed_feedback':
                    failure = patch('backend.interview.grading.json_completion', return_value={'summary': 'Malformed', 'criteria': [], 'claims': []})
                else:
                    failure = patch('backend.interview.grading.json_completion', return_value={'summary': 'Source-backed feedback.',
                        'criteria': [{'id': r['id'], 'status': 'met', 'explanation': 'Explained.'} for r in question['rubric']],
                        'claims': [{'claim': '500 returns zero', 'label': 'supported', 'explanation': 'Cited.', 'snippet_id': response.get_json()['questions'][0]['evidence']['id'], 'line_start': 9999, 'line_end': 9999}]})
                with failure:
                    response = client.post('/answers', json={'turn_id': turn_id, 'answer': draft})
                code, payload = response.status_code, response.get_json()
                no_usable_transcript = True
            after = client.get('/profile').get_json()['usage']['allowances']
            # New authenticated request, same owner; persisted work rather than just an in-memory variable.
            restored = authenticated_client(app, owner).get('/sources/current').get_json()['saved_practice']
            draft_survives = restored['drafts'].get(turn_id) == draft
            with store.connection() as conn:
                count = conn.execute('SELECT count(*) AS n FROM repoviva.attempts WHERE owner=%s', (owner,)).fetchone()['n']
                released = conn.execute('SELECT lease_token IS NULL AS released FROM repoviva.turns WHERE id=%s AND owner=%s', (turn_id, owner)).fetchone()['released']
            allowance_unchanged = all(after[k]['used'] == before[k]['used'] for k in ('answers', 'transcriptions'))
            no_score = 'score' not in payload and count == 0
            return {'status': 'ok', 'passed': code == 502 and no_score and draft_survives and released and allowance_unchanged and no_usable_transcript,
                    'http_status': code, 'no_score': no_score, 'draft_survives_new_session': draft_survives,
                    'lease_released': released, 'allowance_refunded': allowance_unchanged,
                    'no_usable_transcript': no_usable_transcript, 'transcript': payload.get('transcript'),
                    'mode': 'live Prisma silence' if case['fault'] == 'silence' else 'injected provider fault through real Flask/PostgreSQL routes'}
    finally:
        with store.connection() as conn:
            conn.execute('DELETE FROM repoviva.users WHERE id=%s', (owner,))
        store.pool.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true', help='Freeze fixture, baseline, harness and production code hashes before live calls')
    parser.add_argument('--sections', nargs='+', choices=['assessment', 'repairs', 'speech', 'reliability'], default=['assessment', 'repairs', 'speech', 'reliability'])
    parser.add_argument('--gap', type=float, default=6, help='Minimum seconds between Groq calls; no automatic error retries')
    parser.add_argument('--run-name', help='A separate replication checkpoint under evaluation/runs; never replaces the original run')
    args = parser.parse_args()
    os.chdir(ROOT)
    load_dotenv(ROOT / '.env')
    manifest_path, output = HERE / 'freeze.json', HERE / 'results.json'
    if args.run_name:
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,60}', args.run_name):
            raise SystemExit('Use a short run name containing letters, digits, dashes or underscores')
        output = HERE / 'runs' / (args.run_name + '.json')
        output.parent.mkdir(exist_ok=True)
    hashes = {name: sha(ROOT / name) for name in FILES}
    if args.freeze:
        if manifest_path.exists() or output.exists():
            raise SystemExit('Already frozen. Keep this run; use a new version directory for a changed benchmark.')
        save(manifest_path, {'created_at': datetime.now(timezone.utc).isoformat(), 'files': hashes, 'model': provider.MODEL,
             'temperature': .2, 'max_tokens': 4000, 'retries': 0, 'run_policy': 'One result per system/case. Errors are retained. No held-out tuning. Human review pending.'})
        print('Evaluation candidate frozen before live calls. No product tuning against these results.')
        return
    if not manifest_path.exists() or json.loads(manifest_path.read_text())['files'] != hashes:
        raise SystemExit('Freeze is missing or inputs changed; do not silently reuse a benchmark version.')
    dataset = json.loads((HERE / 'dataset.json').read_text(encoding='utf-8'))
    spec = json.loads((HERE / 'baseline.json').read_text())
    results = json.loads(output.read_text(encoding='utf-8')) if output.exists() else {'started_at': datetime.now(timezone.utc).isoformat(), 'freeze_sha256': sha(manifest_path), 'sections': {}}
    if results['freeze_sha256'] != sha(manifest_path):
        raise SystemExit('Result/manifest mismatch')
    calls = RecordedCalls(max(0, args.gap))
    with patch('backend.interview.grading.json_completion', side_effect=calls), patch('backend.interview.debug_checker.json_completion', side_effect=calls), patch('backend.interview.provider.json_completion', side_effect=calls):
        for section in args.sections:
            rows = results['sections'].setdefault(section, [])
            done = {row['id'] for row in rows}
            for case in dataset[section]:
                if case['id'] in done:
                    continue  # Resume only unattempted cases; errors are never cherry-picked away.
                print('Running ' + case['id'] + ' (' + section + ')', flush=True)
                if section == 'assessment': row = assessment(case, dataset, spec, calls)
                elif section == 'repairs': row = repair(case, dataset, spec, calls)
                else:
                    try:
                        value = speech(case, dataset) if section == 'speech' else reliability(case, dataset)
                        row = {'id': case['id'], 'status': 'ok', **value}
                    except Exception as error:
                        row = {'id': case['id'], 'status': 'error', 'error_type': type(error).__name__}
                rows.append(row)
                save(output, results)
                print(case['id'] + ' recorded', flush=True)
    results['last_updated_at'] = datetime.now(timezone.utc).isoformat()
    save(output, results)
    print('Results retained in evaluation/results.json; errors and skipped cases remain visible.')


if __name__ == '__main__':
    main()
