from checks.auth_fixtures import authenticated_client
import io
import unittest
from unittest.mock import patch

from backend.app import app, turns
from backend.evidence.uploads import sources, SOURCE_TTL_SECONDS
from checks.test_source_uploads import pdf_bytes
from checks.quiz_fixtures import fake_question_set, fake_grade
from backend.interview.question_generator import QuestionGenerationError


class UploadedQuestionTests(unittest.TestCase):
    def setUp(self):
        sources.clear()
        turns.clear()
        self.client = authenticated_client(app)

    def tearDown(self):
        sources.clear()
        turns.clear()

    def upload(self, text, name='biology.txt'):
        if isinstance(text, str):
            text = text.encode()
        response = self.client.post('/sources', data={'source_file': (io.BytesIO(text), name)})
        self.addCleanup(response.close)
        self.addCleanup(response.request.environ['wsgi.input'].close)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_generation_and_retrieval_use_uploaded_content(self):
        source = self.upload('Photosynthesis converts light energy into chemical energy.')
        with patch('backend.app.generate_question_set', side_effect=fake_question_set) as generate:
            response = self.client.post('/questions', json={'source_id': source['source_id']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['source_id'], source['source_id'])
        self.assertEqual(generate.call_args.args[0][0]['content'], source['snippets'][0]['content'])
        self.assertNotIn('reference_answer', response.get_data(as_text=True))
        retrieved = self.client.post('/retrieve', json={'question': 'photosynthesis'})
        self.assertEqual(retrieved.get_json()['results'][0]['record']['path'], 'biology.txt')

    def test_no_upload_means_no_generation_or_sample_fallback(self):
        with patch('backend.app.generate_question_set') as generate:
            self.assertEqual(self.client.post('/questions').status_code, 400)
            self.assertEqual(self.client.post('/retrieve', json={'question': 'test'}).status_code, 400)
            generate.assert_not_called()

    def test_generation_failure_returns_specific_safe_error(self):
        self.upload('Study material.')
        error = QuestionGenerationError('The AI service is rate-limited. Please retry.', 'provider_rate_limit', 503)
        with patch('backend.app.generate_question_set', side_effect=error):
            response = self.client.post('/questions')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()['error_code'], 'provider_rate_limit')
        self.assertFalse(turns)

    def test_blank_chunks_are_skipped_without_losing_original_line_numbers(self):
        self.upload('\n' * 40 + 'Gravity attracts masses.')
        with patch('backend.app.generate_question_set', side_effect=fake_question_set) as generate:
            response = self.client.post('/questions')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(generate.call_args.args[0]), 1)
        self.assertEqual(generate.call_args.args[0][0]['start_line'], 41)

    def test_active_source_is_used_without_explicit_id(self):
        source = self.upload('Gravity attracts masses.')
        with patch('backend.app.generate_question_set', side_effect=fake_question_set) as generate:
            response = self.client.post('/questions')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['questions'][0]['source_id'], source['source_id'])
        self.assertIn('Gravity', generate.call_args.args[0][0]['content'][0])

    def test_replacement_preserves_existing_turn_snapshot(self):
        first = self.upload('Photosynthesis uses sunlight.')
        with patch('backend.app.generate_question_set', side_effect=fake_question_set) as generate:
            old = self.client.post('/questions', json={'source_id': first['source_id']}).get_json()['questions'][0]
            second = self.upload('The treaty was signed in 1919.', 'history.txt')
            new = self.client.post('/questions', json={'source_id': second['source_id']}).get_json()['questions'][0]
        self.assertEqual(generate.call_args_list[0].args[0][0]['path'], 'biology.txt')
        self.assertEqual(generate.call_args_list[1].args[0][0]['path'], 'history.txt')
        self.assertNotEqual(old['source_id'], new['source_id'])
        with patch('backend.app.grade_answer', side_effect=fake_grade) as grade:
            self.client.post('/answers', json={'turn_id': old['turn_id'], 'answer': 'Sunlight.'})
        self.assertEqual(grade.call_args.args[2][0]['path'], 'biology.txt')

    def test_missing_expired_and_foreign_uploads_never_fall_back(self):
        source = self.upload('Private notes.')
        with patch('backend.app.generate_question_set') as generate:
            self.assertEqual(authenticated_client(app).post('/questions', json={'source_id': source['source_id']}).status_code, 404)
            self.assertEqual(self.client.post('/questions', json={'source_id': 'missing'}).status_code, 404)
            sources[source['source_id']]['created'] -= SOURCE_TTL_SECONDS
            self.assertEqual(self.client.post('/questions').status_code, 404)
            generate.assert_not_called()

    def test_pdf_page_citations_survive_generation_and_evaluation(self):
        source = self.upload(pdf_bytes([None, 'Gravity attracts masses.']), 'physics.pdf')
        with patch('backend.app.generate_question_set', side_effect=fake_question_set) as generate:
            response = self.client.post('/questions', json={'source_id': source['source_id']})
        question = response.get_json()['questions'][0]
        self.assertEqual(question['evidence']['page'], 2)
        self.assertIsNone(question['evidence']['start_line'])
        self.assertEqual(generate.call_args.args[0][0]['page'], 2)
        with patch('backend.app.grade_answer', side_effect=fake_grade):
            result = self.client.post('/answers', json={'turn_id': question['turn_id'], 'answer': 'Masses.'})
        self.assertEqual(result.get_json()['evidence']['page'], 2)

    def test_another_browser_cannot_answer_uploaded_turn(self):
        source = self.upload('Private notes.')
        with patch('backend.app.generate_question_set', side_effect=fake_question_set):
            question = self.client.post('/questions', json={'source_id': source['source_id']}).get_json()['questions'][0]
        with patch('backend.app.grade_answer') as grade:
            self.assertEqual(authenticated_client(app).post('/answers', json={'turn_id': question['turn_id'], 'answer': 'x'}).status_code, 404)
            grade.assert_not_called()

    def test_current_source_restoration_and_multiple_chunks(self):
        source = self.upload('\n'.join(f'Concept {i}' for i in range(41)))
        self.assertEqual(self.client.get('/sources/current').get_json()['source_id'], source['source_id'])
        with patch('backend.app.generate_question_set', side_effect=fake_question_set) as generate:
            self.assertEqual(self.client.post('/questions').status_code, 200)
        self.assertEqual([item['start_line'] for item in generate.call_args.args[0]], [1, 41])
        self.client.delete('/sources/' + source['source_id'])
        self.assertEqual(self.client.get('/sources/current').status_code, 204)

    def test_invalid_ids_counts_and_oversized_context(self):
        with patch('backend.app.generate_question_set') as generate:
            for value in (None, '', [], 12):
                self.assertEqual(self.client.post('/questions', json={'source_id': value}).status_code, 400)
            source = self.upload('a' * 12001)
            self.assertEqual(self.client.post('/questions', json={'source_id': source['source_id']}).status_code, 422)
            for count in (0, 4, True, '3'):
                self.assertEqual(self.client.post('/questions', json={'source_id': source['source_id'], 'count': count}).status_code, 400)
            generate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
