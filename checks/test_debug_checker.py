"""Repair comparison preserves significant whitespace and accepts equivalent Python ASTs."""
import unittest
from unittest.mock import patch
from backend.interview.debug_checker import check_solution, matches_reference


class DebugCheckerTests(unittest.TestCase):
    def test_python_formatting_and_comments_preserve_behavior(self):
        self.assertTrue(matches_reference('def f(x):\n    return x+5 # repaired', 'def f(x):\n    return x + 5', 'Python'))
        self.assertFalse(matches_reference('def f(x):\n    return "a b"', 'def f(x):\n    return "ab"', 'Python'))
        self.assertFalse(matches_reference('def f(:', 'def f(x):\n    return x', 'Python'))
        self.assertFalse(matches_reference('function f(){return "a b"}', 'function f(){return "ab"}', 'JavaScript'))

    def test_direct_repairs_do_not_call_provider_and_uncertain_has_no_score(self):
        exercise = {'language': 'Python', 'contract': 'Add five', 'reference_code': 'def f(x):\n    return x + 5', 'starter_code': 'def f(x):\n    return x - 5'}
        with patch('backend.interview.debug_checker.json_completion') as provider:
            self.assertEqual(check_solution(exercise['reference_code'], exercise)['score'], 100)
            self.assertEqual(check_solution(exercise['starter_code'], exercise)['score'], 0)
            provider.assert_not_called()
            provider.return_value = {'verdict': 'uncertain', 'explanation': 'Missing dependency context.'}
            result = check_solution('def f(x):\n    return helper(x)', exercise)
            self.assertIsNone(result['score'])
            self.assertEqual(result['method'], 'ai_review')
            provider.return_value = {'verdict': 'correct', 'explanation': ''}
            with self.assertRaises(ValueError):
                check_solution('different', exercise)
