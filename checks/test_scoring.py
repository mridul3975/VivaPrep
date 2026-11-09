from copy import deepcopy
import json
import os
import unittest
from unittest.mock import Mock, patch

from backend.interview.evaluator import EvaluationError
from backend.interview.grading import grade_answer
from backend.interview.question_generator import QuestionGenerationError, generate_question_set
from backend.interview.provider import ProviderError, json_completion


SNIPPETS = [{'id': 'source:1', 'path': 'biology.txt', 'citation_type': 'lines', 'start_line': 1, 'end_line': 1,
             'content': ['Photosynthesis converts light energy into chemical energy in chloroplasts.']}]
PACKAGE = {'question': 'Describe the energy conversion and where it occurs.',
           'reference_answer': 'Light energy becomes chemical energy inside chloroplasts.',
           'rubric': [{'id': 'c1', 'description': 'Explains the energy conversion.', 'snippet_id': 'source:1', 'quote': 'light energy into chemical energy'},
                      {'id': 'c2', 'description': 'Identifies chloroplasts.', 'snippet_id': 'source:1', 'quote': 'in chloroplasts'}]}


def result_for(first, second, claims=None):
    return {'criteria': [{'id': 'c1', 'status': first, 'explanation': 'Energy conversion assessment.'},
                         {'id': 'c2', 'status': second, 'explanation': 'Location assessment.'}],
            'claims': [] if claims is None else claims}


class ScoringTests(unittest.TestCase):
    def test_correct_partial_incorrect_and_missing_answers(self):
        cases = [('met', 'met', 100), ('met', 'partial', 75),
                 ('contradicted', 'contradicted', 0), ('missed', 'missed', 0)]
        for first, second, expected in cases:
            with self.subTest(statuses=(first, second)), patch('backend.interview.grading.json_completion', return_value=result_for(first, second)):
                self.assertEqual(grade_answer(PACKAGE, 'student answer', SNIPPETS)['score']['percentage'], expected)

    def test_unverified_source_criteria_are_excluded_not_marked_wrong(self):
        with patch('backend.interview.grading.json_completion', return_value=result_for('met', 'unverified')):
            score = grade_answer(PACKAGE, 'student answer', SNIPPETS)['score']
        self.assertEqual(score, {'earned': 1, 'possible': 1, 'percentage': 100, 'excluded_criteria': 1})
        with patch('backend.interview.grading.json_completion', return_value=result_for('unverified', 'unverified')):
            self.assertIsNone(grade_answer(PACKAGE, 'student answer', SNIPPETS)['score']['percentage'])

    def test_provider_numeric_score_cannot_override_server_points(self):
        result = result_for('missed', 'missed')
        result['score'] = 100
        with patch('backend.interview.grading.json_completion', return_value=result):
            self.assertEqual(grade_answer(PACKAGE, 'I do not know', SNIPPETS)['score']['percentage'], 0)

    def test_invalid_criteria_and_quotes_fail_instead_of_inventing_grade(self):
        invalid = [result_for('invalid', 'met'), {'criteria': [], 'claims': []},
                   {'criteria': [{'id': 'c1', 'status': 'met', 'explanation': 'x'}] * 2, 'claims': []},
                   result_for('met', 'met', [{'claim': 'c', 'label': 'supported', 'explanation': 'e', 'snippet_id': 'source:1', 'quote': 'invented quote'}])]
        for response in invalid:
            with self.subTest(response=response), patch('backend.interview.grading.json_completion', return_value=response):
                with self.assertRaises(EvaluationError):
                    grade_answer(PACKAGE, 'answer', SNIPPETS)

    def test_reference_and_original_evidence_are_both_sent_for_grading(self):
        with patch('backend.interview.grading.json_completion', return_value=result_for('met', 'met')) as provider:
            grade_answer(PACKAGE, 'Equivalent wording from the student.', SNIPPETS)
        prompt = provider.call_args.args[1]
        self.assertIn(PACKAGE['reference_answer'], prompt)
        self.assertIn(SNIPPETS[0]['content'][0], prompt)
        self.assertIn('Equivalent wording from the student.', prompt)

    def test_question_set_validates_reference_answers_and_rubric_citations(self):
        with patch('backend.interview.question_generator.json_completion', return_value={'questions': [deepcopy(PACKAGE)]}):
            generated = generate_question_set(SNIPPETS)
        self.assertEqual(generated[0]['reference_answer'], PACKAGE['reference_answer'])
        invalid = deepcopy(PACKAGE)
        invalid['rubric'][0]['quote'] = 'not in the uploaded source'
        with patch('backend.interview.question_generator.json_completion', return_value={'questions': [invalid]}):
            with self.assertRaises(QuestionGenerationError):
                generate_question_set(SNIPPETS)

    def test_provider_rejects_non_json_and_missing_content(self):
        for content in (None, 'not JSON', json.dumps([])):
            reply = Mock(ok=True)
            reply.json.return_value = {'choices': [{'message': {'content': content}}]}
            with self.subTest(content=content), patch.dict(os.environ, {'GROQ_API_KEY': 'test'}), patch('backend.interview.provider.requests.post', return_value=reply):
                with self.assertRaises(ProviderError):
                    json_completion('system', 'prompt', {}, 'test')


if __name__ == '__main__':
    unittest.main()
