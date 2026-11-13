# Running checks

Run these commands from the project root with the project virtual environment active.

The separate [40-case evaluation candidate](../evaluation/README.md) is available
at `/evaluation`. Its frozen cases are excluded from development examples here.
Live observations, errors, the general-assistant baseline and a pending human
review sheet are inspectable. Run `python -m unittest checks.test_evaluation -v`
for its offline metric and public-route checks; those are not benchmark cases.

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

After configuring `E2B_API_KEY`, `python -m checks.live.incidents` creates three
real short-lived sandboxes for the prepared booking original/failure/repair.
It is opt-in, uses provider credits, and is separate from offline incident tests.
See [INCIDENTS.md](../INCIDENTS.md) before running it. Cloud execution remains
unverified until that check or the actual E2B-backed browser flow succeeds.

### Neon deployment check

After `neon deploy`, migrations and `npm run build`, start the app with the
project Python environment active using `python -m backend.start`. In a second
terminal, run:

```sh
python -m checks.live.neon prepare --base-url http://127.0.0.1:8000
# Restart the application server, retaining its environment and session secret.
python -m checks.live.neon resume --base-url http://127.0.0.1:8000
```

This uses real Neon storage and live Groq calls, which may consume credits. It
creates one uniquely named verification identity with a signed app session;
it does not bypass the production routes or exercise a real Google account.
It verifies upload, generated questions, scored answers, history, session and
practice restoration after restart, source removal, and logout. The resume
phase removes its synthetic identity and records and writes `neon_result.json`.
Its cookie checkpoint stays in the ignored `.impeccable/review/neon/` directory.
No existing users or study data are truncated.

### Individual providers

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

History/profile checks: `checks/test_history_profile.py` verifies real PostgreSQL
ownership, draft restoration, byte-hash reuse, cached practice, deletion, UTC
reset, failure refunds and concurrent allowance enforcement. Use the dedicated
repoviva_test database; these tests must never point at production.

Debugging checks: `checks/test_debug_generator.py` rejects fabricated source,
invalid edits and incomplete Python excerpts. `checks/test_debugging.py` verifies
owned source-specific runs, hints, CSRF, generation allowance/refunds, size limits
and code-bound observations against real isolated PostgreSQL.
`checks/source_debugging_result.json` records the current browser and live Groq
generation checks. Older `debugging_result.json` is historical.
`checks/live/debugging.py` has prepare/resume behavior based on a private
checkpoint: run it once, restart the local app, then run again to prove Neon
persistence and remove the disposable fixture. Its test observations are fixtures,
not a substitute for the actual browser runner checks. See DEBUGGING.md.

Run `npm run check:dev-proxy` from the project root to exercise the actual Vite
proxy configuration with 13 GET/write requests against a disposable HTTP backend.
It uses an isolated temporary dependency cache and no database. This catches
missing proxy prefixes that production Flask-only browser tests cannot detect.
`dev_navigation_result.json` records the actual localhost:5173 regression check.
## In-app debugging repair checks

`python -m unittest checks.test_debug_checker checks.test_debug_generator checks.test_debugging -v`
covers safe source comparison, alternative review validation, owned saves, stale
results, review quotas, cached reviews, failure refunds and concurrent edits.
Integration tests require `TEST_DATABASE_URL` pointing to the isolated
`repoviva_test` database; never use production storage.
`debug_solution_result.json` records the local browser and live Groq boundaries.
