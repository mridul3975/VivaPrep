"""Repair defenses are owned, source-grounded, saved, quota-bound and edit-sensitive."""
import io
import unittest
import wave
from unittest.mock import patch
from checks import test_postgres as pg
from checks.debug_fixtures import CODE, challenge
from backend.interview.debug_viva import evaluate_defense, fingerprint
from backend.interview.provider import ProviderError
from backend.speech.review import store_debug_review


def completion(status='met'):
    return {'criteria': [{'id': key, 'status': status, 'explanation': 'The operator must add five; 10 yields 5 before and 15 after.',
                           'citations': [{'version': 'broken', 'line_start': 2, 'line_end': 2},
                                         {'version': 'repair', 'line_start': 2, 'line_end': 2}]}
                          for key in ('explanation', 'failing_input')]}


class DefenseEvaluatorTests(unittest.TestCase):
    def state(self):
        return {'scenario': {'starter_code': CODE.replace('+', '-'), 'reference_code': CODE,
                             'language': 'JavaScript', 'contract': 'Add five', 'tests': [], 'execution_mode': 'javascript'},
                'code': CODE, 'explanation': 'Use addition', 'failing_input': '10: 5 before, 15 after'}

    def test_validated_quotes_and_server_computed_score(self):
        state = self.state()
        with patch('backend.interview.debug_viva.json_completion', return_value=completion()) as provider:
            result = evaluate_defense(state)
            self.assertTrue(result['passed']); self.assertEqual(result['score'], 100)
            self.assertEqual(result['criteria'][0]['evidence'][0]['quote'], '  return amount - 5;')
            self.assertEqual(result['criteria'][0]['evidence'][1]['quote'], '  return amount + 5;')
            self.assertNotIn('original_transcript', provider.call_args.args[1])
        original = fingerprint(state)
        state['hypothesis'] = 'An optional early thought.'
        self.assertEqual(original, fingerprint(state))
        state['failing_input'] = '0: -5 before, 5 after'
        self.assertNotEqual(original, fingerprint(state))

    def test_invalid_ranges_missing_duplicate_criteria_and_uncertainty(self):
        mutations = []
        for invalid in (0, 200, True):
            item = completion(); item['criteria'][0]['citations'][0]['line_end'] = invalid; mutations.append(item)
        item = completion(); item['criteria'][1]['id'] = 'explanation'; mutations.append(item)
        item = completion(); item['criteria'][0]['citations'] = []; mutations.append(item)
        mutations.append({'criteria': []})
        for item in mutations:
            with self.subTest(item=item), patch('backend.interview.debug_viva.json_completion', return_value=item), self.assertRaises(ValueError):
                evaluate_defense(self.state())
        with patch('backend.interview.debug_viva.json_completion', return_value=completion('uncertain')):
            result = evaluate_defense(self.state())
            self.assertIsNone(result['score']); self.assertFalse(result['passed'])
        item = completion(); item['criteria'][1]['status'] = 'partial'
        with patch('backend.interview.debug_viva.json_completion', return_value=item):
            self.assertEqual(evaluate_defense(self.state())['score'], 75)


@unittest.skipUnless(pg.TEST_URL, 'Requires isolated PostgreSQL.')
class DebugDefenseTests(unittest.TestCase):
    setUpClass = classmethod(pg.PostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(pg.PostgresTests.tearDownClass.__func__)
    setUp = pg.PostgresTests.setUp
    upload = pg.PostgresTests.upload

    def prepare(self, accepted=True):
        source = self.upload(CODE.encode(), 'tax.js')
        with patch('backend.debugging.generate_debug_challenge', side_effect=challenge):
            result = self.client.post('/debug/runs', json={'source_id': source['source_id']})
        self.assertEqual(result.status_code, 201)
        run = result.get_json(); url = '/debug/runs/' + run['id']
        if accepted:
            self.client.patch(url, json={'code': CODE, 'explanation': 'Addition restores the tax.', 'failing_input': '10 returned 5; now 15.'})
            self.assertEqual(self.client.post(url + '/check', json={'code': CODE}).status_code, 200)
        return run, url

    def used(self):
        return self.client.get('/profile').get_json()['usage']['allowances']['answers']['used']

    def test_owned_accepted_code_required_and_no_forged_review(self):
        run, url = self.prepare(False)
        with patch('backend.debugging.evaluate_defense') as provider:
            self.assertEqual(self.other.post(url + '/defend', json={}).status_code, 404)
            self.assertEqual(self.client.post(url + '/defend', json={}).status_code, 409)
            self.assertEqual(self.client.post(url + '/defend', json={'score': 100}).status_code, 400)
            self.assertEqual(self.client.patch(url, json={'defense_result': {'score': 100}}).status_code, 400)
            provider.assert_not_called()
        self.client.patch(url, json={'code': CODE})
        self.client.post(url + '/check', json={'code': CODE})
        self.assertEqual(self.client.post(url + '/defend', json={}).status_code, 400)

    def test_cached_review_restores_and_edit_invalidates(self):
        run, url = self.prepare()
        before = self.used()
        with patch('backend.interview.debug_viva.json_completion', return_value=completion()) as provider:
            result = self.client.post(url + '/defend', json={})
            self.assertEqual(result.status_code, 200, result.get_json())
            self.assertTrue(result.get_json()['complete'])
            self.assertEqual(self.client.post(url + '/defend', json={}).status_code, 200)
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(self.used(), before + 1)
        restored = self.client.get(url).get_json()
        self.assertTrue(restored['defense_current']); self.assertEqual(restored['defense_result']['score'], 100)
        self.assertTrue(self.client.get('/debug/runs').get_json()['runs'][0]['complete'])
        edited = self.client.patch(url, json={'failing_input': '0 returned -5; now 5.'}).get_json()
        self.assertFalse(edited['complete']); self.assertFalse(edited['defense_current'])
        self.assertIn('defense_result', edited)
        with patch('backend.interview.debug_viva.json_completion', return_value=completion('partial')):
            result = self.client.post(url + '/defend', json={}).get_json()
        self.assertFalse(result['complete']); self.assertEqual(result['defense_result']['score'], 50)
        self.assertFalse(self.client.patch(url, json={'code': run['code']}).get_json()['defense_current'])

    def test_failures_refund_and_release_lease(self):
        _, url = self.prepare(); before = self.used()
        for failure, expected in ((ProviderError('limited', 429), 503), (ValueError('bad quote'), 502)):
            with patch('backend.debugging.evaluate_defense', side_effect=failure):
                result = self.client.post(url + '/defend', json={})
                self.assertEqual(result.status_code, expected)
            saved = self.client.get(url).get_json()
            self.assertNotIn('defense_result', saved); self.assertNotIn('defense_lease', saved)
            self.assertEqual(self.used(), before)
        with patch('backend.interview.debug_viva.json_completion', return_value=completion()):
            self.assertEqual(self.client.post(url + '/defend', json={}).status_code, 200)

    def test_quota_and_csrf_prevent_provider_call_and_leave_run_retryable(self):
        _, url = self.prepare()
        csrf = self.client.environ_base.pop('HTTP_X_CSRF_TOKEN')
        with patch('backend.debugging.evaluate_defense') as provider:
            self.assertEqual(self.client.post(url + '/defend', json={}).status_code, 403)
            self.client.environ_base['HTTP_X_CSRF_TOKEN'] = csrf
            from backend.account import DEFAULTS
            with patch.dict('os.environ', {DEFAULTS['answers'][0]: '0'}):
                self.assertEqual(self.client.post(url + '/defend', json={}).status_code, 429)
            provider.assert_not_called()
        with patch('backend.interview.debug_viva.json_completion', return_value=completion()):
            self.assertEqual(self.client.post(url + '/defend', json={}).status_code, 200)

    def test_concurrent_edit_refunds_and_concurrent_review_is_rejected(self):
        _, url = self.prepare(); before = self.used()
        def changed(state):
            self.assertEqual(self.client.post(url + '/defend', json={}).status_code, 409)
            self.client.patch(url, json={'explanation': 'A changed answer.'})
            with patch('backend.interview.debug_viva.json_completion', return_value=completion()):
                return evaluate_defense(state)
        with patch('backend.debugging.evaluate_defense', side_effect=changed):
            result = self.client.post(url + '/defend', json={})
        self.assertEqual(result.status_code, 409, result.get_json()); self.assertEqual(self.used(), before)
        self.assertNotIn('defense_result', self.client.get(url).get_json())

    def test_spoken_drafts_require_confirmation_restore_and_reject_stale_receipts(self):
        run, url = self.prepare()
        with self.client.application.app_context():
            review = store_debug_review('google:db-one', run['id'], 'explanation', 'add tax', [{'content': CODE.splitlines()}])
        metadata = {'explanation': {'receipt_id': review['receipt_id'], 'reviewed': False}}
        self.assertEqual(self.client.patch(url, json={'speech_reviews': metadata}).status_code, 200)
        with patch('backend.debugging.evaluate_defense') as provider:
            self.assertEqual(self.client.post(url + '/defend', json={}).status_code, 400); provider.assert_not_called()
        metadata['explanation']['reviewed'] = True
        self.client.patch(url, json={'speech_reviews': metadata})
        self.assertEqual(self.client.get(url).get_json()['speech_reviews']['explanation']['original_transcript'], 'add tax')
        with patch('backend.interview.debug_viva.json_completion', return_value=completion()):
            response = self.client.post(url + '/defend', json={})
        self.assertTrue(response.get_json()['complete'])
        changed = self.client.patch(url, json={'explanation': 'new wording'}).get_json()
        self.assertFalse(changed['speech_reviews']['explanation']['reviewed']); self.assertFalse(changed['complete'])
        with self.client.application.app_context():
            store_debug_review('google:db-one', run['id'], 'explanation', 'another recording', [{'content': CODE.splitlines()}])
        self.assertEqual(self.client.patch(url, json={'speech_reviews': metadata}).status_code, 409)
        self.assertEqual(self.client.patch(url, json={'speech_reviews': {}}).status_code, 200)

    def test_transcription_is_scoped_to_owned_debug_run_and_not_auto_submitted(self):
        run, url = self.prepare()
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b'\0\0' * 1600)
        def form(**extra):
            return {'audio_file': (io.BytesIO(buffer.getvalue()), 'test.wav'), 'debug_run_id': run['id'], 'debug_field': 'explanation', **extra}
        with patch('backend.app.transcribe_wav', return_value='add tax') as provider:
            self.assertEqual(self.other.post('/transcriptions', data=form()).status_code, 404)
            provider.assert_not_called()
            self.assertEqual(self.client.post('/transcriptions', data=form(debug_field='bad')).status_code, 400)
            response = self.client.post('/transcriptions', data=form())
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertFalse(response.get_json()['speech_review']['reviewed'])
        saved = self.client.get(url).get_json()
        self.assertNotIn('speech_receipts', saved); self.assertNotIn('defense_result', saved)
        self.assertEqual(saved['explanation'], 'Addition restores the tax.')
