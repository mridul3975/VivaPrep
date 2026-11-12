"""Opt-in live Groq check: subjective generation and explanation grading, no DB."""
import json
from pathlib import Path
from dotenv import load_dotenv
from backend import example
from backend.interview.question_generator import generate_question_set
from backend.interview.grading import grade_answer

load_dotenv()
source = {'id': 'prime:1', 'path': example.FILENAME, 'start_line': 1, 'end_line': 10,
          'content': example.CODE.rstrip('\n').splitlines()}
questions = generate_question_set([source], count=2)
package = example.question_set([source], 1)[0]
bare = grade_answer(package, 'False', [source])
reasoned = grade_answer(package, 'The input 1 is smaller than 2, so the initial condition holds and the function returns False immediately. A return exits the function, so divisor initialization and the loop are never reached.', [source])
assert bare['score']['percentage'] == 0, bare
assert reasoned['score']['percentage'] == 100, reasoned
result = {'status': 'passed', 'provider': 'Live Groq', 'generated_questions': questions,
          'bare_boolean': bare, 'reasoned_answer': reasoned,
          'boundary': 'Live subjective generation and rubric grading; no DB, user recordings or live STT.'}
Path('checks/subjective_questions_live_result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(f"Live Groq: {len(questions)} open-ended questions validated; bare False scored 0/100; reasoned answer scored 100/100.")
