import unittest
from unittest.mock import patch
from backend import example
from backend.languages import LANGUAGES, language_choice, language_instruction, matches_language, short_feedback
from backend.interview.question_generator import _validate_questions
from backend.interview.grading import grade_answer

SOURCE = {'id': 'prime:1', 'path': 'prime.py', 'start_line': 1, 'end_line': 10, 'content': example.CODE.splitlines()}

class IndianLanguageTests(unittest.TestCase):
    def test_prepared_questions_followups_and_citations(self):
        for language in LANGUAGES:
            with self.subTest(language=language):
                self.assertEqual(language_choice(language), language)
                self.assertIn('Never translate source quotes', language_instruction(language))
                for package in example.question_set([SOURCE], 3, language):
                    self.assertTrue(matches_language(package['question'], language))
                    self.assertTrue(matches_language(package['reference_answer'], language))
                    _validate_questions({'questions': [package]}, [SOURCE], 1)
                    for item in package['rubric']: self.assertIn(item['quote'], example.CODE)
                    child = example.followup({'question': package['question'], 'question_package': package, 'snippets': [SOURCE]}, 'answer')
                    self.assertTrue(matches_language(child['question'], language))
                    _validate_questions({'questions': [child]}, [SOURCE], 1)

    def test_native_feedback_grade_and_translation_safety(self):
        for language in ('hi', 'ta', 'bn', 'te', 'mr', 'kn'):
            with self.subTest(language=language):
                package = example.question_set([SOURCE], 1, language)[0]
                response = {'summary': package['reference_answer'], 'criteria': [{'id': r['id'], 'status': 'met', 'explanation': package['reference_answer']} for r in package['rubric']], 'claims': []}
                with patch('backend.interview.grading.json_completion', return_value=response):
                    result = grade_answer(package, package['reference_answer'], [SOURCE])
                self.assertEqual(result['language'], language)
                self.assertEqual(result['score']['percentage'], 100)
                with patch('backend.interview.provider.json_completion', return_value={'summary': 'English only.'}), self.assertRaises(ValueError):
                    short_feedback('Correct for 1: False.', language)
                with patch('backend.interview.provider.json_completion', return_value={'summary': package['reference_answer'].replace('False', 'True')}), self.assertRaises(ValueError):
                    short_feedback('Correct for 1: False.', language)

if __name__ == '__main__': unittest.main()
