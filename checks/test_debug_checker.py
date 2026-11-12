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
