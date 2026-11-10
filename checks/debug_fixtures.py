"""Source-specific provider responses for deterministic debugging checks."""
from unittest.mock import patch
from backend.interview.debug_generator import generate_debug_challenge

CODE = 'function addTax(amount) {\n  return amount + 5;\n}'


def completion(*_args, **_kwargs):
    return {
        'title': 'The total loses its tax', 'contract': 'addTax(amount) adds a fixed tax of 5. addTax(10) must return 15.',
        'line_start': 1, 'line_end': 3, 'replace_original': 'amount + 5', 'replace_broken': 'amount - 5',
        'function_name': 'addTax', 'hints': ['Trace the total.', 'Compare the arithmetic.', 'The tax should increase the total.'],
        'tests': [{'name': f'Amount {amount}', 'args_json': f'[{amount}]', 'expected_json': str(amount + 5)} for amount in (10, 0, 20)],
        'verification_steps': ['Call addTax(10); expect 15.', 'Call addTax(0); expect 5.'],
    }


def challenge(document, snippet_id=None):
    with patch('backend.interview.debug_generator.json_completion', side_effect=completion):
        return generate_debug_challenge(document, snippet_id)
