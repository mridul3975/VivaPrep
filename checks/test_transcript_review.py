import unittest
from unittest.mock import patch
from checks import test_postgres as pg
from checks.quiz_fixtures import fake_grade
from backend.speech.review import suggested_checks, store_review


class TermReviewTests(unittest.TestCase):
    def test_source_hint_never_changes_transcript_or_claims_confidence(self):
        source=[{'content':['def is_prime(number):','    return number > 1']}]
        checks=suggested_checks('is crime returns True',source)
        self.assertEqual(checks[0]['heard'],'is crime')
        self.assertEqual(checks[0]['source_term'],'is_prime')
        self.assertEqual(suggested_checks('is_prime returns True',source),[])
        self.assertNotIn('confidence',checks[0])


@unittest.skipUnless(pg.TEST_URL,'Requires isolated PostgreSQL.')
class TranscriptReviewTests(unittest.TestCase):
    setUpClass=classmethod(pg.PostgresTests.setUpClass.__func__)
    tearDownClass=classmethod(pg.PostgresTests.tearDownClass.__func__)
    setUp=pg.PostgresTests.setUp
    upload=pg.PostgresTests.upload
    question=pg.PostgresTests.question

    def prepare(self):
        source=self.upload(b'def is_prime(n):\n    return n > 1','prime.py')
        q=self.question(source['source_id'])
        with self.client.application.app_context():
            review=store_review('google:db-one',q['turn_id'],'is crime returns True',q['evidence_snippets'])
        return source,q,review

    def test_confirmed_final_answer_only_is_graded_original_is_restored(self):
        source,q,review=self.prepare()
        metadata={'receipt_id':review['receipt_id'],'reviewed':False}
        body={'turn_id':q['turn_id'],'answer':'is_prime returns True','speech_review':metadata}
        self.assertEqual(self.client.post('/answers',json=body).status_code,400)
        metadata['reviewed']=True
        with patch('backend.app.grade_answer',side_effect=fake_grade) as grader:
            response=self.client.post('/answers',json=body)
        self.assertEqual(response.status_code,200,response.get_json())
        self.assertEqual(grader.call_args.args[1],body['answer'])
        audit=response.get_json()['speech_review']
        self.assertEqual(audit['original_transcript'],'is crime returns True');self.assertTrue(audit['corrections_made'])
        restored=self.client.get('/sources/current').get_json()['saved_practice']['results'][q['turn_id']]
        self.assertEqual(restored['speech_review'],audit)

    def test_unconfirmed_draft_persists_and_typed_opt_out_clears_review(self):
        source,q,review=self.prepare();url='/history/turns/'+q['turn_id']+'/draft'
        body={'answer':'edited','speech_review':{'receipt_id':review['receipt_id'],'reviewed':False}}
        self.assertEqual(self.client.put(url,json=body).status_code,200)
        saved=self.client.get('/sources/current').get_json()['saved_practice']
        self.assertFalse(saved['speech_reviews'][q['turn_id']]['reviewed'])
        self.assertEqual(saved['speech_reviews'][q['turn_id']]['original_transcript'],'is crime returns True')
        self.client.put(url,json={'answer':'typed'})
        self.assertEqual(self.client.get('/sources/current').get_json()['saved_practice']['speech_reviews'],{})

    def test_other_owner_forged_original_and_stale_receipt_are_rejected(self):
        source,q,review=self.prepare()
        body={'turn_id':q['turn_id'],'answer':'final','speech_review':{'receipt_id':review['receipt_id'],'reviewed':True}}
        self.assertEqual(self.other.post('/answers',json=body).status_code,404)
        body['speech_review']['original_transcript']='forged'
        self.assertEqual(self.client.post('/answers',json=body).status_code,400)
        del body['speech_review']['original_transcript']
        with self.client.application.app_context():store_review('google:db-one',q['turn_id'],'new transcript',q['evidence_snippets'])
        self.assertEqual(self.client.post('/answers',json=body).status_code,409)
