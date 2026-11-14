import unittest
from unittest.mock import patch
from backend import example
from backend.languages import language_choice
from backend.database import StudyConflict
from backend.interview.grading import grade_answer
from backend.interview.evaluator import EvaluationError
from backend.speech.review import suggested_checks
from checks import test_postgres as pg

SOURCE = {'id': 'prime:1', 'path': 'prime.py', 'start_line': 1, 'end_line': 10, 'content': example.CODE.splitlines()}


class HinglishUnitTests(unittest.TestCase):
    def test_feedback_translation_preserves_boolean_facts_or_fails_closed(self):
        from backend.languages import short_feedback
        with patch('backend.interview.provider.json_completion', return_value={'summary': 'Input 1 par False sahi hai.'}):
            self.assertIn('False', short_feedback('False is correct for input 1.', 'hinglish'))
        with patch('backend.interview.provider.json_completion', return_value={'summary': 'Input 1 par True sahi hai.'}), self.assertRaises(ValueError):
            short_feedback('False is correct for input 1.', 'hinglish')
        with patch('backend.interview.provider.json_completion', return_value={'summary': 'This is still English.'}), self.assertRaises(ValueError):
            short_feedback('False is correct for input 1.', 'hinglish')

    def test_only_supported_language_codes(self):
        for value in (None, {}, 'xx', 'french', '<instructions>'):
            with self.assertRaises(StudyConflict): language_choice(value)

    def test_spelling_suggestion_does_not_correct_wrong_claim_negation_or_number(self):
        text = 'is crime input 1 par True return karta hai, loop nahi rukta.'
        checks = suggested_checks(text, [SOURCE])
        self.assertEqual(checks[0]['source_term'], 'is_prime')
        corrected = text.replace(checks[0]['heard'], checks[0]['source_term'])
        self.assertIn('True', corrected); self.assertIn('1', corrected); self.assertIn('nahi', corrected)
        unsafe = [{'content': ['def is_not_prime(number2): return True']}]
        self.assertFalse(suggested_checks('is prime number', unsafe))

    def test_prepared_questions_and_followups_preserve_code_quotes(self):
        from backend.interview.question_generator import _validate_questions
        packages = example.question_set([SOURCE], 3, 'hinglish')
        for package in packages:
            self.assertEqual(package['language'], 'hinglish'); self.assertIn('is_prime', package['question'])
            for criterion in package['rubric']: self.assertIn(criterion['quote'], example.CODE)
            followup = example.followup({'question': package['question'], 'question_package': package, 'snippets': [SOURCE]}, 'mixed answer')
            self.assertEqual(followup['language'], 'hinglish')
            _validate_questions({'questions': [followup]}, [SOURCE], 1)

    def test_short_feedback_language_prompt_and_malformed_summary_withhold_score(self):
        package = example.question_set([SOURCE], 1, 'hinglish')[0]
        response = {'summary': 'Early return sahi samjha; loop tak execution nahi pahunchta.', 'criteria': [{'id': r['id'], 'status': 'met', 'explanation': 'Reasoning sahi hai.'} for r in package['rubric']], 'claims': []}
        answer = '1 do se chhota hai, is_prime False return karke exit hota hai, loop nahi chalta.'
        with patch('backend.interview.grading.json_completion', return_value=response) as provider:
            result = grade_answer(package, answer, [SOURCE]); self.assertEqual(result['score']['percentage'], 100)
            self.assertIn('Roman-script Hinglish', provider.call_args.args[0]); self.assertIn(answer, provider.call_args.args[1])
            self.assertEqual(result['language'], 'hinglish')
        del response['summary']
        with patch('backend.interview.grading.json_completion', return_value=response), self.assertRaises(EvaluationError): grade_answer(package, answer, [SOURCE])


@unittest.skipUnless(pg.TEST_URL, 'Requires isolated PostgreSQL.')
class HinglishFlowTests(unittest.TestCase):
    setUpClass = classmethod(pg.PostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(pg.PostgresTests.tearDownClass.__func__)
    setUp = pg.PostgresTests.setUp

    def test_cache_language_boundary_feedback_followup_and_history_restore(self):
        source = self.client.post('/sources/example').get_json()
        def questions(language):
            r = self.client.post('/questions', json={'source_id': source['source_id'], 'language': language}); self.assertEqual(r.status_code, 200, r.get_json()); return r.get_json()
        english = questions('en'); hinglish = questions('hinglish')
        self.assertNotEqual(english['practice_id'], hinglish['practice_id'])
        self.assertEqual(questions('hinglish')['questions'], hinglish['questions'])
        q = hinglish['questions'][0]
        def grade(package, answer, snippets):
            self.assertEqual(package['language'], 'hinglish')
            response = {'summary': 'Early return ki wajah se loop nahi chalta.', 'criteria': [{'id': r['id'], 'status': 'met', 'explanation': 'Sahi reasoning.'} for r in package['rubric']], 'claims': []}
            with patch('backend.interview.grading.json_completion', return_value=response): return grade_answer(package, answer, snippets)
        with patch('backend.app.grade_answer', side_effect=grade):
            r = self.client.post('/answers', json={'turn_id': q['turn_id'], 'answer': '1 < 2 hai, isliye False return; loop nahi chalta.'})
        self.assertEqual(r.status_code, 200, r.get_json()); self.assertEqual(r.get_json()['language'], 'hinglish')
        child = self.client.post('/viva/turns/' + q['turn_id'] + '/follow-up').get_json()
        self.assertEqual(child['language'], 'hinglish')
        saved = self.client.get('/sources/current').get_json()['saved_practice']
        self.assertEqual(saved['questions'][0]['language'], 'hinglish'); self.assertIn('nahi', saved['results'][q['turn_id']]['summary'])
        self.assertEqual(self.client.post('/questions', json={'source_id': source['source_id'], 'language': 'de'}).status_code, 400)
        retry = self.client.post('/history/practice-sets/' + hinglish['practice_id'] + '/retry').get_json()
        self.assertTrue(all(item['language'] == 'hinglish' for item in retry['saved_practice']['questions']))
