# Deploy RepoViva on Render

The React build and Flask API run in one service. No Vite server, separate static
host, CORS setup, or frontend provider API key is needed in production. Google
sign-in uses a public OAuth client ID supplied at runtime by Flask.

Configure [Google sign-in](AUTHENTICATION.md) before testing the study flow.

## Production build and local check

With the Python environment active, run from the project root:

```sh
pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m unittest discover -s checks -p 'test_*.py' -v
python -m backend.start
```

Open `http://localhost:8000`. On Windows, run Gunicorn under WSL. Microphone capture
works on localhost; remote visitors must use HTTPS.

Set `DATABASE_URL` and a stable `SESSION_SECRET` before starting. The startup
command applies database migrations before running Gunicorn, and stops if they
fail. The server uses one worker and four threads; retain one hosting instance
for this deployment. PostgreSQL retains material, practice and unexpired login
sessions across restarts. See [POSTGRES.md](POSTGRES.md) for setup and memory mode.

## Container

The root Dockerfile builds React with Node 24, then copies only its output and the
Python application into a Python 3.12 runtime. Student material is uploaded at
runtime; bundled samples, local recordings, `.env`, and development tools are excluded.

If Docker is installed:

```sh
docker build -t repoviva .
docker run --rm --env-file .env -p 8000:10000 repoviva
```

A database URL using `localhost` points inside the container. Supply a
container-reachable database host in its runtime environment; Docker Desktop can
reach a host database through `host.docker.internal` when PostgreSQL permits it.

The default container command migrates PostgreSQL, then runs Gunicorn with debug
mode and reloading off.
`PORT` is read from the runtime environment, defaulting to 10000 in the container.

## Render

Running application incidents additionally require backend-only `E2B_API_KEY`.
Migration 007 adds owned project snapshots and bounded compute usage. See
[INCIDENTS.md](INCIDENTS.md) for setup, limits and the required live sandbox check.
Without this key, Study and code repairs still work; new running incidents are
disabled. The Docker image also includes the public evaluation artifacts.

1. This app is configured for Neon PostgreSQL. Keep the pooled `DATABASE_URL`
   and direct `DATABASE_URL_UNPOOLED` from the ignored `.env` for the web service's
   runtime environment. If using Render Postgres instead, choose **New > Postgres**, name the database, select the same region
   as the web service, choose a database plan, and create it. A Free database is
   optional and expires after 30 days; choose a paid plan for longer retention.
   See [Render's database setup](https://render.com/docs/postgresql-creating-connecting)
   and [Free plan limits](https://render.com/docs/free).
2. For a local connection to that hosted database, put its **External Database
   URL** in the ignored root `.env` as `DATABASE_URL`. Require TLS with
   `sslmode=require` (append `?sslmode=require`, or `&sslmode=require` if the URL
   already has query parameters). Run `python -m backend.database migrate` and
   `python -m backend.database check`. This explicitly changes the local app from
   its current local database to Render; existing local records are not copied.
3. Push the project source to a Git repository that your Render account can access.
   Create a Blueprint from that repository using the root `render.yaml`. Alternatively,
   create a Web Service, select Docker, and use the root Dockerfile.
4. Use one instance and `/health` as the health-check path. Leave the Docker
   command at its default so the migrate-then-Gunicorn startup is used.
5. Set `GROQ_API_KEY`, `VACHANA_API_KEY`, `GOOGLE_CLIENT_ID`, `DATABASE_URL`, and
   `DATABASE_URL_UNPOOLED` in the service's runtime environment. With Neon, use
   the pooled and direct URLs pulled by `neon deploy`, including their SSL
   parameters. With Render Postgres, use its **Internal Database URL** for
   `DATABASE_URL` in the same-region web service; the external URL is for local
   connections, and `DATABASE_URL_UNPOOLED` can use the same internal URL.
   The Blueprint uses `sync: false` placeholders and contains no secret values.
   Do not prefix these values with `VITE_` or put them in the React build.
   The Blueprint also generates `SESSION_SECRET` for upload-session cookies and
   sets `SESSION_COOKIE_SECURE=1` for the HTTPS deployment. Configure these too
   if creating the service manually.
6. Deploy, wait for a successful health check showing `storage_mode: "postgresql"`,
   then open the assigned HTTPS URL.

The deployment is not verified until the public URL is returned and exercised.
Register the public HTTPS origin in the Google OAuth client's authorized
JavaScript origins. Run a complete turn there: sign in with Google, upload
material, generate a question, record or upload speech, review
the transcript, submit an answer, and inspect the quote. Also check a fabricated
turn ID returns 404, and an unknown API path does not return the React page.
Also verify sign-out blocks further study API access. Restart the service and
confirm the active material, saved questions, submitted feedback and history
remain. Unexpired login sessions survive with a stable `SESSION_SECRET`; expired
sessions still require Google sign-in. Real Google account sign-in and a hosted
Render deployment remain unverified.

Render's Free service sleeps after 15 minutes of inactivity and can take about a
minute to wake. PostgreSQL study records survive web-service sleep/restarts; in
explicit memory mode they do not. Open the demo before recording your submission
video. The Neon database connection is verified; no Render database or
web service has been provisioned by this change.

References:

- https://flask.palletsprojects.com/en/stable/deploying/gunicorn/
- https://render.com/docs/docker
- https://render.com/docs/configure-environment-variables
- https://render.com/docs/free

## Daily application allowances

Render defaults are DAILY_QUESTION_LIMIT=10, DAILY_REVIEW_LIMIT=30 and
DAILY_TRANSCRIPTION_LIMIT=10. Set these on the backend, never in frontend
variables. Limits reset at midnight UTC and persist in PostgreSQL. Startup runs
additive schema migrations before Gunicorn starts. See HISTORY_PROFILE.md.
