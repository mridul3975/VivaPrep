"""Guard against substituted projects, fabricated source and unusable plans."""
import copy
import unittest
from unittest.mock import patch
from backend.evidence.documents import extract_document
from backend.interview.debug_generator import generate_debug_challenge, source_excerpt
from backend.debugging import same_json
from checks.debug_fixtures import CODE, completion


class DebugGeneratorTests(unittest.TestCase):
    def document(self, code=CODE, filename='tax.js'):
        return extract_document(filename, code.encode())

    def generate(self, data, document=None):
        with patch('backend.interview.debug_generator.json_completion', return_value=data):
            return generate_debug_challenge(document or self.document())

    def test_exact_source_snapshot_and_mutation(self):
        data = self.generate(completion())
        self.assertEqual(data['project'], 'tax.js')
        self.assertEqual(data['reference_code'], CODE)
        self.assertEqual(data['starter_code'], CODE.replace('+', '-'))
        self.assertEqual(data['function_name'], 'addTax')
        self.assertEqual(data['tests'][0]['expected'], 15)
        self.assertEqual(data['source']['start_line'], 1)
        self.assertEqual(len(data['_hints']), 3)

    def test_cannot_substitute_invented_function_or_invalid_lines(self):
        for changes in ({'replace_original': 'validateRecording'}, {'line_start': 0}, {'line_end': 99},
                        {'replace_broken': 'amount + 5'}, {'function_name': 'fakeFunction'}, {'hints': []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.generate({**completion(), **changes})

    def test_python_has_local_verification_and_real_source(self):
        data = {**completion(), 'function_name': '', 'tests': [], 'replace_original': 'amount + 5', 'replace_broken': 'amount - 5', 'line_end': 2}
        exercise = self.generate(data, self.document('def add_tax(amount):\n    return amount + 5', 'tax.py'))
        self.assertEqual(exercise['language'], 'Python')
        self.assertEqual(exercise['execution_mode'], 'local')
        self.assertEqual(exercise['tests'], [])
        self.assertIn('def add_tax', exercise['starter_code'])

    def test_python_changed_line_alone_is_not_a_debugging_function(self):
        data = {**completion(), 'function_name': '', 'tests': [], 'line_start': 2, 'line_end': 2}
        with self.assertRaises(ValueError):
            self.generate(data, self.document('def add_tax(amount):\n    return amount + 5', 'tax.py'))

    def test_notes_and_unknown_sections_rejected_before_provider_call(self):
        with patch('backend.interview.debug_generator.json_completion') as provider:
            with self.assertRaises(ValueError):
                generate_debug_challenge(self.document(filename='notes.md'))
            with self.assertRaises(ValueError):
                generate_debug_challenge(self.document(), 'other-file:1')
            provider.assert_not_called()

    def test_chunks_keep_global_lines_and_include_adjacent_code(self):
        doc = self.document('\n'.join(['// header'] * 40 + CODE.splitlines()))
        language, first, lines = source_excerpt(doc, doc['snippets'][1]['id'])
        self.assertEqual(language, 'JavaScript'); self.assertEqual(first, 41)
        self.assertEqual('\n'.join(lines), CODE)
        data = self.generate({**completion(), 'line_start': 41, 'line_end': 43}, doc)
        self.assertEqual(data['reference_code'], CODE)

    def test_repeated_substring_and_invalid_json_are_rejected(self):
        with self.assertRaises(ValueError):
            self.generate({**completion(), 'line_end': 4}, self.document(CODE + '\n// amount + 5'))
        data = copy.deepcopy(completion()); data['tests'][0]['args_json'] = '[NaN]'
        with self.assertRaises(ValueError):
            self.generate(data)

    def test_json_verdict_keeps_booleans_distinct_and_compares_objects(self):
        self.assertFalse(same_json(True, 1))
        self.assertTrue(same_json({'b': [1.0], 'a': None}, {'a': None, 'b': [1]}))
