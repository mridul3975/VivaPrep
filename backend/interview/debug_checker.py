"""Compare practice repairs with their source; review alternatives without executing them."""
import ast
import json
import textwrap
from backend.interview.provider import json_completion, object_schema


def matches_reference(code, reference, language):
    # Preserve indentation and whitespace inside strings. Never strip all whitespace.
    if code.replace('\r\n', '\n').strip('\n') == reference.replace('\r\n', '\n').strip('\n'):
        return True
    if language.lower() == 'python':
        try:
            return ast.dump(ast.parse(textwrap.dedent(code))) == ast.dump(ast.parse(textwrap.dedent(reference)))
        except (SyntaxError, ValueError, RecursionError):
            return False
    return False


def check_solution(code, exercise):
    reference = exercise['reference_code']
    if matches_reference(code, reference, exercise['language']):
        return {'verdict': 'correct', 'score': 100, 'method': 'reference',
                'explanation': 'Correct! You restored the uploaded implementation. This verifies the practice repair by source comparison; it does not execute the code.'}
    if code.replace('\r\n', '\n').strip('\n') == exercise['starter_code'].replace('\r\n', '\n').strip('\n'):
