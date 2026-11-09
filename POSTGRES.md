# PostgreSQL persistence

RepoViva uses PostgreSQL when `DATABASE_URL` is set. The backend uses psycopg 3
and a connection pool; React continues to call Flask on the same origin. A blank
`DATABASE_URL` explicitly selects temporary memory mode for development. A
configured database failure returns 503; it never switches silently to memory.

## Local setup

The current ignored root `.env` points to a working local PostgreSQL database on
port 5432 using a dedicated application role. It is not a hosted Render database.
Keep its credentials private. For a fresh setup, create a database and dedicated
role that can create the `repoviva` schema and its tables, then set the connection
URL in the root `.env`:

```dotenv
DATABASE_URL=postgresql://APP_USER:URL_ENCODED_PASSWORD@localhost:5432/APP_DATABASE
```

With the project Python environment active, run from the repository root:

```sh
pip install -r requirements.txt
python -m backend.database migrate
python -m backend.database check
python -m backend.app
```

Both database commands load the root `.env` and print safe status messages rather
than the connection URL. `migrate` applies versioned SQL under
`backend/migrations/` in a transaction with a database advisory lock. Repeating it
does not reapply recorded versions. `check` verifies connectivity and the expected
schema version. `GET /health` reports `storage_mode: "postgresql"` and returns 503
if the configured database cannot be checked.

Production starts with `python -m backend.start`: migrate first, then execute
Gunicorn. The Docker image already uses this command. Keep a stable
`SESSION_SECRET` across restarts so existing signed cookies remain readable.

## Stored records and ownership

All application tables live in the `repoviva` schema:

| Table | Contents |
| --- | --- |
| `schema_migrations` | Applied migration versions |
| `users` | Stable Google identity, email, name and sign-in timestamps |
| `login_sessions` | SHA-256 hash of the random app session ID, owner and expiry |
| `sources` | Extracted document/snippets and citation metadata as JSONB; active flag and evidence cursor |
| `practice_sets` | Owner and source for each generated question set |
| `turns` | Ordered questions, private reference/rubric/evidence snapshot, evaluation lease |
| `attempts` | Submitted answer, feedback JSONB, earned/possible points, percentage and timestamp |

Access is scoped to the verified Google identity on the server. One partial unique
index permits one active source per identity. Uploading another valid file
archives the previous source rather than deleting its practice history; a failed
replacement preserves the active source. There is no automatic expiry of saved
material or practice records. Original uploaded binary files and recordings are
not stored in these tables.

**Remove upload** asks for confirmation, then deletes the selected source and
cascades to its practice sets, turns and attempts. Signing out revokes the login
session and clears the browser workspace; it does not delete saved study records.
An expired login requires Google sign-in again, after which the same identity can
restore its saved material. App sessions last at most one hour and never outlive
the Google ID token. Google tokens are not retained.

## Restoring study state

`GET /sources/current` returns the active source and its latest `saved_practice`:
public questions, submitted feedback and submitted answers. Unsubmitted reference
answers and rubrics remain private. After reload, the UI resumes the first
unanswered question, or shows the last review when the set is complete. Unsubmitted
drafts are not saved. `GET /history` returns the signed-in student's latest 100
answer attempts with questions, filenames and scores; there is no separate
history screen yet. Regrading saves another attempt while the current set displays
the latest result for that turn.

## Checks and boundaries

See [checks/README.md](checks/README.md) for isolated PostgreSQL tests. They cover
fresh-process restoration, ownership, replacement, deletion, scoring and failure
behavior using simulated AI responses and fixture identities. Never point these
tests at the application database: they truncate their dedicated test data.
Local restart persistence does not establish a hosted deployment, real Google
account sign-in, or a live provider round trip. See [DEPLOYMENT.md](DEPLOYMENT.md)
for the remaining Render setup and end-to-end verification.
