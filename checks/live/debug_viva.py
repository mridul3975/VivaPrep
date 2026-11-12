"""Opt-in live Groq check; uses two requests, no database or learner records."""
import json
from pathlib import Path
from dotenv import load_dotenv
from backend import example
from backend.interview.debug_viva import evaluate_defense

load_dotenv()
exercise = example.challenge({'filename': example.FILENAME})
state = {'scenario': exercise, 'code': exercise['reference_code'],
         'explanation': 'The strict < loop skips a divisor when its square equals the input. Changing it to <= checks that boundary, so perfect squares are rejected by the divisibility check.',
         'failing_input': 'For 9 the broken loop checks 2, increments to 3, then stops because 9 < 9 is false and returns True. With <= it checks 3, finds remainder zero and returns False.'}
correct = evaluate_defense(state)
assert correct['passed'] and correct['score'] == 100, correct
incorrect = evaluate_defense({**state, 'explanation': 'The code failed because it subtracts tax. I changed it to addition.',
                              'failing_input': 'For 2, the broken function returns False and the repaired function returns 100.'})
assert not incorrect['passed'] and incorrect['score'] < 100, incorrect
result = {'status': 'passed', 'provider': 'Live Groq', 'correct_score': correct['score'],
          'incorrect_score': incorrect['score'], 'correct_feedback': correct, 'incorrect_feedback': incorrect,
          'boundary': 'Static reasoning and validated code citations. This does not execute Python or verify live microphone/STT.'}
Path('checks/debug_viva_live_result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(f"Live Groq: correct defense {correct['score']}/100; conflicting defense {incorrect['score']}/100; all citations validated.")
