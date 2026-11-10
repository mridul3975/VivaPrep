# History, profile and daily allowances

The header has **Study**, **History** and **Profile**. The former Your material
and Answer review navigation items were section shortcuts; their useful evidence
and feedback remain in the study workspace. Back is available across screens.

History groups saved practice under each owned file, including unanswered sets.
Resume restores the selected question and saved text draft. Review opens saved
feedback. Practice again copies saved questions into a new run without generating
them again; reviewing new answers still uses the answer-review allowance.
Search supports original and subsequently uploaded alias filenames. Lists are
paged in groups of 20. The latest submitted answer per question is displayed;
older regrading attempts remain stored but have no separate timeline screen.

Uploading identical file bytes restores that user's saved material before PDF
extraction or AI generation. Renaming a file does not invalidate the match;
changed bytes create a separate record. Sources from different accounts are never
shared. Original files and raw recordings are not stored. Closing material keeps
its practice. Delete permanently in History removes that material's extracted
text, questions, drafts, answers and scores after confirmation.

Profile stores display name, institution, course and study year separately from
Google's verified identity. Email is managed by Google. Allowances are enforced
on the backend and persist in Neon:

| Action | Daily default | Environment variable |
| --- | ---: | --- |
| Generate a question set (up to 3 questions) | 10 | DAILY_QUESTION_LIMIT |
| Review an answer | 30 | DAILY_REVIEW_LIMIT |
| Transcribe audio | 10 | DAILY_TRANSCRIPTION_LIMIT |

They reset at midnight UTC (05:30 in India); Profile displays the next reset in
the browser's local time. A user row lock reserves usage atomically before the
provider call, so concurrent requests cannot spend the last use twice. Known
provider, validation or persistence failures refund the reservation. An interrupted
call with unknown outcome remains counted. Provider rate limits can still apply.
Reopening, restoring duplicates and cached practice do not consume generation
allowance. Deleting history does not replenish usage.

Migration `002_history_profile_usage.sql` adds profile data, source/set selection,
drafts and a daily usage ledger. `python -m backend.start` applies migrations
before serving. PostgreSQL is required for durable history; explicit memory
development mode reports its limitations and usage resets with its process.

API additions: GET/PATCH `/profile`, GET `/history/documents`, GET/DELETE
`/history/documents/<id>`, POST `/sources/<id>/activate`, POST `/sources/<id>/close`,
POST `/history/practice-sets/<id>/retry`, PUT `/history/turns/<id>/draft`.
All require the signed-in owner; writes require the application's CSRF token.
Exhausted actions return 429 with `daily_allowance_exceeded` and Retry-After.

Validation uses real isolated PostgreSQL for ownership, concurrent usage, refunds,
duplicate reuse, drafts, cached runs and cascades. Browser checks exercise real
Flask/DB requests with fixture Google credentials and simulated AI/STT at
1440/768/390/360px. Real Google account sign-in remains a user-account check.
