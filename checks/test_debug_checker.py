"""Repair comparison preserves significant whitespace and accepts equivalent Python ASTs."""
import unittest
from unittest.mock import patch
from backend.interview.debug_checker import check_solution, matches_reference


