"""Follow-ups use owned submitted answers, immutable evidence and bounded quotas."""
import unittest
from unittest.mock import patch
from checks import test_postgres as pg
from checks.quiz_fixtures import fake_question_set, fake_grade
from backend.app import app
from backend.interview.followup import generate_followup
from backend.interview.provider import ProviderError


@unittest.skipUnless(pg.TEST_URL, 'Requires isolated PostgreSQL.')
class VivaTests(unittest.TestCase):
    setUpClass = classmethod(pg.PostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(pg.PostgresTests.tearDownClass.__func__)
    setUp = pg.PostgresTests.setUp
    upload = pg.PostgresTests.upload
    question = pg.PostgresTests.question
    answer = pg.PostgresTests.answer

    def prepare(self):
        source = self.upload(b'def add_tax(x):\n    return x + 5', 'tax.py')
        question = self.question(source['source_id'])
        return source,question,'/viva/turns/'+question['turn_id']+'/follow-up'

    def completion(self, parent, answer):
        self.assertEqual(answer, 'It adds five to the amount.')
        package = fake_question_set(parent['snippets'],1)[0]
        return {**package,'question':'For input zero, which value is returned and why?'}

    def test_requires_auth_ownership_submitted_answer_and_csrf(self):
        source,q,url = self.prepare()
        self.assertEqual(app.test_client().post(url).status_code,401)
        self.assertEqual(self.other.post(url).status_code,404)
        self.assertEqual(self.client.post(url).status_code,409)
        csrf=self.client.environ_base.pop('HTTP_X_CSRF_TOKEN')
        self.assertEqual(self.client.post(url).status_code,403)
        self.client.environ_base['HTTP_X_CSRF_TOKEN']=csrf
        self.assertEqual(self.client.post(url,json={'answer':'Use forged answer'}).status_code,400)

    def test_answer_bound_citation_hidden_reference_cache_order_and_no_chain(self):
        source,q,url=self.prepare();self.answer(q['turn_id'],'It adds five to the amount.')
        before=self.client.get('/profile').get_json()['usage']['allowances']['questions']['used']
        with patch('backend.viva.generate_followup',side_effect=self.completion) as provider:
            response=self.client.post(url);self.assertEqual(response.status_code,201,response.get_json())
            child=response.get_json()
            self.assertNotIn('reference_answer',child);self.assertEqual(child['parent_answer'],'It adds five to the amount.')
            self.assertEqual(child['parent_turn_id'],q['turn_id']);self.assertEqual(child['evidence_snippets'],q['evidence_snippets'])
            self.assertEqual(self.client.post(url).get_json()['turn_id'],child['turn_id']);self.assertEqual(provider.call_count,1)
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['questions']['used'],before+1)
        self.assertEqual(self.client.post('/viva/turns/'+child['turn_id']+'/follow-up').status_code,400)
        practice=self.client.get('/sources/current').get_json()['saved_practice']
        self.assertEqual([item['turn_id'] for item in practice['questions']],[q['turn_id'],child['turn_id']])
        self.assertEqual(practice['resume_turn_id'],child['turn_id'])
        self.answer(child['turn_id'],'Five.');self.assertIn(child['turn_id'],self.client.get('/sources/current').get_json()['saved_practice']['results'])

    def test_provider_failure_refunds_and_releases_parent(self):
        source,q,url=self.prepare();self.answer(q['turn_id'],'It adds five to the amount.')
        before=self.client.get('/profile').get_json()['usage']['allowances']['questions']['used']
        for error in (ProviderError('Unavailable'),ValueError('Bad citation')):
            with patch('backend.viva.generate_followup',side_effect=error):
                self.assertEqual(self.client.post(url).status_code,502)
        self.assertEqual(self.client.get('/profile').get_json()['usage']['allowances']['questions']['used'],before)
        with patch('backend.viva.generate_followup',side_effect=self.completion):
            self.assertEqual(self.client.post(url).status_code,201)

    def test_prepared_example_free_and_persisted_after_root(self):
        source=self.client.post('/sources/example').get_json()
        roots=self.client.post('/questions',json={'source_id':source['source_id']}).get_json()['questions']
        with patch('backend.app.grade_answer', side_effect=fake_grade):
            self.assertEqual(self.client.post('/answers',json={'turn_id':roots[0]['turn_id'],'answer':'The early return exits before the loop.'}).status_code, 200)
        with patch('backend.viva.generate_followup') as provider:
            child=self.client.post('/viva/turns/'+roots[0]['turn_id']+'/follow-up').get_json()
            provider.assert_not_called()
        self.assertIn('is_prime(9)',child['question'])
        self.assertIn('explain',child['question'])
        saved=self.client.get('/sources/current').get_json()['saved_practice']
        self.assertEqual([item['turn_id'] for item in saved['questions']],[roots[0]['turn_id'],child['turn_id'],roots[1]['turn_id'],roots[2]['turn_id']])


class FollowupValidationTests(unittest.TestCase):
    def test_prompt_contains_answer_and_rejects_fabricated_citation(self):
        snippets=[{'id':'source:1','path':'tax.py','start_line':1,'end_line':2,'content':['def tax(x):','    return x + 5']}]
        parent={'question':'What does tax do?','snippets':snippets}
        package={'question':'Why does input zero return five?','reference_answer':'It adds five.','rubric':[{'description':'Trace the return','snippet_id':'source:1','line_start':2,'line_end':2}]}
        with patch('backend.interview.followup.json_completion',return_value={'questions':[package]}) as provider:
            result=generate_followup(parent,'I think it subtracts five.')
            self.assertEqual(result['rubric'][0]['quote'],'    return x + 5')
            self.assertIn('I think it subtracts five.',provider.call_args.args[1])
        package['rubric'][0]['line_end']=20
        with patch('backend.interview.followup.json_completion',return_value={'questions':[package]}):
            with self.assertRaises(ValueError):generate_followup(parent,'some answer')
