"""An explicitly prepared, provider-free Python demo shared by Study and Debug."""
import re
from backend.interview.debug_generator import SOURCE_SCENARIO_ID

CODE = '''def is_prime(number):
    """Return True when number is a prime integer."""
    if number < 2:
        return False
    divisor = 2
    while divisor * divisor <= number:
        if number % divisor == 0:
            return False
        divisor += 1
    return True
'''
FILENAME = 'example_prime.py'


def is_example(document):
    return document.get('prepared_example') == 'prime-v1' and '\n'.join(document['snippets'][0]['content']).rstrip('\n') == CODE.rstrip('\n')


def question_set(snippets, count):
    cases = [(1, False, 3, 4), (2, True, 10, 10), (9, False, 6, 8)]
    return [{'question': f'Prepared Python example: What does is_prime({number}) return? Answer True or False.',
             'reference_answer': f'False' if not expected else 'True', 'prepared_example': 'prime-v1',
             'rubric': [{'id': 'result', 'description': f'Identify the return value for {number}.', 'snippet_id': snippets[0]['id'],
                        'line_start': start, 'line_end': end, 'quote': '\n'.join(snippets[0]['content'][start-1:end])}]}
            for number, expected, start, end in cases[:count]]


def grade(package, answer, snippets):
    # This prepared quiz intentionally asks a Boolean answer, not free-form reasoning.
    text = answer.strip().lower().rstrip('.! ')
    match = re.fullmatch(r'(?:(?:it |the function )?(?:returns? |is ))?(true|false)', text)
    correct = bool(match and match[1] == package['reference_answer'].lower())
    expected = package['rubric'][0]
    explanation = 'Correct return value.' if correct else 'For this prepared demo, answer True or False. The source establishes the return value shown below.'
    return {'reference_answer': package['reference_answer'], 'claims': [],
            'criteria': [{**expected, 'status': 'met' if correct else 'missed', 'points': int(correct), 'max_points': 1,
                          'explanation': explanation, 'evidence': snippets[0]}],
            'score': {'earned': int(correct), 'possible': 1, 'percentage': 100 if correct else 0, 'excluded_criteria': 0}}


def challenge(document):
    return {'id': SOURCE_SCENARIO_ID, 'title': 'Prime checker accepts a perfect square', 'project': document['filename'], 'language': 'Python',
            'starter_code': CODE.replace('divisor * divisor <= number', 'divisor * divisor < number').rstrip('\n'),
            'reference_code': CODE.rstrip('\n'), 'function_name': '', 'execution_mode': 'local', 'tests': [],
            'contract': 'Prepared example: is_prime should return False for 1 and 9, and True for 2 and 17. Repair the loop so a square such as 9 is not accepted as prime.',
            'verification_steps': [], 'source': {'filename': document['filename'], 'start_line': 1, 'end_line': 10},
            'provenance': 'Prepared Python example with one deliberate practice change. No AI request is used to create this exercise.',
            '_hints': ['Trace the loop for number = 9 and divisor = 3.', 'The loop must test a divisor whose square equals the number.', 'Inspect whether the loop comparison includes equality.']}
