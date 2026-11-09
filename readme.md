# RepoViva

Practice explaining a project, with feedback grounded in its source code.

**Status, November 9, 2026 (IST): local Flask backend implemented.** Source loading,
retrieval, question generation, and answer evaluation are connected; standalone
Prisma transcription and live question/answer calls have been exercised. Fourteen
local regression tests pass. The production React build is served directly by
Flask under one Gunicorn worker. A local production browser test completed real
question generation, Prisma WAV upload, transcript review, and answer evaluation.
Direct microphone capture, real PCM WAV conversion, playback, cancellation, retry,
and the 60-second limit have been tested with a synthetic browser microphone.
A physical microphone with live Prisma and deployment are still pending. The
stage assignments and dates below remain the original learning plan.

## Why build this?

Students can describe what a project does without being able to explain how its code works. RepoViva is a practice tool that asks a focused question, accepts a typed or spoken answer, and separates supported claims, contradictions and claims the available code cannot verify.

The builder's goal is equally important: understand and implement each part personally, and be able to explain it during an internship interview. AI assistance is allowed as a tutor; contribution claims must reflect what actually happened.

## First release

Start with one small, sanitized source pack from a repository the builder can inspect and share. If using SpeakSpin, obtain its actual source first. Do not treat résumé text or this conversation as evidence of what the code does. Before real source is available, use clearly labeled synthetic fixtures.

The proposed user flow is:

1. Select the bundled project and a supported feature, such as matchmaking.
2. Receive a question grounded in selected snippets, with optional Gnani Timbre playback.
3. Type an answer or record a short answer transcribed using Gnani Prisma.
4. Review and correct the transcript before submitting it for evaluation.
5. Read claim-level feedback and click cited snippets.
6. Continue for up to three questions and see a summary of what to revise.

English and Hinglish are the target input languages. Actual language quality, supported formats and latency must be tested; no performance or accuracy claims are established yet.

## Stack

Python + Flask backend and React + Vite frontend written in TypeScript. Start with Python standard-library file reading and introduce Flask at the API stage. Use simple Python validation functions rather than a new validation framework. Node.js is only needed for frontend tooling. TypeScript applies to the frontend; Flask remains a Python backend.

Use a project-local `.venv` for backend dependencies. It is an isolated Python package environment, not a web framework. You can call its Python executable directly without activation; the setup task below explains how.

Keep RAG as a small, explicit pipeline: read source files, split them into cited chunks, retrieve relevant chunks, then give those chunks to the LLM for questions and feedback. Begin with a reviewed feature map, then implement simple keyword ranking using Python. No embeddings, vector database or RAG framework is needed for this release. Learn each part while building it.

## Documents

- [PRD.md](PRD.md): users, problem, scope, user journey and product acceptance.
- [architecture.md](architecture.md): components, data flow, boundaries and trade-offs.
- [trd.md](trd.md): technical requirements, proposed contracts, acceptance checks and milestones.
- This file: working agreement, progress and the current assignment.

## Learning workflow

Each stage ends with a working artifact, a meaningful check, and a short explanation without notes. Do not move forward just because generated code runs.

For each small task:

1. Explain the intended input, output and failure cases in plain language.
2. Attempt the implementation yourself. If stuck, ask for a hint or one specific example.
3. Run it and inspect the actual output.
4. Fix one observed issue at a time. Ask for review of your attempt rather than a complete replacement.
5. Explain why it works, one limitation, and one change you can make yourself.
6. Commit the completed part and update the progress entry below.

When requesting AI assistance, use: "Help me with Stage N, task X only. Explain the concept, inspect my attempt, and give the smallest useful hint. Do not implement later stages or rewrite the project unless I explicitly ask."

Future stages are a roadmap. Only Stage 1 is currently assigned in detail. There are no completed checkpoints yet.

## Roadmap and target dates

Assumption: about 4–5 focused hours per day. These are planning targets, not guaranteed estimates. If a learning checkpoint takes longer, cut optional features using the rules in trd.md.

| Stage | Working outcome | Target, IST | Status |
| --- | --- | --- | --- |
| 1 | Load and display line-numbered source evidence locally | Oct 30 | Not started |
| 2 | Implement simple source retrieval; separately verify one real Prisma and Timbre call | Oct 31–Nov 1 | Not started |
| 3 | Text-only question and claim-level evaluation through Flask | Nov 2 | Not started |
| 4 | Browser voice recording, transcript review and spoken question | Nov 3–4 | Not started |
| 5 | Three-turn session, evidence UI and deployed demo | Nov 5 | Not started |
| 6 | Evaluation cases, user feedback, fixes and public working demo | Nov 6–7 | Not started |
| 7 | Freeze, document, record and submit | Nov 8–10 | Not started |

## Current assignment — Stage 1 only

**Outcome:** a local Python script that reads one source file and prints line-numbered snippets. No model, web server, database or frontend in this stage. The TypeScript frontend is introduced only after the backend evidence-loading stages are understood.

**Timebox:** roughly 90–150 minutes, including explanation and checking. If you need longer, record the blocker instead of skipping understanding.

### 1. Prepare a small workspace

Create a project folder with `samples/`, `backend/`, and `checks/`. Put these four Markdown documents in the project root. Initialize Git using your usual workflow. Record your Python version. Stage 1 uses only Python standard-library modules; do not install Flask or retrieval packages yet.

**First subtask: create and check the environment on Windows PowerShell.** From your project root, run:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -c "import sys; print(sys.executable); print(sys.prefix != sys.base_prefix)"
```

If `python` is not recognized but the Python launcher is installed, try `py --version` and `py -m venv .venv` for the first two commands. The final command should show the project environment path and `True`. If neither works, stop and resolve the Python installation first. No activation or PowerShell execution-policy change is required.

Add `.venv/`, `.env` and `__pycache__/` to `.gitignore`. Your source files live outside `.venv`. Later, install Flask with `.\.venv\Scripts\python.exe -m pip install flask`; do not install it yet. Record dependencies in `backend/requirements.txt` when introduced. Recreate the environment from dependency files rather than copying or committing `.venv`.

In VS Code, select `.venv\Scripts\python.exe` as the project interpreter if using the Python extension. On macOS/Linux the equivalent executable is `.venv/bin/python`. Background: [official venv documentation](https://docs.python.org/3/library/venv.html).

**Stop after checking the environment if that concept is new.** Confirm which Python is running before starting the loader.

Decide now that `.env`, API keys and private source will never be committed. There is no need to create API keys during this stage.

### 2. Choose one readable source file

Use a small source file you are authorized to share and can read yourself. Keep it under about 100 lines for this exercise. If no actual SpeakSpin code is available, write your own small synthetic matchmaking example and label it **synthetic**, with no claim that it reproduces SpeakSpin.

Include at least one branch or condition worth explaining. Keep any behavior such as a timeout exactly as the source says; do not assume three seconds from this conversation.

### 3. Define the representation before implementing it

Write down a snippet record with these fields: `id`, `path`, `start_line`, `end_line`, `content`. Use one-based, inclusive line numbers. Explain each field. Keep the displayed source text unchanged, including blank lines and indentation.

### 4. Implement the smallest loader

Create `backend/inspect_source.py`. Its job is to read that one UTF-8 text file, split it into chunks of at most 40 lines, and display each snippet ID, source path, line range and numbered content in the terminal. For now, the file path may be a local command-line argument. Do not execute the loaded source.

Use `pathlib.Path`, `read_text`, `splitlines`, list slicing, loops and dictionaries. Handle LF and CRLF line endings; a final newline should not create a phantom extra source line. Avoid trimming source content. For a blank file, return an explicit no-content result.

### 5. Check it against a file you understand

- Count the fixture lines independently and compare them to the display.
- Verify a statement near a chunk boundary appears exactly once and with the correct source line number.
- Check that blank lines and indentation do not shift the references.
- Try a missing file and an empty file. Produce a readable error or explicit no-content outcome.
- Use a 41-line fixture to confirm that fixed chunks produce ranges 1–40 and 41–41.

Record expected and actual results. A small assert-based check is sufficient; a large test framework is unnecessary here. Correct line mapping matters because later feedback depends on it.

### 6. Explain, commit and stop

Without reading a prepared script, explain: Why chunks? What does an evidence ID represent? Why are line numbers preserved? What could a fixed chunk boundary split? How is reading a file different from executing it?

Make one small modification yourself, such as changing the chunk size to 20, and predict the new output before running it. Commit your implementation only after the checks pass.

**Bring back:** your loader, one sample output, the check results, and the one concept that was hardest. We review Stage 1, then unlock the detailed Stage 2 assignment. Do not implement the whole roadmap in advance.

## Progress and continuity

Update this section after each working session and attach the current docs/code in a later chat. These files do not update automatically. Never record credentials.

| Date, IST | Stage/task | What I implemented | Check and result | What I can explain | Blocker / next action | Commit |
| --- | --- | --- | --- | --- | --- | --- |
| Oct 30, 2026 | Planning | No code yet; stack revised to Python/Flask/RAG + React | No checks run | To be assessed at Stage 1 | Complete source loader | — |

For each session also note the AI help used: explanation, hint, snippet, review or generated implementation. This supports accurate interview descriptions.

## Running the app

From the project root, with the project virtual environment active:

```sh
python -m backend.app
```

The Flask backend exposes `/health`, `/retrieve`, `/questions`, `/answers`, and
`/transcriptions`.
Question generation and evaluation require `GROQ_API_KEY`. Turn state is held in
memory in a single process and is cleared on restart. In a second terminal, run
`npm run dev` from `frontend/` and open the URL Vite prints. Its development proxy
forwards requests to Flask on port 5000. When using WSL, run both servers inside
WSL with its Python and Node installations. Restart Vite if changes made through
Windows are not picked up. The Vite proxy only applies during development;
the production build is served directly by Flask. See [DEPLOYMENT.md](DEPLOYMENT.md)
for the one-worker Gunicorn command and Render setup.

After generating a question, use **Upload audio (WAV)** to choose a recording.
The browser sends the file as multipart field `audio_file` to `/transcriptions`.
On success, the transcript replaces the draft in the answer text area. Review or
edit it, then click **Submit Answer** to evaluate it. Uploading alone never
evaluates an answer. Failed transcription preserves the existing draft.

For direct capture, click **Record answer**, allow microphone access, speak, and
click **Stop and transcribe**. Recording stops automatically after 60 seconds.
The browser decodes its recording and encodes a real mono 16-bit 16 kHz PCM WAV
before sending it through the same transcription endpoint. The microphone is
released on stop/cancel. The last recording can be played back or retranscribed
after a provider failure. Review the editable transcript and explicitly submit it
for evaluation. Recording requires localhost or HTTPS; upload and typing remain
available when recording is unsupported or permission is denied.

To test the WAV upload endpoint from the project root, set `VACHANA_API_KEY` in the
backend environment or root `.env`, restart Flask, and run:

```sh
curl -F "audio_file=@samples/test.wav" http://127.0.0.1:5000/transcriptions
```

Use `curl.exe` in Windows PowerShell. This makes a real Prisma call. The endpoint
accepts uncompressed WAV recordings up to 60 seconds and 10 MiB, and returns
`{"transcript": "..."}`. It returns 400 for missing/empty/incomplete recordings,
413 for oversized uploads, 415 for unsupported audio, and 502 for provider failures.
It only transcribes; evaluation still requires a separate answer submission.

Current source layout:

```text
backend/
  app.py                       # Flask routes and turn state
  evidence/
    read.py                    # Load source and create snippets
    retrieve.py                # Keyword retrieval
  interview/
    question_generator.py      # Generate grounded questions
    evaluator.py               # Evaluate claims and validate quotes
  speech/
    transcriber.py             # Prisma WAV transcription
checks/
  test_answer_flow.py           # Local regression tests
  live/                        # Explicitly run provider checks
samples/                       # Source fixtures, read as text
```

See [checks/README.md](checks/README.md) for local test and live-check commands.

## Challenge delivery

Proposed internal target: submit by November 10 at 6 PM IST, with November 9 preferred if everything is ready. The official deadline is November 10, 2026 at 11:59 PM IST. Publish the working video before final submission and nominate its post link. Include Gnani attribution and the required hashtags. These are planned actions, not actions authorized for this assistant to publish or submit automatically.

Sources checked October 30, 2026: [challenge page](https://www.gnani.ai/internship), [participation terms](https://www.gnani.ai/great-indian-ai-internship-registration-form), [developer docs](https://docs.gnani.ai/). Recheck the final form and API contracts when implementing/submitting.
