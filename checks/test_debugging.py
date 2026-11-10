"""Saved debugging practice ownership, observations and independent AI quotas."""
import unittest
from checks import test_postgres as pgtests
from backend.app import app
from backend.debugging import SCENARIO_ID, STARTER, TESTS


@unittest.skipUnless(pgtests.TEST_URL, 'Requires the isolated repoviva_test database.')
class DebuggingTests(unittest.TestCase):
    setUpClass = classmethod(pgtests.PostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(pgtests.PostgresTests.tearDownClass.__func__)
    setUp = pgtests.PostgresTests.setUp
    upload = pgtests.PostgresTests.upload

    def start(self, **extra):
        response = self.client.post('/debug/runs', json={'scenario_id': SCENARIO_ID, **extra})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_catalogue_reproduction_and_hints_are_graduated(self):
        self.assertEqual(app.test_client().get('/debug/challenges').status_code, 401)
        scenario = self.client.get('/debug/challenges').get_json()['challenges'][0]
        self.assertEqual(scenario['tests'][0]['args'], [30000, 30])
        run = self.start()
        self.assertEqual(run['hints'], [])
        self.assertEqual(run['code'], STARTER)
        for index in range(1, 5):
            result = self.client.post(f"/debug/runs/{run['id']}/hint").get_json()
            self.assertEqual(len(result['hints']), min(index, 3))
        self.assertEqual(self.client.patch(f"/debug/runs/{run['id']}", json={'hints_revealed': 3}).status_code, 400)

    def test_owned_context_is_snapshot_and_delete_removes_attached_run(self):
        source = self.upload(b'const duration = elapsed / 1000;', 'recorder.js')
        run = self.start(source_id=source['source_id'])
        self.assertEqual(run['context']['filename'], 'recorder.js')
        self.assertEqual(run['context']['snippet']['content'][0], 'const duration = elapsed / 1000;')
        self.assertEqual(self.other.post('/debug/runs', json={'scenario_id': SCENARIO_ID, 'source_id': source['source_id']}).status_code, 404)
        self.client.delete('/history/documents/' + source['source_id'])
        self.assertEqual(self.client.get('/debug/runs/' + run['id']).status_code, 404)

    def test_code_explanations_and_hints_survive_session_and_do_not_charge_ai(self):
        before = self.client.get('/profile').get_json()['usage']
        run = self.start()
        url = '/debug/runs/' + run['id']
        body = {'code': 'function validateRecording() { return false; }', 'hypothesis': 'The compared units differ.', 'explanation': 'Compare matching units.'}
        self.assertEqual(self.client.patch(url, json=body).status_code, 200)
        self.client.post(url + '/hint')
        from checks.auth_fixtures import authenticated_client
        client = authenticated_client(app, 'google:db-one')
        saved = client.get(url).get_json()
        self.assertEqual(saved['code'], body['code'])
        self.assertEqual(saved['hypothesis'], body['hypothesis'])
        self.assertEqual(len(saved['hints']), 1)
        self.assertEqual(self.client.get('/profile').get_json()['usage'], before)
        self.assertEqual(self.client.get('/debug/runs').get_json()['runs'][0]['id'], run['id'])
        self.assertEqual(self.other.get('/debug/runs').get_json()['runs'], [])
        for method in ('get', 'patch', 'delete'):
            result = getattr(self.other, method)(url, **({'json': body} if method == 'patch' else {}))
            self.assertEqual(result.status_code, 404)
        self.assertEqual(self.other.post(url + '/hint').status_code, 404)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_observations_bind_to_exact_code_and_edit_invalidates_pass(self):
        run = self.start()
        url = '/debug/runs/' + run['id']
        code = STARTER.replace('minSeconds * 1000', 'minSeconds')
        rows = [{'id': t['id'], 'actual': t['expected'], 'error': '', 'passed': True} for t in TESTS]
        data = {'code': code, 'hypothesis': 'Units differ.', 'explanation': 'Both are now seconds.', 'test_result': {'tested_code': code, 'results': rows}}
        result = self.client.patch(url, json=data)
        self.assertEqual(result.status_code, 200, result.get_json())
        self.assertTrue(result.get_json()['complete'])
        self.assertIn('client observations', result.get_json()['verification'])
        # Server recomputes pass flags, but does not certify browser execution.
        rows[0]['actual'] = False
        result = self.client.patch(url, json=data).get_json()
        self.assertFalse(result['tests_passed'])
        self.assertFalse(result['test_result']['results'][0]['passed'])
        rows[0]['actual'] = True
        self.client.patch(url, json=data)
        edited = self.client.patch(url, json={'code': STARTER}).get_json()
        self.assertFalse(edited['tests_current']); self.assertFalse(edited['complete'])
        self.assertEqual(self.client.patch(url, json={'test_result': data['test_result']}).status_code, 400)

    def test_invalid_data_csrf_and_code_are_never_executed_on_server(self):
        run = self.start()
        url = '/debug/runs/' + run['id']
        for body in ({'code': 2}, {'explanation': 'x' * 4001}, {'test_result': {}}, {'complete': True}, []):
            self.assertEqual(self.client.patch(url, json=body).status_code, 400)
        self.assertEqual(self.client.patch(url, json={'code': 'while (true) {}'}).status_code, 200)
        self.assertEqual(self.client.patch(url, json={'code': 'x' * 50000}).status_code, 413)
        csrf = self.client.environ_base.pop('HTTP_X_CSRF_TOKEN')
        try:
            self.assertEqual(self.client.post(url + '/hint').status_code, 403)
        finally:
            self.client.environ_base['HTTP_X_CSRF_TOKEN'] = csrf
