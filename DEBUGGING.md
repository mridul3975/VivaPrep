# Debug your uploaded project

Open **Debug**. The page uses the source file already selected in Study or restored
from History. With no source it asks for an upload. Students can upload another
source file directly in Debug and choose a starting section. PDFs and notes stay
available for Study but cannot start debugging exercises.

**Create debugging exercise** sends the chosen section and up to two adjacent
chunks to Groq. The exercise uses an exact excerpt from that file with one
deliberately introduced logic change. The backend validates the original global
line range, exact replacement text and bounded code, hints and test data. Python
excerpts must parse as complete functions or classes; no uploaded code is executed
by Flask. A provider or validation failure returns an error, never a sample task.

Each exercise shows its filename, source lines, expected behavior, practice code
and three graduated hints. Comparing with the uploaded excerpt is an explicit
disclosure that reveals the original. The original upload remains unchanged.
Code, typed/spoken hypothesis, explanation, hints and observations autosave and
resume from Debug or History under the exercise title and filename. Code edits
invalidate old test results. Permanently deleting source material also deletes
its linked exercises. There is no whole-repository or multi-file ingestion.

## Execution and verification

For self-contained synchronous **JavaScript** functions, Groq supplies 3–6 JSON
input/output cases. The browser first runs them against the original excerpt and
the practice version. Original code must pass every case and practice code must
fail at least one; otherwise the UI blocks test submission and asks for another
exercise. Tests use the actual function name and support scalar, array and object
results, including array-valued positional arguments. Basic named ES function and
variable exports are supported. Node, DOM, async and external module dependencies
are not available in the runner.

Other languages (including Python and TypeScript), and code requiring project
dependencies, receive **local verification steps** and a practice-code download.
Students test in their own environment and record commands/results in their
explanation. The app does not execute these tests, mark them passed or certify
completion. AI test plans and the uploaded reference's behavior are not proof of
complete application correctness.

JavaScript executes in a fresh Worker inside an opaque sandboxed iframe. CSP
blocks network connections and outside resources. Learner text arrives by
structured clone, not HTML interpolation. A private MessageChannel returns
observations; iframe source and token are checked. Execution stops after three
seconds. Submitted code never executes on Flask. The server validates case IDs,
JSON observations and the code fingerprint and recomputes pass flags. Browser
results remain client observations, not a tamper-proof assessment.

## Allowances and storage

Creating an exercise consumes **one question-set allowance**, shared with Study's
daily limit of 10. Known generation/validation failures refund that reservation.
Resuming, saving, revealing hints and running browser tests do not call Groq or
use another allowance. Speech uses the existing daily transcription allowance.
Raw voice recordings are not saved by the app.

Migration 003's JSONB state already supports source-specific scenario snapshots;
no new migration is required. Each run requires an authenticated owner, a valid
owned source ID and CSRF for writes. The newest 20 source-derived runs are listed,
with up to 100 per user. Legacy sample runs are kept as archived records but no
longer offered in the Debug or History lists. Old bookmarks return HTTP 410 with
a route back to choosing the student's own source; they cannot restore the sample.

- GET `/debug/challenges`: empty list and `requires_source: true` for compatibility.
- GET `/debug/runs`: recent source-derived exercises with filename/title.
- POST `/debug/runs`: `{source_id, snippet_id?}` generates and saves an exercise.
- GET/PATCH/DELETE `/debug/runs/<id>`: restore/save/delete owned work.
- POST `/debug/runs/<id>/hint`: reveal one of the stored hints.

## Checks

`checks/test_debug_generator.py` validates exact source binding, chunk boundaries,
complete Python excerpts and rejected fabricated replacements. PostgreSQL tests
in `checks/test_debugging.py` cover ownership, CSRF, persistence, cascades,
allowances/failure refunds and stale observations. Current evidence is recorded
in `checks/source_debugging_result.json`; previous curated-exercise verification
files are historical. Live Google sign-in and a Render deployment are separate
from local signed-identity fixture checks.

<!-- specs: solution checking requirements for non-JS languages -->
