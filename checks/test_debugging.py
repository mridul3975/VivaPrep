"""Source-owned debugging generation, persistence, quotas and observations."""
import unittest
from unittest.mock import patch
from checks import test_postgres as pgtests
from backend.app import app
from backend.interview.provider import ProviderError
from checks.debug_fixtures import CODE, challenge


@unittest.skipUnless(pgtests.TEST_URL, 'Requires the isolated repoviva_test database.')
class DebuggingTests(unittest.TestCase):
    setUpClass = classmethod(pgtests.PostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(pgtests.PostgresTests.tearDownClass.__func__)
    setUp = pgtests.PostgresTests.setUp
    upload = pgtests.PostgresTests.upload

    def start(self, source=None):
        source = source or self.upload(CODE.encode(), 'tax.js')
        with patch('backend.debugging.generate_debug_challenge', side_effect=challenge):
            response = self.client.post('/debug/runs', json={'source_id': source['source_id']})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_requires_actual_owned_source_and_no_default_challenge(self):
        self.assertEqual(app.test_client().get('/debug/challenges').status_code, 401)
        self.assertEqual(self.client.get('/debug/challenges').get_json()['challenges'], [])
        self.assertEqual(self.client.post('/debug/runs', json={}).status_code, 400)
        source = self.upload(CODE.encode(), 'tax.js')
        with patch('backend.debugging.generate_debug_challenge') as provider:
            self.assertEqual(self.other.post('/debug/runs', json={'source_id': source['source_id']}).status_code, 404)
            notes = self.upload(b'No code.', 'notes.md')
            self.assertEqual(self.client.post('/debug/runs', json={'source_id': notes['source_id']}).status_code, 400)
            provider.assert_not_called()

    def test_source_snapshot_and_graduated_hints(self):
        source = self.upload(CODE.encode(), 'student-tax.js')
        run = self.start(source)
        self.assertEqual(run['scenario']['project'], 'student-tax.js')
        self.assertEqual(run['scenario']['reference_code'], CODE)
        self.assertEqual(run['scenario']['starter_code'], CODE.replace('+', '-'))
        self.assertEqual(run['source_id'], source['source_id'])
        self.assertEqual(run['hints'], [])
        self.assertNotIn('challenge_hints', run)
        for index in range(1, 5):
            result = self.client.post(f"/debug/runs/{run['id']}/hint").get_json()
            self.assertEqual(len(result['hints']), min(index, 3))
        self.assertEqual(self.client.patch(f"/debug/runs/{run['id']}", json={'hints_revealed': 3}).status_code, 400)
        self.client.delete('/history/documents/' + source['source_id'])
        self.assertEqual(self.client.get('/debug/runs/' + run['id']).status_code, 404)

    def test_old_sample_links_cannot_restore_or_mutate_sample(self):
        with self.store.connection() as conn:
            conn.execute("INSERT INTO repoviva.debug_runs(id,owner,scenario_id,state) VALUES(%s,%s,%s,'{}'::jsonb)",
                         ('archived-check', 'google:db-one', 'recording-duration-v1'))
        url = '/debug/runs/archived-check'
        self.assertEqual(self.client.get('/debug/runs').get_json()['runs'], [])
        self.assertEqual(self.other.get(url).status_code, 404)
        for response in (self.client.get(url), self.client.patch(url, json={'code': 'anything'}), self.client.post(url + '/hint')):
            self.assertEqual(response.status_code, 410)
            self.assertIn('own source file', response.get_json()['error'])
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_failure_refunds_allowance_without_creating_sample_and_enforces_limit(self):
        source = self.upload(CODE.encode(), 'tax.js')
        before = self.client.get('/profile').get_json()['usage']['allowances']['questions']['used']
        for error, status in ((ProviderError('Provider unavailable'), 502), (ValueError('Invalid quote'), 502), (ProviderError('Rate limited', 429), 503)):
            with patch('backend.debugging.generate_debug_challenge', side_effect=error):
                response = self.client.post('/debug/runs', json={'source_id': source['source_id']})
            self.assertEqual(response.status_code, status)
        self.assertEqual(self.client.get('/debug/runs').get_json()['runs'], [])
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['questions']['used'], before)
        with patch('backend.account.limits', return_value={'questions': 0, 'answers': 30, 'transcriptions': 10}), patch('backend.debugging.generate_debug_challenge') as provider:
            self.assertEqual(self.client.post('/debug/runs', json={'source_id': source['source_id']}).status_code, 429)
            provider.assert_not_called()

    def test_owned_saves_survive_session_and_only_generation_charges_ai(self):
        before = self.client.get('/profile').get_json()['usage']['allowances']['questions']['used']
        run = self.start()
        url = '/debug/runs/' + run['id']
        body = {'code': CODE, 'hypothesis': 'The operator subtracts tax.', 'explanation': 'Add tax instead.'}
        self.assertEqual(self.client.patch(url, json=body).status_code, 200)
        self.client.post(url + '/hint')
        from checks.auth_fixtures import authenticated_client
        saved = authenticated_client(app, 'google:db-one').get(url).get_json()
        self.assertEqual(saved['code'], CODE)
        self.assertEqual(len(saved['hints']), 1)
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['questions']['used'], before + 1)
        summary = self.client.get('/debug/runs').get_json()['runs'][0]
        self.assertEqual(summary['filename'], 'tax.js')
        self.assertEqual(summary['title'], run['scenario']['title'])
        self.assertEqual(self.other.get('/debug/runs').get_json()['runs'], [])
        for method in ('get', 'patch', 'delete'):
            self.assertEqual(getattr(self.other, method)(url, **({'json': body} if method == 'patch' else {})).status_code, 404)
        self.assertEqual(self.other.post(url + '/hint').status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_observations_bind_to_this_function_and_invalidate_on_edit(self):
        run = self.start()
        url = '/debug/runs/' + run['id']
        rows = [{'id': t['id'], 'actual': t['expected'], 'error': '', 'passed': True} for t in run['scenario']['tests']]
        data = {'code': CODE, 'hypothesis': 'Subtracting tax.', 'explanation': 'Now adds tax.', 'test_result': {'tested_code': CODE, 'results': rows}}
        result = self.client.patch(url, json=data)
        self.assertEqual(result.status_code, 200, result.get_json())
        self.assertTrue(result.get_json()['solution_passed'])
        self.assertFalse(result.get_json()['complete'])  # A saved explanation still needs a viva review.
        rows[0]['actual'] = False
        self.assertFalse(self.client.patch(url, json=data).get_json()['tests_passed'])
        rows[0]['actual'] = 15
        self.client.patch(url, json=data)
        edited = self.client.patch(url, json={'code': run['scenario']['starter_code']}).get_json()
        self.assertFalse(edited['tests_current']); self.assertFalse(edited['complete'])
        self.assertEqual(self.client.patch(url, json={'test_result': data['test_result']}).status_code, 400)
        rows[0]['actual'] = float('nan')
        self.assertEqual(self.client.patch(url, json=data).status_code, 400)

    def test_local_plan_cannot_claim_tests_passed(self):
        source = self.upload(b'def add_tax(amount):\n    return amount + 5', 'tax.py')
        from checks.debug_fixtures import completion
        from backend.interview.debug_generator import generate_debug_challenge
        data = {**completion(), 'function_name': '', 'tests': [], 'line_end': 2}
        def local_challenge(document, snippet_id=None):
            with patch('backend.interview.debug_generator.json_completion', return_value=data):
                return generate_debug_challenge(document, snippet_id)
        with patch('backend.debugging.generate_debug_challenge', side_effect=local_challenge):
            response = self.client.post('/debug/runs', json={'source_id': source['source_id']})
        self.assertEqual(response.status_code, 201, response.get_json())
        run = response.get_json()
        self.assertFalse(run['tests_passed']); self.assertFalse(run['complete'])
        self.assertIn('not been verified', run['verification'])
        self.assertEqual(self.client.patch('/debug/runs/' + run['id'], json={'test_result': {'tested_code': run['code'], 'results': []}}).status_code, 400)

    def test_invalid_input_and_csrf_and_code_never_executed_on_server(self):
        run = self.start()
        url = '/debug/runs/' + run['id']
        for body in ({'code': 2}, {'explanation': 'x' * 4001}, {'test_result': {}}, {'complete': True}, []):
            self.assertEqual(self.client.patch(url, json=body).status_code, 400)
        self.assertEqual(self.client.patch(url, json={'code': 'while (true) {}'}).status_code, 200)
        self.assertEqual(self.client.patch(url, json={'code': 'x' * 50000}).status_code, 413)
        csrf = self.client.environ_base.pop('HTTP_X_CSRF_TOKEN')
        try:
            self.assertEqual(self.client.post(url + '/hint').status_code, 403)
            self.assertEqual(self.client.post(url + '/check', json={'code': CODE}).status_code, 403)
        finally:
            self.client.environ_base['HTTP_X_CSRF_TOKEN'] = csrf

    def test_reference_check_is_owned_free_persistent_and_stale_after_edit(self):
        run = self.start()
        url = '/debug/runs/' + run['id']
        before = self.client.get('/profile').get_json()['usage']['allowances']['answers']['used']
        self.assertEqual(self.other.post(url + '/check', json={'code': CODE}).status_code, 404)
        self.assertEqual(self.client.post(url + '/check', json={'code': CODE}).status_code, 409)
        for body in ({}, {'code': ''}, {'code': 1}, {'code': 'a' * 12001}):
            self.assertEqual(self.client.post(url + '/check', json=body).status_code, 400)
        self.client.patch(url, json={'code': CODE, 'hypothesis': 'Wrong operator', 'explanation': 'Restored addition'})
        with patch('backend.interview.debug_checker.json_completion') as provider:
            result = self.client.post(url + '/check', json={'code': CODE}).get_json()
            provider.assert_not_called()
        self.assertEqual(result['solution_result']['score'], 100)
        self.assertTrue(result['solution_passed']); self.assertFalse(result['complete']); self.assertFalse(result['tests_passed'])
        self.assertTrue(self.client.get(url).get_json()['solution_current'])
        self.assertTrue(self.client.get('/debug/runs').get_json()['runs'][0]['solution_passed'])
        changed = self.client.patch(url, json={'code': CODE + '\n// changed'}).get_json()
        self.assertFalse(changed['solution_current']); self.assertFalse(changed['complete'])
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['answers']['used'], before)

    def test_alternative_review_quota_cache_failure_refund_and_race(self):
        run = self.start()
        url = '/debug/runs/' + run['id']
        code = 'function addTax(amount) { return 5 + amount; }'
        self.client.patch(url, json={'code': code})
        before = self.client.get('/profile').get_json()['usage']['allowances']['answers']['used']
        with patch('backend.interview.debug_checker.json_completion', side_effect=ProviderError('Unavailable')):
            self.assertEqual(self.client.post(url + '/check', json={'code': code}).status_code, 502)
        self.assertNotIn('solution_result', self.client.get(url).get_json())
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['answers']['used'], before)
        with patch('backend.interview.debug_checker.json_completion', return_value={'verdict': 'correct', 'explanation': 'Addition is commutative.'}) as provider:
            for _ in range(2):
                result = self.client.post(url + '/check', json={'code': code})
                self.assertEqual(result.status_code, 200, result.get_json())
                self.assertEqual(result.get_json()['solution_result']['method'], 'ai_review')
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['answers']['used'], before + 1)
        new_code = code + '\n// new'
        self.client.patch(url, json={'code': new_code})
        with patch('backend.account.limits', return_value={'questions': 10, 'answers': 0, 'transcriptions': 10}), patch('backend.interview.debug_checker.json_completion') as provider:
            self.assertEqual(self.client.post(url + '/check', json={'code': new_code}).status_code, 429)
            provider.assert_not_called()
        def concurrent_edit(*args):
            self.client.patch(url, json={'code': code + '\n// edited during review'})
            return {'verdict': 'incorrect', 'explanation': 'Changed code.'}
        with patch('backend.interview.debug_checker.json_completion', side_effect=concurrent_edit):
            self.assertEqual(self.client.post(url + '/check', json={'code': new_code}).status_code, 409)
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['answers']['used'], before + 1)
