"""Compare practice repairs with their source; review alternatives without executing them."""
import ast
import json
import textwrap
from backend.interview.provider import json_completion, object_schema


def matches_reference(code, reference, language):
    # Preserve indentation and whitespace inside strings. Never strip all whitespace.
    if code.replace('\r\n', '\n').strip('\n') == reference.replace('\r\n', '\n').strip('\n'):
        return True
