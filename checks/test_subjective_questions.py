"""Prepared and generated questions require source-grounded explanations."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from backend import example
from backend.interview.question_generator import generate_question_set, _validate_questions, QuestionGenerationError
from backend.interview.grading import grade_answer
from backend.interview.followup import generate_followup
from checks import test_postgres as pg
from checks.quiz_fixtures import fake_grade

SOURCE = {'id': 'prime:1', 'path': 'prime.py', 'start_line': 1, 'end_line': 10, 'content': example.CODE.rstrip('\n').splitlines()}


class SubjectiveQuestionTests(unittest.TestCase):
    def test_prepared_questions_and_followups_have_explanatory_rubrics(self):
        packages = example.question_set([SOURCE], 3)
        self.assertEqual(len(_validate_questions({'questions': deepcopy(packages)}, [SOURCE], 3)), 3)
        for package in packages:
            self.assertEqual(package['prepared_example'], example.QUESTION_VERSION)
            self.assertGreater(len(package['rubric']), 1)
            self.assertNotIn('Answer True or False', package['question'])
            for criterion in package['rubric']:
                self.assertIn(criterion['quote'], example.CODE)
            child = example.followup({'question': package['question'], 'snippets': [SOURCE]}, 'My explanation.')
            self.assertNotEqual(child['question'], package['question'])
            self.assertEqual(child['prepared_example'], example.QUESTION_VERSION)
            self.assertEqual(len(_validate_questions({'questions': [child]}, [SOURCE], 1)), 1)

    def test_binary_or_output_only_generation_is_repaired_or_rejected(self):
        valid = example.question_set([SOURCE], 1)[0]
        invalid = {**valid, 'question': 'What does is_prime(1) return?', 'reference_answer': 'False'}
        with patch('backend.interview.question_generator.json_completion', side_effect=[{'questions': [invalid]}, {'questions': [valid]}]) as provider:
            self.assertEqual(generate_question_set([SOURCE], 1)[0]['question'], valid['question'])
            self.assertEqual(provider.call_count, 2)
            self.assertIn('Every question must be subjective', provider.call_args.args[1])
        with patch('backend.interview.question_generator.json_completion', return_value={'questions': [invalid]}), self.assertRaises(QuestionGenerationError):
            generate_question_set([SOURCE], 1)
        parent = {'question': valid['question'], 'snippets': [SOURCE]}
        with patch('backend.interview.followup.json_completion', return_value={'questions': [invalid]}), self.assertRaises(ValueError):
            generate_followup(parent, 'False')

    def test_bare_boolean_cannot_satisfy_explanation_criteria_and_wording_is_not_graded(self):
        package = example.question_set([SOURCE], 1)[0]
        response = {'criteria': [{'id': item['id'], 'status': 'missed', 'explanation': 'The cause was not explained.'} for item in package['rubric']], 'claims': []}
        with patch('backend.interview.grading.json_completion', return_value=response) as provider:
            result = grade_answer(package, 'False', [SOURCE])
            self.assertEqual(result['score']['percentage'], 0)
            self.assertIn('a bare True/False', provider.call_args.args[1])
        response['criteria'] = [{**item, 'status': 'met', 'explanation': 'Correct reasoning in equivalent words.'} for item in response['criteria']]
        with patch('backend.interview.grading.json_completion', return_value=response):
            self.assertEqual(grade_answer(package, 'One is below two, so the function exits early without entering the loop.', [SOURCE])['score']['percentage'], 100)


@unittest.skipUnless(pg.TEST_URL, 'Requires isolated PostgreSQL.')
class PreparedUpgradeTests(unittest.TestCase):
    setUpClass = classmethod(pg.PostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(pg.PostgresTests.tearDownClass.__func__)
    setUp = pg.PostgresTests.setUp

    def test_old_demo_is_not_reused_as_new_questions_and_history_is_preserved(self):
        from psycopg.types.json import Jsonb
        source = self.client.post('/sources/example').get_json()
        old = self.client.post('/questions', json={'source_id': source['source_id']}).get_json()
        with self.store.connection() as conn:
            rows = conn.execute('SELECT id,payload FROM repoviva.turns WHERE practice_id=%s', (old['practice_id'],)).fetchall()
            for row in rows:
                payload = row['payload']; payload['question_package']['prepared_example'] = 'prime-v1'
                payload['question'] = 'Old Boolean question: True or False?'
                conn.execute('UPDATE repoviva.turns SET payload=%s WHERE id=%s', (Jsonb(payload), row['id']))
        self.assertIsNone(self.client.get('/sources/current').get_json()['saved_practice'])
        self.assertIsNone(self.client.post('/sources/example').get_json()['saved_practice'])
        fresh = self.client.post('/questions', json={'source_id': source['source_id']}).get_json()
        self.assertNotEqual(fresh['practice_id'], old['practice_id'])
        self.assertTrue(all(item['prepared_example'] == example.QUESTION_VERSION for item in fresh['questions']))
        self.assertEqual(self.client.post('/questions', json={'source_id': source['source_id']}).get_json()['questions'], fresh['questions'])
        retry = self.client.post('/history/practice-sets/' + old['practice_id'] + '/retry')
        self.assertEqual(retry.status_code, 200, retry.get_json())
        self.assertTrue(all(item['prepared_example'] == example.QUESTION_VERSION for item in retry.get_json()['saved_practice']['questions']))
        with self.store.connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM repoviva.turns WHERE practice_id=%s', (old['practice_id'],)).fetchone()['n'], 3)
        with patch('backend.app.grade_answer', side_effect=fake_grade) as grader:
            response = self.client.post('/answers', json={'turn_id': fresh['questions'][0]['turn_id'], 'answer': 'The guard returns early.'})
            self.assertEqual(response.status_code, 200, response.get_json()); grader.assert_called_once()
