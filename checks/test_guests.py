"""Real guest cookies, prepared examples, quota boundaries and account transfer."""
import io
import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from backend.app import app
from backend.auth import guest_identities
from backend.guest_limits import events
from checks import test_auth as auth_tests
from checks import test_postgres as pgtests
from checks.quiz_fixtures import fake_question_set, fake_grade
from backend.interview.question_generator import QuestionGenerationError
from backend.example import CODE


def guest(client):
    bootstrap = client.get('/auth/session').get_json()
    response = client.post('/auth/guest', headers={'X-CSRF-Token': bootstrap['csrf_token']})
    assert response.status_code == 200, response.get_json()
    client.environ_base['HTTP_X_CSRF_TOKEN'] = response.get_json()['csrf_token']
    return response.get_json()


class GuestMemoryTests(unittest.TestCase):
    setUpClass = classmethod(auth_tests.GoogleAuthTests.setUpClass.__func__)
    login = auth_tests.GoogleAuthTests.login

    def setUp(self):
        auth_tests.GoogleAuthTests.setUp(self)
        events.clear(); guest_identities.clear()

    def test_guest_cookie_isolation_csrf_and_resume_after_logout(self):
        self.assertEqual(self.client.post('/auth/guest').status_code, 403)
        first = guest(self.client)
        self.assertTrue(first['user']['is_guest']); self.assertEqual(first['user']['email'], '')
        self.assertNotEqual(first['csrf_token'], self.initial['csrf_token'])
        profile = self.client.get('/profile').get_json()
        self.assertEqual([profile['usage']['allowances'][key]['limit'] for key in ('questions','answers','transcriptions')], [1,3,1])
        other = app.test_client(); second = guest(other)
        self.assertNotEqual(first['user']['id'], second['user']['id'])
        source = self.client.post('/sources/example').get_json()
        self.assertEqual(other.get('/sources/' + source['source_id']).status_code, 404)
        self.client.post('/auth/logout')
        resumed = guest(self.client)
        self.assertEqual(resumed['user']['id'], first['user']['id'])

    def test_prepared_questions_free_but_subjective_feedback_uses_review_budget(self):
        guest(self.client)
        with patch.dict(os.environ, {'GUEST_QUESTION_LIMIT':'0','GUEST_REVIEW_LIMIT':'0','GUEST_DAILY_QUESTIONS_LIMIT':'0','GUEST_DAILY_ANSWERS_LIMIT':'0'}), patch('backend.app.generate_question_set') as provider, patch('backend.app.grade_answer') as grader:
            source = self.client.post('/sources/example').get_json()
            questions = self.client.post('/questions', json={'source_id': source['source_id']}).get_json()['questions']
            self.assertEqual(len(questions), 3)
            for question in questions:
                self.assertNotIn('Answer True or False', question['question'])
                result = self.client.post('/answers', json={'turn_id': question['turn_id'], 'answer': 'The early return exits before the loop.'})
                self.assertEqual(result.status_code, 429, result.get_json())
            repeated = self.client.post('/questions', json={'source_id': source['source_id']}).get_json()['questions']
            self.assertEqual(repeated, questions)
            provider.assert_not_called(); grader.assert_not_called()
            self.assertEqual(len(events), 1)  # Only session admission, no AI reservation.
        with patch('backend.app.grade_answer', side_effect=fake_grade) as grader:
            result = self.client.post('/answers', json={'turn_id': questions[0]['turn_id'], 'answer': 'Input 1 satisfies number < 2, so it returns before the loop.'})
            self.assertEqual(result.status_code, 200, result.get_json())
            self.assertEqual(grader.call_count, 1)
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['answers']['used'], 1)

    def test_network_creation_limit_does_not_block_existing_guest(self):
        first = guest(self.client)
        with patch.dict(os.environ, {'GUEST_SESSIONS_PER_NETWORK':'1'}):
            other = app.test_client(); bootstrap = other.get('/auth/session').get_json()
            self.assertEqual(other.post('/auth/guest', headers={'X-CSRF-Token': bootstrap['csrf_token']}).status_code, 429)
            self.assertEqual(self.client.post('/auth/guest').get_json()['user']['id'], first['user']['id'])

    def test_google_upgrade_moves_memory_work_and_revokes_guest_cookie(self):
        guest(self.client)
        source = self.client.post('/sources/example').get_json()
        question = self.client.post('/questions', json={'source_id': source['source_id']}).get_json()['questions'][0]
        response = self.login()
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertFalse(response.get_json()['user']['is_guest'])
        self.client.environ_base['HTTP_X_CSRF_TOKEN'] = response.get_json()['csrf_token']
        self.assertEqual(self.client.get('/sources/current').get_json()['source_id'], source['source_id'])
        with patch('backend.app.grade_answer', side_effect=fake_grade):
            self.assertEqual(self.client.post('/answers', json={'turn_id':question['turn_id'],'answer':'The early return exits before the loop.'}).status_code, 200)
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['questions']['limit'], 10)


@unittest.skipUnless(pgtests.TEST_URL, 'Requires isolated PostgreSQL repoviva_test.')
class GuestPostgresTests(unittest.TestCase):
    setUpClass = classmethod(pgtests.PostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(pgtests.PostgresTests.tearDownClass.__func__)

    def setUp(self):
        pgtests.PostgresTests.setUp(self)
        with self.store.connection() as conn:
            conn.execute('DELETE FROM repoviva.guest_events')
        self.client = app.test_client(); self.other = app.test_client()
        guest(self.client); guest(self.other)

    def own_file(self, client=None, filename='tax.py'):
        response = (client or self.client).post('/sources', data={'source_file':(io.BytesIO(b'def add_tax(x):\n    return x + 5'),filename)})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_personal_limit_is_separate_for_each_guest_and_google(self):
        source, other_source = self.own_file(), self.own_file(self.other)
        with patch('backend.app.generate_question_set', side_effect=fake_question_set) as provider:
            self.assertEqual(self.client.post('/questions', json={'source_id':source['source_id']}).status_code, 200)
            rejected = self.client.post('/questions', json={'source_id':source['source_id']})
            self.assertEqual(rejected.status_code, 429)
            self.assertEqual(rejected.get_json()['error_code'], 'guest_allowance_exceeded')
            self.assertEqual(self.other.post('/questions', json={'source_id':other_source['source_id']}).status_code, 200)
            self.assertEqual(provider.call_count, 2)
        self.client.post('/auth/logout'); guest(self.client)
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['questions']['remaining'], 0)

    def test_shared_cap_concurrency_refund_and_provider_free_fallback(self):
        left, right = self.own_file(), self.own_file(self.other)
        with patch.dict(os.environ, {'GUEST_DAILY_QUESTIONS_LIMIT':'1'}), patch('backend.app.generate_question_set', side_effect=fake_question_set) as provider:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda item: item[0].post('/questions', json={'source_id':item[1]['source_id']}).status_code, [(self.client,left),(self.other,right)]))
            self.assertEqual(sorted(results), [200,429]); self.assertEqual(provider.call_count, 1)
            sample = self.client.post('/sources/example').get_json()
            self.assertEqual(self.client.post('/questions', json={'source_id':sample['source_id']}).status_code, 200)
        with self.store.connection() as conn:
            conn.execute('DELETE FROM repoviva.guest_events WHERE action=%s', ('questions',))
            conn.execute('DELETE FROM repoviva.api_usage')
        with patch('backend.app.generate_question_set', side_effect=QuestionGenerationError('Unavailable')):
            self.assertEqual(self.other.post('/questions', json={'source_id':right['source_id']}).status_code, 502)
        self.assertEqual(self.other.get('/profile').get_json()['usage']['allowances']['questions']['used'], 0)
        with self.store.connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) AS n FROM repoviva.guest_events WHERE action='questions'").fetchone()['n'], 0)

    def test_free_debug_source_ownership_and_reference_check(self):
        with patch.dict(os.environ, {'GUEST_DAILY_QUESTIONS_LIMIT':'0','GUEST_QUESTION_LIMIT':'0'}), patch('backend.debugging.generate_debug_challenge') as provider:
            source = self.client.post('/sources/example').get_json()
            run = self.client.post('/debug/runs', json={'source_id':source['source_id']})
            self.assertEqual(run.status_code, 201, run.get_json())
            run = run.get_json(); url = '/debug/runs/' + run['id']
            self.assertEqual(self.other.get(url).status_code, 404)
            self.assertEqual(self.other.post('/debug/runs', json={'source_id':source['source_id']}).status_code, 404)
            self.client.patch(url, json={'code':run['scenario']['reference_code']})
            result = self.client.post(url+'/check', json={'code':run['scenario']['reference_code']}).get_json()
            self.assertEqual(result['solution_result']['score'], 100)
            self.assertEqual(self.client.post('/debug/runs', json={'source_id':source['source_id']}).get_json()['id'], run['id'])
            provider.assert_not_called()

    def test_account_transfer_preserves_work_and_revokes_old_identity(self):
        source = self.client.post('/sources/example').get_json()
        question = self.client.post('/questions', json={'source_id':source['source_id']}).get_json()['questions'][0]
        with patch('backend.app.grade_answer', side_effect=fake_grade):
            self.assertEqual(self.client.post('/answers', json={'turn_id':question['turn_id'],'answer':'The early return exits before the loop.'}).status_code, 200)
        run = self.client.post('/debug/runs', json={'source_id':source['source_id']}).get_json()
        old = self.client.get('/auth/session').get_json()['user']['id']
        with app.app_context():
            self.store.save_login({'id':'google:upgraded','email':'upgraded@example.test','name':'Upgraded'},'new-token',9999999999,guest_owner=old)
        with self.store.connection() as conn:
            self.assertIsNone(conn.execute('SELECT id FROM repoviva.users WHERE id=%s',(old,)).fetchone())
            self.assertEqual(conn.execute('SELECT owner FROM repoviva.debug_runs WHERE id=%s',(run['id'],)).fetchone()['owner'],'google:upgraded')
            self.assertEqual(conn.execute('SELECT owner FROM repoviva.sources WHERE id=%s',(source['source_id'],)).fetchone()['owner'],'google:upgraded')
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM repoviva.attempts WHERE owner=%s',('google:upgraded',)).fetchone()['n'],1)
        self.assertIsNone(self.client.get('/auth/session').get_json()['user'])
