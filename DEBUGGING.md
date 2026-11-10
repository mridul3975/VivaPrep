# Debugging practice

Open **Debug → Start challenge**. The first release contains one curated
JavaScript challenge: a 30-second recording is incorrectly rejected by a
recording-duration validator. The bug is deliberately introduced into a practice
function inspired by SpeakSpin's recording flow. It is not a detected defect in
the user's running SpeakSpin application.

The learner inspects the code, records or types a hypothesis, repairs the
function, runs ten executable tests, and explains why the fix works. Tests cover
the exact boundary, just-under boundary, longer and shorter recordings, another
minimum, zero, negative, non-numeric and missing durations, and invalid minimums.
The broken baseline passes 7/10; a correct implementation passes 10/10. There is
no immediate solution reveal. Hints are revealed one at a time and saved per run.

Code edits invalidate the old verdict until the learner reruns tests. Code,
hypothesis, explanation, hints and test observations persist in Neon and reopen
from Debug or History. Deleting a run requires confirmation. The newest 20 runs
are listed; an account may retain 100 runs. Deleting recent runs exposes older
ones. Raw voice recordings remain browser-local and are not stored by the app.

An uploaded source/text file currently selected in Study can be attached as
reference context, with its original source location and content fingerprint.
The exercise remains the curated function. Original files are not modified.
Deleting attached material also deletes its associated debugging runs and context
snapshots. Standalone runs have no attached source. PDF material continues to
support question practice, but is not used as executable source for this exercise.

## Execution and verification boundary

Learner JavaScript runs in a fresh Worker inside a sandboxed iframe without
`allow-same-origin`. The iframe CSP blocks connections, external resources,
forms and base changes. Only the fixed harness source enters the HTML; learner
code arrives by structured clone. A private MessageChannel carries observations,
and the parent checks the iframe source and a per-run token. A three-second
deadline terminates the runner; leaving the screen aborts it. Flask never evals,
imports or executes submitted code. Code, output and input size limits apply.

This is browser-local practice for individual learners, not a hardened remote
code-execution service or a tamper-proof assessment. The backend validates the
shape, case IDs, boolean observations and code fingerprint, then recomputes pass
flags. It cannot certify that a client actually executed the tests. Saved results
are explicitly described as browser observations. There is no LLM correctness
verdict, score inflation or automatic merge into the original project.

The isolation follows the browser's [iframe sandbox model](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/iframe)
and [Worker/CSP behavior](https://developer.mozilla.org/en-US/docs/Web/API/Web_Workers_API/Using_web_workers).
Host resource exhaustion beyond the deadline and anti-cheating are outside this
first release. Arbitrary repository ingestion, generated mutations, arbitrary
test commands, other languages and real-project patch export are future work.

## Voice and allowances

The existing recorder sends WAV audio to backend `/transcriptions`; the returned
text goes into the selected Hypothesis or Why the fix works field and remains
editable. Text fields autosave. Transcribing consumes one daily transcription
allowance on success. Starting challenges, revealing hints, running tests and
reopening saved results consume no Groq question/review allowance.

## Storage and API

Migration `003_debug_practice.sql` adds owned debug runs, indexed by owner/date.
Startup applies it before serving. Every route requires an authenticated student,
and writes use CSRF protection:

- GET `/debug/challenges`: the curated scenario and executable cases.
- GET/POST `/debug/runs`: list recent runs or start the scenario with an optional
  owned source ID.
- GET/PATCH/DELETE `/debug/runs/<id>`: restore, save or delete a run.
- POST `/debug/runs/<id>/hint`: reveal one more hint, capped at three.

`checks/test_debugging.py` exercises real isolated PostgreSQL, ownership, CSRF,
size/shape validation, hints, snapshots, cascades and stale verdicts. Browser
checks cover baseline/fixed code, syntax errors, infinite loops, network blocking,
worker message isolation, fixture voice capture, history and reload at
1440/768/390/360px. `checks/live/debugging.py` verifies persistence through the
running server and Neon using a disposable identity; its submitted observations
are fixtures. Real Google account login and live microphone/provider operation
are separate from the fixture browser checks.
