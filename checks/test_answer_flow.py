import io
import json
import os
import unittest
from unittest.mock import Mock, patch

from backend.app import app, turns, TURN_TTL_SECONDS
from backend.evidence.uploads import sources
from backend.interview.evaluator import EvaluationError, evaluate_answer
from checks.quiz_fixtures import fake_question_set, fake_grade


class AnswerFlowTests(unittest.TestCase):
    def setUp(self):
        turns.clear()
        sources.clear()
        self.client = app.test_client()
        response = self.client.post('/sources', data={'source_file': (io.BytesIO(b'The limit is 40 lines.'), 'notes.txt')})
        self.source_id = response.get_json()['source_id']
        response.close()

    def new_turn(self):
        with patch('backend.app.generate_question_set', side_effect=fake_question_set):
            response = self.client.post('/questions', json={'source_id': self.source_id})
        self.assertEqual(response.status_code, 200)
        return response.get_json()['questions'][0]

    def test_answer_uses_stored_reference_and_evidence_not_client_fields(self):
        question = self.new_turn()
        self.assertNotIn('reference_answer', json.dumps(question))
        with patch('backend.app.grade_answer', side_effect=fake_grade) as grade:
            response = self.client.post('/answers', json={
                'turn_id': question['turn_id'], 'answer': '40 lines',
                'question': 'tampered', 'reference_answer': 'tampered', 'score': 100,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['score']['percentage'], 100)
        self.assertEqual(grade.call_args.args[0]['question'], question['question'])
        self.assertEqual(grade.call_args.args[0]['reference_answer'], 'A hidden source-grounded reference answer.')
        self.assertEqual(grade.call_args.args[2], question['evidence_snippets'])

    def test_unknown_turn_and_provider_failure(self):
        self.assertEqual(self.client.post('/answers', json={'turn_id': 'unknown', 'answer': 'x'}).status_code, 404)
        turn_id = self.new_turn()['turn_id']
        with patch('backend.app.grade_answer', side_effect=EvaluationError('private provider detail')):
            response = self.client.post('/answers', json={'turn_id': turn_id, 'answer': 'x'})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('private provider detail', response.get_data(as_text=True))
        self.assertFalse(turns[turn_id]['busy'])

    def test_invalid_request_inputs_are_rejected_before_evaluation(self):
        payloads = [None, [], 'answer', {}, {'answer': 'x'}, {'turn_id': 'id'},
                    {'turn_id': 123, 'answer': 'x'}, {'turn_id': '', 'answer': 'x'},
                    {'turn_id': '   ', 'answer': 'x'}, {'turn_id': 'id', 'answer': 123},
                    {'turn_id': 'id', 'answer': ''}, {'turn_id': 'id', 'answer': '   '},
                    {'turn_id': 'id', 'answer': 'x' * 4001}]
        with patch('backend.app.grade_answer') as grade:
            for payload in payloads:
                with self.subTest(payload=payload):
                    self.assertEqual(self.client.post('/answers', json=payload).status_code, 400)
            self.assertEqual(self.client.post('/answers', data='{', content_type='application/json').status_code, 400)
            grade.assert_not_called()

    def test_expired_turn_is_rejected(self):
        turn_id = self.new_turn()['turn_id']
        turns[turn_id]['created'] -= TURN_TTL_SECONDS
        with patch('backend.app.grade_answer') as grade:
            self.assertEqual(self.client.post('/answers', json={'turn_id': turn_id, 'answer': '40'}).status_code, 404)
            self.assertNotIn(turn_id, turns)
            grade.assert_not_called()

    def test_busy_turn_does_not_start_another_evaluation(self):
        turn_id = self.new_turn()['turn_id']
        turns[turn_id]['busy'] = True
        with patch('backend.app.grade_answer') as grade:
            self.assertEqual(self.client.post('/answers', json={'turn_id': turn_id, 'answer': '40'}).status_code, 409)
            grade.assert_not_called()

    def test_legacy_claim_check_rejects_nonverbatim_quote(self):
        snippet = {'path': 'sample.py', 'start_line': 1, 'end_line': 3,
                   'content': ['if ready:', '    first()', '    second()']}
        claim = {'claim': 'c', 'label': 'supported', 'explanation': 'e', 'quote': 'first()\nsecond()'}
        response = Mock(ok=True)
        response.json.return_value = {'choices': [{'message': {'content': json.dumps([claim])}}]}
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test'}), patch('backend.interview.evaluator.requests.post', return_value=response):
            with self.assertRaises(EvaluationError):
                evaluate_answer('q', 'a', snippet)


if __name__ == '__main__':
    unittest.main()
