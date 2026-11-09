# Running checks

Run these commands from the project root with the project virtual environment active.

## Local regression tests

```sh
python -m unittest discover -s checks -p 'test_*.py' -v
```

These tests simulate provider responses and do not make live API calls.
Authentication tests verify locally signed fixture tokens using Google's real
verifier; they do not sign in to a real Google account. Existing feature tests
seed authenticated local test sessions using `auth_fixtures.py`. There is no
production authentication bypass.
The production-serving checks require the React build first. On a fresh checkout,
run `npm --prefix frontend ci` and `npm --prefix frontend run build` before the
test command.

## PostgreSQL integration tests

Ordinary feature tests explicitly use memory storage so a configured application
`DATABASE_URL` is not used for their fixtures. PostgreSQL checks are opt-in:

```sh
python -m unittest checks.test_postgres -v
```

Set `TEST_DATABASE_URL` in the terminal environment to an isolated PostgreSQL
database named **`repoviva_test`** before running that command. The fixture refuses
any other database name, applies migrations and truncates its test tables between
cases. Never use the application's local or hosted database URL. The development
fixture uses a separate PostgreSQL instance on port 55432; the application uses
its durable local database on port 5432. Without `TEST_DATABASE_URL`, these tests
skip. The CLI configuration is described in [POSTGRES.md](../POSTGRES.md).

The checks exercise real PostgreSQL transactions, idempotent migrations,
fresh-Python-process restoration of an unexpired login and saved practice,
private unsubmitted references, ownership, archival replacement, cascading
deletion, history, evaluation leases and safe database failures. They use fixture
Google identities and simulated AI responses. They do not establish real Google
sign-in, a live provider round trip, or a deployed Render service.

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
The local question-endpoint and evaluation harnesses also seed an authenticated
test identity; they exercise live AI providers, not live Google authentication.

`live_flow_result.json` records an older claim-only flow; the current scored flow
is exercised by `checks.live.evaluation`. The JSON is an historical saved result,
not a test that executes automatically.

`live_study_flow_result.json` records the live browser verification of uploaded
biology, history, and PDF material with question sets, hidden references, scoring,
and file switching on November 9. It is a recorded result, not an automated test.

`ui_redesign_result.json` records the silver/charcoal redesign checks. The UI matrix
uses real uploads, simulated AI/STT responses, and a fake microphone to cover
states consistently. A separate real browser flow with `guide.pdf` exercised
Groq question generation and grading. Screenshots and the local browser harness
are development artifacts under the ignored `.impeccable/review/` directory.

`orbs_ui_result.json` records the November 10 Finora/Meridial-inspired refinement
and native Thinking Orbs checks. The browser matrix uses real uploads, simulated
AI/STT responses, and a fake microphone. Pixel comparisons verify idle pausing,
active animation, reduced-motion rendering, and offscreen pausing. This pass
does not repeat the separately recorded live-provider flow.

`authentication_result.json` records Google-only authentication checks. Its
browser matrix uses an isolated Flask fixture with locally signed identity
tokens and a stub Google SDK/certificate response. A real Google account sign-in
remains a separate check after configuring the actual OAuth client ID and origin.
