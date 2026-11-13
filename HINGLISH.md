# English and Hinglish practice

Select English or Hinglish at guest entry or on the setup screen before starting
a set. Questions, references and the selected language are saved with the turn;
reopening History or retrying a practice preserves that choice. Prepared-question
cache reuse requires the same language. Existing turns default to English.
Only these two presentation languages are offered. The navigation/UI shell stays
English; this is not a claim of full-app translation or support for many languages.

The prepared Python questions and follow-ups have reviewed Roman-Hinglish versions.
Uploaded material uses the same source-grounded generator with explicit language
instructions and a presentation check. Code identifiers, operators, literal values
and source quotes are never translated. The existing bilingual evaluator accepts
English, Hindi script and Roman Hinglish answers and assesses meaning against the
same criteria. It returns a short summary in the selected language.

A live check found that the model could ignore the language instruction for its
summary. Hinglish feedback therefore has a presentation guard. If necessary, one
bounded extra provider call translates only that feedback, preserving its numeric,
Boolean and identifier tokens. It cannot change the learner answer or criterion
statuses. Invalid/malformed feedback or changed tokens fail closed without saving
a new score. Personal review allowance is charged once; known failures refund it.
This style check is not a measure of fluency, confidence or correctness.

Prisma v3.0 uses `indic-auto`, `format=codemix` and substitution disabled. Mixed
speech can include Hindi script while English terms stay Latin. The original
transcript is saved untouched. Source-term suggestions are optional, explicit
identifier spelling changes, not acoustic-confidence estimates. Suggestions that
would alter protected negations, Boolean words or numbers are filtered out.
Learners must check terms, numbers and negations, then confirm the final transcript.
REST clips are limited to 30 seconds; the recorder stops just before that limit.
Oversized recordings/uploads are rejected rather than silently truncating words.
Edits reset confirmation. Only the final answer goes to the grader; original
speech and spelling flags never establish knowledge or earn points.

Example: changing `is crime` to `is_prime` must leave `True`, `1` and `nahi`
unchanged. A technically wrong claim must still be assessed as wrong.

Timbre has not been added as an in-app feature. The development speech sample was
generated with a stock Timbre voice solely to exercise the actual Prisma pipeline.
The browser smoke test uses an uploaded mixed-language WAV; it does not establish
performance on real learner microphones or accents. This phase covers Study/viva
questions and feedback; Debug's separate repair assessment is not translated here.

No SQL migration is needed: language and summaries use existing JSONB records.
Deploy the backend and rebuilt frontend together. Historical work remains intact.

## Verification boundaries

`checks/test_hinglish.py` covers language validation, cache isolation, quote
integrity, immutable language on saved turns, History/follow-up/retry restoration,
transcript corrections and malformed feedback. `checks/hinglish_live_result.json`
contains live Groq generation and a contradictory-claim smoke test. Private browser
evidence is `.impeccable/review/hinglish/result.json`: live Prisma transcription,
explicit transcript review, live Groq feedback, reload and Hinglish follow-up.

These are development examples, not feature 4's held-out, manually reviewed
30-50-case evaluation. No agreement rate, real-learner outcome or superiority to
a general chatbot is claimed. Preserve this separation for the next phase.

The verification record, including failures found during development and the
boundaries of the live test, is `checks/hinglish_result.json`. Run backend checks
with an isolated `TEST_DATABASE_URL` using `python -m unittest discover -s checks
-p "test_*.py" -q`; the PostgreSQL fixtures clear their test tables. Frontend
checks are `npm run build`, `npm run lint` and
`node frontend/scripts/check-transcript.mjs` from the repository root.
