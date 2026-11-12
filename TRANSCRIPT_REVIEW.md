# Transcript review before assessment

Speech answers now include a review step between Prisma transcription and
grading. The answer remains editable. A disclosure preserves the original text;
bounded suggestions compare likely spellings of technical identifiers against
the owned question's original source packet. For example, “is crime” may be
offered alongside `is_prime`. Suggestions never change text automatically.
An explicit Use action replaces the matching phrase; the student can also edit
manually or leave it unchanged. Numbers and negations are highlighted in the
general review guidance, not automatically corrected.

The current Prisma adapter provides no word-level acoustic confidence. These
are source-name heuristics, not confidence scores or proof of a transcription
mistake. They can miss mistakes or suggest a term the student did not mean.

The student confirms that the final text matches their intent before submitting.
Any subsequent text edit resets confirmation. The backend resolves an owned
receipt and requires confirmation when speech-review metadata is submitted.
The existing grader receives only the final answer and source, never the raw
transcript or spelling flags as evidence of knowledge. Result metadata keeps the
original transcript, final answer, checks and whether text changed. This does
not claim to infer a student's knowledge from audio or detect every STT error.

## Persistence and compatibility

Apply migration **006_transcript_review.sql** before serving this build. Each
question keeps one latest receipt, containing text/checks and no audio. Recording
again rotates its receipt ID; a stale receipt cannot submit as the latest speech
answer. Submitted feedback retains its own immutable comparison snapshot.
Drafts restore original text and confirmation along with the corrected answer.
Ending/reopening a draft as typed clears its review metadata. Typed answers
remain supported without a speech receipt; this is a learning tool, not proof
that an answer was spoken. Guest-to-Google upgrade transfers receipts with work.
Deleting material cascades to its receipts. Existing account/history retention
applies to transcript text; recordings are not stored.

The Study client sends `turn_id` in multipart `/transcriptions`. The backend
checks ownership before calling the provider and copies source context from
the saved turn. Other existing clients, including Debug voice explanations,
can still omit `turn_id` and receive the original transcript-only response.
Debug now supplies `debug_run_id` and `debug_field` instead, retaining an owned
per-field receipt in the existing run state. Its viva answers must be confirmed
before review; original speech is kept out of the evaluator prompt. See DEBUGGING.md.
Review suggestions use no extra AI request or allowance. Voice and final grading
keep their existing allowances.

## Checks

Browser evidence: `.impeccable/review/transcript-review/result.json`. Real local
Flask/PostgreSQL and anonymous guest cookies exercised a valid WAV upload,
intentional term replacement, manual editing, confirmation/reset, draft reload,
explicit submission and the follow-up flow at desktop/phone sizes. STT was a
fixture; a physical microphone or live provider confidence was not tested.
`checks/test_transcript_review.py` covers source hints, final-only grading,
original/result restoration, typed opt-out, ownership, stale receipts and forged
metadata. A neighboring History fix ensures Practice again starts with original
questions and creates fresh follow-ups rather than cloning old parent links.
