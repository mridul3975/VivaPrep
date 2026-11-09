# Deploy RepoViva on Render

The React build and Flask API run in one service. No Vite server, separate static
host, CORS setup, or frontend API key is needed in production.

## Production build and local check

With the Python environment active, run from the project root:

```sh
pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m unittest discover -s checks -p 'test_*.py' -v
gunicorn --config gunicorn.conf.py backend.app:app
```

Open `http://localhost:8000`. On Windows, run Gunicorn under WSL. Microphone capture
works on localhost; remote visitors must use HTTPS.

The server uses one worker and four threads. Keep both the worker count and the
hosting instance count at one: turn state and locks are process-local. Restarting
or redeploying clears turns; the client must generate a new question afterward.

## Container

The root Dockerfile builds React with Node 24, then copies only its output and the
Python application into a Python 3.12 runtime. Only `samples/read.py` is bundled;
local recordings, `.env`, and development tools are excluded.

If Docker is installed:

```sh
docker build -t repoviva .
docker run --rm --env-file .env -p 8000:10000 repoviva
```

The default container command runs Gunicorn with debug mode and reloading off.
`PORT` is read from the runtime environment, defaulting to 10000 in the container.

## Render

1. Push the project source to a Git repository that your Render account can access.
2. Create a Blueprint from that repository using the root `render.yaml`. Alternatively,
   create a Web Service, select Docker, and use the root Dockerfile.
3. Use one Free instance and `/health` as the health-check path. Leave the Docker
   command at its default so the image's Gunicorn command is used.
4. Set `GROQ_API_KEY` and `VACHANA_API_KEY` in the service's runtime environment.
   The Blueprint uses `sync: false` placeholders and contains no secret values.
   Do not prefix these values with `VITE_` or put them in the React build.
5. Deploy, wait for a successful health check, then open the assigned HTTPS URL.

The deployment is not verified until the public URL is returned and exercised.
Run a complete turn there: generate a question, record or upload speech, review
the transcript, submit an answer, and inspect the quote. Also check a fabricated
turn ID returns 404, and an unknown API path does not return the React page.

Render's Free service sleeps after 15 minutes of inactivity and can take about a
minute to wake. Sleeping or restarting clears the in-memory turns. Open the demo
before recording your submission video and start a new question after a restart.

References:

- https://flask.palletsprojects.com/en/stable/deploying/gunicorn/
- https://render.com/docs/docker
- https://render.com/docs/configure-environment-variables
- https://render.com/docs/free
