# Running checks

Run these commands from the project root with the project virtual environment active.

## Local regression tests

```sh
python -m unittest discover -s checks -p 'test_*.py' -v
```

These tests simulate provider responses and do not make live API calls.
The production-serving checks require the React build first. On a fresh checkout,
run `npm --prefix frontend ci` and `npm --prefix frontend run build` before the
test command.

## Live provider checks

Run these individually. They make real provider requests and may consume credits.

```sh
python -m checks.live.question_generation path/to/material.txt
python -m checks.live.question_endpoint path/to/material.pdf
python -m checks.live.evaluation path/to/material.txt --answer "Your answer"
python -m checks.live.transcription samples/test.wav
```

The question and evaluation scripts read `GROQ_API_KEY` from the environment or
the root `.env` file. The transcription script expects `VACHANA_API_KEY` to be set
in the terminal environment. Importing these modules does not execute requests.

`live_flow_result.json` records an older claim-only flow; the current scored flow
is exercised by `checks.live.evaluation`. The JSON is an historical saved result,
not a test that executes automatically.

`live_study_flow_result.json` records the live browser verification of uploaded
biology, history, and PDF material with question sets, hidden references, scoring,
and file switching on November 9. It is a recorded result, not an automated test.
