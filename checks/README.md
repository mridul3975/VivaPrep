# Running checks

Run these commands from the project root with the project virtual environment active.

## Local regression tests

```sh
python -m unittest discover -s checks -p 'test_*.py' -v
```

These tests simulate provider responses and do not make live API calls.

## Live provider checks

Run these individually. They make real provider requests and may consume credits.

```sh
python -m checks.live.question_generation
python -m checks.live.question_endpoint
python -m checks.live.evaluation
python -m checks.live.transcription samples/test.wav
```

The question and evaluation scripts read `GROQ_API_KEY` from the environment or
the root `.env` file. The transcription script expects `VACHANA_API_KEY` to be set
in the terminal environment. Importing these modules does not execute requests.

`live_flow_result.json` records the earlier live end-to-end run; it is a saved
result, not a test that executes automatically.
