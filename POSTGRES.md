# PostgreSQL persistence

RepoViva uses PostgreSQL when `DATABASE_URL` is set. The backend uses psycopg 3
and a connection pool; React continues to call Flask on the same origin. A blank
`DATABASE_URL` explicitly selects temporary memory mode for development. A
configured database failure returns 503; it never switches silently to memory.

## Local setup

The current ignored root `.env` uses the `production` branch of Neon project
`cold-field-68844991`. Keep its credentials private. To use a local database
instead, create a database and dedicated
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

## Using Neon

Neon works with the existing psycopg 3 backend. The root `neon.ts` declares the
Postgres-only setup; Google Identity Services continues to handle sign-in.
The CLI installed the Neon agent tooling and linked the requested production
branch through the ignored `.neon` file:

```sh
npm i -g neon@latest
neon init -y --org-id org-wispy-haze-93118470 --project-id cold-field-68844991 --branch production --services postgres
neon deploy
```

Complete the browser authorization when requested; run `neon login` and retry
if authorization expires. `neon deploy` pulls Neon variables into the existing
root `.env`. The verified pull preserved Google, Groq, Prisma and session settings.
`DATABASE_URL` is the pooled endpoint for application requests;
`DATABASE_URL_UNPOOLED` is the direct endpoint for migrations. The migration CLI
and production startup select the direct URL, falling back to `DATABASE_URL`
when no direct URL is configured. Explicit test overrides take precedence over
both URLs. Preserve SSL parameters and keep all database credentials off React.
Connection establishment allows 15 seconds and pool acquisition allows 20
seconds, with connection health checks before reuse. Authentication requests
allow 30 seconds so a hosted database waking up does not immediately abort login.

From the project root, install Node dependencies with `npm ci` and
`npm --prefix frontend ci`. Run `npm run build`, then the `migrate` and `check`
commands above. With the Python environment active, `python -m backend.start`
starts the production-built app with Gunicorn. On Render, configure **both**
database URLs in the service environment. Neon provisions the database; it does
not host this Flask/React app. Changing the connection URLs does not transfer
existing local study records.

The migration was first verified on an expiring child of production. The live
check in `checks/live/neon.py` exercises a disposable app identity through real
Neon storage and Groq question generation/grading, then verifies restoration after
a server restart and removes its own records. See `checks/neon_result.json` for
the results and verification boundaries.

See [Neon's connection guide](https://neon.com/docs/get-started/connect-neon)
and [connection pooling guidance](https://neon.com/docs/connect/connection-pooling).

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

## History/profile migration

Migration 002 adds student profile fields, saved selection, drafts and daily API
usage. History supports owned source activation, hash reuse, pagination and
cached practice. Usage is reserved atomically under a per-user row lock. Known
failed calls refund their reservation; deletion does not replenish usage.
See [HISTORY_PROFILE.md](HISTORY_PROFILE.md) for contracts and defaults.
