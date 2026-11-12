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
fail at least one; otherwise Check solution falls back to comparison or AI review.
Tests use the actual function name and support scalar, array and object
results, including array-valued positional arguments. Basic named ES function and
variable exports are supported. Node, DOM, async and external module dependencies
are not available in the runner.

**Check solution** gives an in-app result for every supported language. Restoring
the exact source gives 100/100, and unchanged broken code gives 0/100. Python also
accepts an identical parsed syntax tree, so comments and formatting do not force
an AI call; significant string contents and code structure are preserved.
Alternative repairs are reviewed by Groq against the original, broken version
and expected behavior. A correct review gives 100/100, an incorrect review gives
0/100, and an inconclusive review has no score. Feedback identifies the method;
AI review is static reasoning, can be wrong, and never claims to execute code.
JavaScript scores are the percentage of generated test cases passed. These are
practice scores against the uploaded baseline, not proof of whole-app correctness.
An accepted solution enables the repair viva described below. Saved solution results are bound to the checked code fingerprint;
editing code makes them stale. Provider failures assign no new score.

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
An AI review of a different repair uses one answer-review allowance (30/day by
default); direct source checks are free. Rechecking unchanged saved code reuses
its review. Known provider/validation failures refund the review allowance.
Raw voice recordings are not saved by the app.

## Defend the repair

After checking a repair, the student answers two questions: why the broken code
failed and how the fix works; then a concrete input with its broken and repaired
outcomes. They may type or record either answer. The optional starting hypothesis
remains available but is not graded. Spoken answers have the same source-term
checks and explicit transcript confirmation as Study. Original transcripts and
corrected drafts persist with the run; speech suggestions are not confidence scores.

**Submit viva answers** reviews the saved repair, the actual broken/source code,
contract and available test observations. Groq assesses each answer as understood,
partial, missed or uncertain. The server validates local code ranges and copies
the cited quotes itself. It computes a separate reasoning score: 2/1/0 points per
answer, converted to a percentage; any uncertain criterion yields no overall
score. This is AI static reasoning and does not execute a proposed input.

Completion requires a currently accepted repair and both viva answers understood.
Saving text alone no longer marks a run complete. Editing code or either assessed
answer makes its previous viva feedback stale. Feedback, speech drafts and status
restore through Debug and History. Older runs remain available and can take the
new viva without regenerating the exercise.

A new viva review uses **one answer-review allowance**, including for the prepared
Python example; that example's generation and direct repair checks remain free.
Unchanged submissions reuse their saved review. Provider, malformed-citation and
concurrent-edit failures refund the reservation. A temporary per-run lease prevents
duplicate concurrent reviews and expires after two minutes if interrupted.
The extension uses existing owned JSONB run state and needs no new SQL migration.

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
- POST `/debug/runs/<id>/check`: `{code}` checks the saved version, returning a
  persisted `solution_result` with verdict, score, method and explanation. Stale
  saves or changes during review return 409; another user's run returns 404.
- POST `/debug/runs/<id>/defend`: `{}` reviews saved `explanation` and
  `failing_input` only after the current repair passes. Returns the saved
  `defense_result` and `defense_current`; missing answers/unconfirmed speech return
  400, unfixed/concurrently changed work returns 409, provider failures 502/503.
- PATCH also accepts `failing_input` and `speech_reviews` metadata keyed by answer
  field (`receipt_id`, `reviewed`). Original transcripts are resolved server-side.
- POST `/transcriptions` accepts optional `debug_run_id` and `debug_field` multipart
  fields for owned-run speech receipts. It does not save an answer or grade it.

## Checks

`checks/test_debug_generator.py` validates exact source binding, chunk boundaries,
complete Python excerpts and rejected fabricated replacements. PostgreSQL tests
in `checks/test_debugging.py` cover ownership, CSRF, persistence, cascades,
allowances/failure refunds and stale observations. Current evidence is recorded
in `checks/source_debugging_result.json`; previous curated-exercise verification
files are historical. Live Google sign-in and a Render deployment are separate
from local signed-identity fixture checks.

Repair-viva regression coverage is in `checks/test_debug_viva.py`, browser evidence
in `checks/debug_viva_result.json`, and opt-in live Groq evidence in
`checks/debug_viva_live_result.json` (`PYTHONPATH=. .venv/bin/python checks/live/debug_viva.py`).
That live script uses two provider requests and no database or learner records.
