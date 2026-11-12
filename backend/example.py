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
QUESTION_VERSION = 'prime-explain-v2'


def is_example(document):
    return document.get('prepared_example') == 'prime-v1' and '\n'.join(document['snippets'][0]['content']).rstrip('\n') == CODE.rstrip('\n')


def question_set(snippets, count):
    cases = [
        ('Explain how is_prime handles numbers below 2. Walk through input 1 and explain why the loop is never reached.',
         'For 1 the number < 2 condition is true, so the function immediately returns False. The return exits the function before divisor initialization or the loop.',
         [('Explain the early return for inputs below 2, using input 1.', 3, 4), ('Explain why that return prevents the loop from running.', 3, 6)]),
        ('Walk through is_prime(2). Explain why it returns True even though the loop body never runs.',
         'The input 2 does not satisfy number < 2. divisor starts at 2, and 2 * 2 <= 2 is false, so the loop is skipped. Execution reaches return True.',
         [('Explain why input 2 passes the initial guard.', 3, 4), ('Trace the initial divisor, false loop condition, and final return.', 5, 10)]),
        ('Trace is_prime(9) through the loop. Explain how the function finds a divisor and why the loop condition includes equality.',
         'divisor starts at 2; 4 <= 9 is true and 9 % 2 is nonzero, so divisor becomes 3. Since 3 * 3 <= 9 includes equality, divisor 3 is tested. 9 % 3 is zero, so the function returns False. Without equality, that square-root divisor would be skipped.',
         [('Trace divisor 2 and the increment to 3.', 5, 9), ('Explain the equality boundary and the return when divisor 3 divides 9.', 6, 8)]),
    ]
    return [_package(snippets, question, reference, criteria) for question, reference, criteria in cases[:count]]


def _package(snippets, question, reference, criteria):
    return {'question': question, 'reference_answer': reference, 'prepared_example': QUESTION_VERSION,
            'rubric': [{'id': f'c{index}', 'description': description, 'snippet_id': snippets[0]['id'],
                        'line_start': start, 'line_end': end, 'quote': '\n'.join(snippets[0]['content'][start - 1:end])}
                       for index, (description, start, end) in enumerate(criteria, 1)]}


def current_practice(practice):
    # Keep historical Boolean practice accessible in History, but start the new demo fresh.
    if practice and all(item.get('prepared_example') == QUESTION_VERSION for item in practice['questions']):
        return practice
    return None


def grade(package, answer, snippets):
    # Compatibility only for explicitly reopened historical prime-v1 turns.
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


def followup(turn, answer):
    if 'below 2' in turn['question'] or 'loop body never runs' in turn['question']:
        return _package(turn['snippets'], 'Contrast your earlier explanation with is_prime(9). Trace the divisor checks and explain why equality in the loop condition matters.',
                        question_set(turn['snippets'], 3)[2]['reference_answer'],
                        [('Trace divisor 2 and the increment to 3.', 5, 9), ('Explain why equality allows divisor 3 to reject 9.', 6, 8)])
    return _package(turn['snippets'], 'Building on your trace, explain why is_prime(17) reaches the final return. Walk through the candidate divisors and the stopping condition.',
                    'For 17, divisors 2, 3 and 4 are checked and each leaves a nonzero remainder. divisor then becomes 5; 25 <= 17 is false. No divisor caused an early return, so the final return True is reached.',
                    [('Trace the tested divisors and their nonzero remainders.', 5, 9), ('Explain why divisor 5 stops the loop and execution returns True.', 6, 10)])
