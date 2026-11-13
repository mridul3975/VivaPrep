import unittest
from evaluation.metrics import agreement, errors, assessment_outcome, word_errors


class EvaluationTests(unittest.TestCase):
    def test_freeze_verification_allows_only_exact_line_ending_conversion(self):
        import hashlib
        import tempfile
        from pathlib import Path
        from evaluation.verify import frozen_bytes
        original = b'def identity(value):\r\n    return value\r\n'
        expected = hashlib.sha256(original).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'development.py'
            path.write_bytes(original.replace(b'\r\n', b'\n'))
            self.assertEqual(frozen_bytes(path, expected), original)
            path.write_bytes(b'def identity(value):\n    return None\n')
            self.assertIsNone(frozen_bytes(path, expected))

    def test_errors_stay_in_planned_denominator_and_are_not_false_accepts(self):
        rows = [
            {'id': 'development-positive', 'expected': 'supported', 'system': {'status': 'error'}},
            {'id': 'development-negative', 'expected': 'unsupported', 'system': {'status': 'ok', 'label': 'supported'}},
            {'id': 'development-missing', 'expected': 'partial'},
        ]
        self.assertEqual(agreement(rows, 'system', 'expected', 'label'), {'agreed': 0, 'planned': 3, 'completed': 1, 'errors_or_missing': 2})
        outcome = errors(rows, 'system', 'supported')
        self.assertEqual(outcome['incorrect_acceptances'], ['development-negative'])
        self.assertEqual(outcome['positive_cases_without_verdict'], ['development-positive'])
        self.assertEqual(outcome['incorrect_rejections'], [])

    def test_contradiction_blocks_acceptance_even_when_rubric_marked_met(self):
        result = {'criteria': [{'id':'c1','status':'met'},{'id':'c2','status':'met'}], 'claims':[{'label':'contradicted'}]}
        self.assertFalse(assessment_outcome(result)['accepted'])
        self.assertEqual(assessment_outcome(result)['label'], 'contradicted')
        result['criteria'].pop()
        with self.assertRaises(ValueError): assessment_outcome(result)

    def test_wer_keeps_negation_and_counts_insertions_deletions_and_substitutions(self):
        self.assertEqual(word_errors('do not return two', 'do return 2')['edits'], 2)
        self.assertEqual(word_errors('नहीं आता', 'नहीं आता')['edits'], 0)
        self.assertEqual(word_errors('नहीं आता।', 'नहीं आता.')['edits'], 0)
        self.assertEqual(word_errors('hello', 'hello extra')['edits'], 1)

    def test_public_report_does_not_expose_arbitrary_files_or_require_signin(self):
        from backend.app import app
        with app.test_client() as client:
            with client.get('/evaluation') as response:
                self.assertEqual(response.status_code, 200)
                self.assertIn('independent human review', response.get_data(as_text=True))
            for path in ('/evaluation/data/.env', '/evaluation/data/run.py', '/evaluation/data/../.env', '/evaluation/data/audio/S99.wav'):
                with client.get(path) as response: self.assertEqual(response.status_code, 404)
            with client.get('/evaluation/data/dataset.json') as response:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.get_json()['assessment']), 16)
