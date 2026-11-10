# History and saved-file reuse

Status: core history implementation completed November 10, 2026. History now
lists owned files and sets, restores drafts and results, supports cached practice
and duplicate-file reuse, and separates closing from permanent deletion.
Profile shows server-enforced daily allowances. The original design below records
the starting point and wider plan; original-file downloads, full attempt timelines
and a dedicated version-comparison interface remain future work.

## Current state

The database already stores extracted material, generated question sets, private
reference answers and rubrics, submitted answers, feedback, and scores. A new
upload archives the previous source. The existing `/history` endpoint returns
the latest 100 answer attempts, but React has no History screen. Reload restores
only the active file's latest practice set. Older sources cannot currently be
reopened through the UI.

Every upload currently runs extraction and receives a new source ID, even if its
bytes match a saved file. `backend/evidence/documents.py` already computes the
SHA-256 of those bytes as `revision`, but only after extraction. We can reuse
that fingerprint rather than introducing a second definition of file identity.

Original PDF/source binaries and recordings are not stored. Existing extracted
text and citation metadata are sufficient to reopen study material and generate
questions; downloading the original file would be a separate storage feature.

## Intended experience

Add one **History** navigation entry. It opens a simple searchable list of the
student's saved files. Each row shows the filename, file type, last activity,
and practice status. Opening a file lists its practice sets with dates, progress,
and completed scores. Unanswered sets must appear too; history cannot depend on
the student having submitted an answer.

Available actions:

- **Resume:** reopen an unfinished set with its existing questions, submitted
  results, saved draft and current position. No question-generation request.
- **Review:** inspect an earlier set's questions, answers, feedback and evidence.
  No AI request.
- **Practice again:** reuse a saved question set in a fresh run. Copy the question
  package into new turn IDs, hide reference answers until submission, and keep
  the previous run's results. New answers are evaluated normally.
- **New questions:** explicitly generate and save another set using Groq. Never
  replace earlier sets.

Uploading an already saved file should restore its existing material and latest
practice, with a small "Restored from history" notice. Keep the existing clean
study workspace and interactive dot background; do not introduce dashboard charts
or a large onboarding panel.

## Phase 1: Prepare storage without losing existing records

1. Reuse `sources`, `practice_sets`, `turns`, and `attempts` instead of adding a
   parallel history store.
2. Index saved-file lookup by verified owner, existing byte fingerprint, and
   extraction kind (text or PDF). Add last-opened/activity metadata for ordering.
3. Read existing fingerprints from `document.revision`; do not require students
   to re-upload their current material.
4. Preserve legacy duplicate source IDs and their question snapshots. Group
   matching legacy records in the history response and include all their runs.
   Choose a stable saved source for future duplicate uploads. Do not delete or
   rewrite old turns just to collapse duplicate-looking rows.
5. Make duplicate lookup and activation atomic under the existing per-user row
   lock. Two simultaneous uploads of the same file must not create two new rows.
6. Record extraction, question-generation and evaluation versions so future
   pipeline changes can distinguish compatible saved packages from stale ones.
7. Update the database health check to validate the expected migration version;
   it currently assumes version 1 and would reject a new migration.

Deliverable: existing records remain intact and can support efficient lookup.

## Phase 2: Add history and reopening APIs

Keep the existing `/history` response compatible while adding focused routes:

| Route | Purpose |
| --- | --- |
| `GET /history/documents` | Paginated, searchable saved-file summaries, including inactive files |
| `GET /history/documents/<source_id>` | Owned file details and paginated practice sets |
| `GET /history/practice-sets/<practice_id>` | Saved questions, latest submitted results and attempt history |
| `POST /sources/<source_id>/activate` | Activate an older file and restore the selected or latest practice set |
| `POST /history/practice-sets/<practice_id>/retry` | Create a fresh run from saved questions without generating them again |

Every query must use the verified Google identity. Register new routes with the
existing authentication and CSRF protection. Archived material is readable by
its owner, while generation still requires the currently active source.
Activation updates the active source and opens the chosen run in one transaction.

Return public question fields only before submission. Keep reference answers
and rubrics private for unsubmitted questions. Historical grading must use its
saved evidence snapshot, even after a newer file or extraction exists.

Summaries use the latest graded attempt per question, not the sum of repeated
submissions. Show progress for unfinished sets and label a score as final only
when the set is complete. Paginate lists rather than silently limiting the
visible history to the latest 100 attempts.

## Phase 3: Build the History screen

1. Add History to the current navigation and provide loading, empty, error and
   populated states.
2. Add filename search and recent-activity ordering. Group past sets under their
   file so repeated practice does not clutter the main list.
3. Open an older set for review; offer Resume for unfinished work and Practice
   again for a fresh run using the same questions.
4. Use the existing workspace restoration shape (`saved_practice`) so opening
   history restores questions, progress, answers and feedback consistently.
5. Preserve the current workspace until history loading/activation succeeds.
   A failed request must not clear the student's material or draft.

Deliverable: students can find and reopen earlier material without uploading it.

## Phase 4: Recognize duplicate uploads

1. Validate the upload envelope, size and allowed file kind, then compute its
   byte fingerprint on the backend before expensive extraction.
2. Search only this student's saved material using the fingerprint and kind.
3. On a match, activate and return the saved source and saved practice with
   `reused: true`. Skip PDF extraction/chunking and question generation.
4. On a miss, follow the existing extraction path and save a new source.
5. The frontend restores a hit automatically and exposes New questions as an
   explicit action. It must not immediately generate another set after restoring.

Matching rules:

- Same bytes with a different filename reopen the existing material. Record the
  new display name as an alias; preserve filenames in historical citations.
- Same filename with changed bytes is different material. Keep the old version
  available in History.
- Identical files uploaded by different users do not share private practice,
  answers, grades or history.
- An incompatible extraction/generation version triggers the necessary fresh
  processing while keeping older study records and evidence intact.

In this first version, re-upload still transfers the bytes to the backend for
verification. The savings are extraction and AI work. Opening History directly
also avoids transferring the file again.

## Phase 5: Protect work and make deletion explicit

1. Change the workspace's remove/close action to **Close material**: deactivate
   it and return to setup while preserving the file and practice history.
2. Put **Delete permanently** in History with a confirmation explaining that
   associated questions, answers and scores will be removed. Keep deletion scoped
   to the selected owned material. If legacy duplicates are grouped into one
   entry, delete that entry's matching source IDs and runs together; do not
   include other content versions just because their filenames match.
3. Debounce draft-text saving and store the current question position. Resume
   must prefer a newer draft over the last submitted answer without treating the
   draft as graded. Flush saves before controlled in-app navigation or switching
   material. Tab-close saves are best effort; preserve the local draft and show
   a retry if saving fails rather than promising lossless saving during outages.
4. Preserve every submitted attempt. Reuse saved feedback when reviewing that
   attempt; a newly submitted answer must be evaluated against the chosen
   question and evidence, not assigned an old score because the file matches.
5. Keep sign-out separate from deletion. A later Google sign-in restores the
   same user's library.

## Phase 6: Verify and release

Test the migration on an isolated Neon child branch before production. Never
run truncating integration fixtures against the production database.

Acceptance checks:

1. Upload file A, generate questions, submit answers, then upload file B. Both
   appear in History and reopening A restores its results.
2. Re-upload A, including under another filename. Restore its saved record and
   verify extraction and question generation were not called.
3. Upload edited A with the original filename. Create new material while keeping
   the earlier version and its practice accessible.
4. Two concurrent identical uploads produce one new saved entry.
5. Resume an unfinished run after reload/server restart, including its saved
   draft and question position.
6. Practice again starts a fresh run using cached questions and preserves old
   scores. New questions creates another set through the AI provider.
7. One user cannot list, activate, review, retry or delete another user's records.
8. Close preserves history; confirmed permanent deletion removes only the
   selected material and linked records.
9. Old records and legacy duplicate uploads remain accessible after migration.
10. History, resume and duplicate-upload states work on desktop and phones with
    clear keyboard focus, no overflow and no misleading score summaries.

Implementation order: storage/read APIs -> History UI and reopening -> duplicate
upload reuse -> draft/deletion protection -> complete regression and live Neon
verification. The first visible milestone is opening an old file from History
and seeing its saved questions, answers and scores without re-uploading it.
