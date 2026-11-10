"""Owned saved practice and real, concurrency-safe PostgreSQL allowances."""
import io
import os
import threading
import unittest
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from backend.app import app
from backend.account import period
from backend.database import close_pools
from backend.interview.evaluator import EvaluationError
from checks.auth_fixtures import authenticated_client
from checks.quiz_fixtures import fake_question_set, fake_grade
from checks import test_postgres as pgtests
TEST_URL = pgtests.TEST_URL


@unittest.skipUnless(TEST_URL, 'Requires the isolated repoviva_test database.')
class HistoryProfileTests(unittest.TestCase):
    setUpClass = classmethod(pgtests.PostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(pgtests.PostgresTests.tearDownClass.__func__)
    setUp = pgtests.PostgresTests.setUp
    upload = pgtests.PostgresTests.upload
    question = pgtests.PostgresTests.question
    answer = pgtests.PostgresTests.answer

    def quotas(self):
        response = self.client.get('/profile')
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()['usage']['allowances']

    def test_profile_details_survive_login_and_cannot_edit_identity_or_limits(self):
        self.assertEqual({k: v['remaining'] for k, v in self.quotas().items()}, {'questions': 10, 'answers': 30, 'transcriptions': 10})
        self.assertEqual(self.client.patch('/profile', json={'institution': 'Example College', 'display_name': 'Learner'}).status_code, 200)
        again = authenticated_client(app, 'google:db-one')
        self.assertEqual(again.get('/profile').get_json()['details']['institution'], 'Example College')
        self.assertEqual(self.other.get('/profile').get_json()['details'], {})
        for data in ({'email': 'changed@test'}, {'limit': 100}, {'course': 2}, {'study_year': 'x' * 41}, []):
            self.assertEqual(self.client.patch('/profile', json=data).status_code, 400)

    def test_duplicate_bytes_reuse_saved_questions_before_extraction_and_alias_search(self):
        source = self.upload()
        question = self.question(source['source_id'])
        self.upload(b'A different document.', 'other.md')
        with patch('backend.evidence.uploads.extract_document') as extract, patch('backend.app.generate_question_set') as generate:
            result = self.client.post('/sources', data={'source_file': (io.BytesIO(b'Photosynthesis uses light energy.'), 'renamed.md')})
        self.assertEqual(result.status_code, 200, result.get_json())
        extract.assert_not_called(); generate.assert_not_called()
        restored = result.get_json()
        self.assertTrue(restored['reused'])
        self.assertEqual(restored['source_id'], source['source_id'])
        self.assertEqual(restored['saved_practice']['questions'][0]['turn_id'], question['turn_id'])
        self.assertNotIn('reference_answer', result.get_data(as_text=True))
        self.assertEqual(self.client.get('/history/documents?q=renamed').get_json()['documents'][0]['id'], source['source_id'])
        self.assertEqual(self.quotas()['questions']['used'], 1)

    def test_changed_bytes_and_different_owner_are_separate(self):
        source = self.upload()
        changed = self.upload(b'An edited version.', 'notes.md')
        self.assertNotEqual(changed['source_id'], source['source_id'])
        other = self.other.post('/sources', data={'source_file': (io.BytesIO(b'Photosynthesis uses light energy.'), 'notes.md')})
        self.assertEqual(other.status_code, 201)
        self.assertNotEqual(other.get_json()['source_id'], source['source_id'])
        self.assertEqual(len(self.client.get('/history/documents').get_json()['documents']), 2)
        for path in (f"/sources/{source['source_id']}/activate", f"/sources/{source['source_id']}/close"):
            self.assertEqual(self.other.post(path, json={}).status_code, 404)
        self.assertEqual(self.other.get(f"/history/documents/{source['source_id']}").status_code, 404)
        self.assertEqual(self.other.delete(f"/history/documents/{source['source_id']}").status_code, 404)

    def test_close_restore_draft_review_and_free_practice_again(self):
        source = self.upload()
        question = self.question(source['source_id'])
        turn = question['turn_id']
        self.assertEqual(self.client.put(f'/history/turns/{turn}/draft', json={'answer': 'My unfinished answer'}).status_code, 200)
        self.assertEqual(self.other.put(f'/history/turns/{turn}/draft', json={'answer': 'bad'}).status_code, 404)
        self.assertEqual(self.client.post(f"/sources/{source['source_id']}/close").status_code, 204)
        self.assertEqual(self.client.get('/sources/current').status_code, 204)
        detail = self.client.get(f"/history/documents/{source['source_id']}").get_json()
        practice = detail['practice_sets'][0]['id']
        restored = self.client.post(f"/sources/{source['source_id']}/activate", json={'practice_id': practice}).get_json()['saved_practice']
        self.assertEqual(restored['drafts'][turn], 'My unfinished answer')
        self.assertEqual(restored['resume_turn_id'], turn)
        feedback = self.answer(turn)
        restored = self.client.get('/sources/current').get_json()['saved_practice']
        self.assertEqual(restored['drafts'], {})
        self.assertEqual(restored['results'][turn], feedback)
        self.assertEqual(self.client.get(f"/history/documents/{source['source_id']}").get_json()['practice_sets'][0]['score'], 100)
        before = self.quotas()
        with patch('backend.app.generate_question_set') as generate:
            retry = self.client.post(f'/history/practice-sets/{practice}/retry')
        self.assertEqual(retry.status_code, 200, retry.get_json()); generate.assert_not_called()
        self.assertNotEqual(retry.get_json()['saved_practice']['questions'][0]['turn_id'], turn)
        self.assertEqual(retry.get_json()['saved_practice']['results'], {})
        self.assertNotIn('reference_answer', retry.get_data(as_text=True))
        self.assertEqual(self.quotas(), before)
        self.assertEqual(self.other.post(f'/history/practice-sets/{practice}/retry').status_code, 404)
        self.assertEqual(self.client.delete(f"/history/documents/{source['source_id']}").status_code, 200)
        self.assertEqual(self.client.get('/history/documents').get_json()['documents'], [])
        # Deleting history cannot replenish paid API usage.
        self.assertEqual(self.quotas(), before)

    def test_daily_limit_blocks_before_provider_and_allows_other_user(self):
        source = self.upload()
        with patch.dict(os.environ, {'DAILY_QUESTION_LIMIT': '1'}), patch('backend.app.generate_question_set', side_effect=fake_question_set) as generate:
            self.assertEqual(self.client.post('/questions', json={'source_id': source['source_id']}).status_code, 200)
            rejected = self.client.post('/questions', json={'source_id': source['source_id']})
            self.assertEqual(rejected.status_code, 429, rejected.get_json())
            self.assertEqual(rejected.get_json()['error_code'], 'daily_allowance_exceeded')
            self.assertGreater(int(rejected.headers['Retry-After']), 0)
            self.assertEqual(generate.call_count, 1)
        self.assertEqual(self.other.get('/profile').get_json()['usage']['allowances']['questions']['used'], 0)

    def test_concurrent_requests_cannot_overspend_last_question_allowance(self):
        source = self.upload()
        clients = [authenticated_client(app, 'google:db-one') for _ in range(2)]
        barrier = threading.Barrier(2)
        def submit(client):
            barrier.wait(timeout=5)
            return client.post('/questions', json={'source_id': source['source_id']}).status_code
        with patch.dict(os.environ, {'DAILY_QUESTION_LIMIT': '1'}), patch('backend.app.generate_question_set', side_effect=fake_question_set) as generate:
            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = list(executor.map(submit, clients))
            self.assertEqual(sorted(statuses), [200, 429])
            self.assertEqual(generate.call_count, 1)
        self.assertEqual(self.quotas()['questions']['used'], 1)

    def test_review_failures_refund_allowance_and_limit_releases_turn_lease(self):
        question = self.question(self.upload()['source_id'])
        with patch('backend.app.grade_answer', side_effect=EvaluationError('Provider failure')):
            self.assertEqual(self.client.post('/answers', json={'turn_id': question['turn_id'], 'answer': 'x'}).status_code, 502)
        self.assertEqual(self.quotas()['answers']['used'], 0)
        with patch.dict(os.environ, {'DAILY_REVIEW_LIMIT': '0'}), patch('backend.app.grade_answer') as grade:
            self.assertEqual(self.client.post('/answers', json={'turn_id': question['turn_id'], 'answer': 'x'}).status_code, 429)
            grade.assert_not_called()
        self.answer(question['turn_id'])
        self.assertEqual(self.quotas()['answers']['used'], 1)

    def test_valid_audio_counts_once_and_missing_audio_is_free(self):
        self.assertEqual(self.client.post('/transcriptions').status_code, 400)
        def audio():
            output = io.BytesIO()
            with wave.open(output, 'wb') as stream:
                stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(16000)
                stream.writeframes(b'\x00\x00' * 16000)
            output.seek(0)
            return {'audio_file': (output, 'answer.wav')}
        with patch.dict(os.environ, {'DAILY_TRANSCRIPTION_LIMIT': '1'}), patch('backend.app.transcribe_wav', return_value='A transcript') as transcribe:
            self.assertEqual(self.client.post('/transcriptions', data=audio()).status_code, 200)
            self.assertEqual(self.client.post('/transcriptions', data=audio()).status_code, 429)
            self.assertEqual(transcribe.call_count, 1)
        self.assertEqual(self.quotas()['transcriptions']['used'], 1)

    def test_usage_resets_by_utc_date_and_survives_new_pool(self):
        self.question(self.upload()['source_id'])
        close_pools()
        self.assertEqual(self.quotas()['questions']['used'], 1)
        with patch('backend.account.period', return_value=(period()[0] + timedelta(days=1), period()[1] + timedelta(days=1))):
            self.assertEqual(self.quotas()['questions']['remaining'], 10)

    def test_draft_validation_busy_lease_and_malformed_history_page(self):
        turn = self.question(self.upload()['source_id'])['turn_id']
        for data in ({'answer': 2}, {'answer': 'x' * 4001}, []):
            self.assertEqual(self.client.put(f'/history/turns/{turn}/draft', json=data).status_code, 400)
        _, lease = self.store.claim_turn('google:db-one', turn)
        self.assertEqual(self.client.put(f'/history/turns/{turn}/draft', json={'answer': 'x'}).status_code, 409)
        self.store.release_turn('google:db-one', turn, lease)
        self.assertEqual(self.client.get('/history/documents?offset=oops').status_code, 400)
