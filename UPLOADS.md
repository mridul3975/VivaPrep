# Upload, inspect evidence, and generate questions

Students can upload one source/text file or text-based PDF using **Upload study
material**. Questions and answer evaluation now use the active uploaded file.
There is no bundled-demo fallback in the student endpoints: generating questions
requires an uploaded file.
Replacing or removing an upload clears the question, answer, and feedback in the
browser. Reloading the page restores the active upload from its browser session.

## File handling

- UTF-8 source/text: `.py`, `.js`, `.jsx`, `.ts`, `.tsx`, `.md`, `.txt`, `.java`,
  `.c`, `.cpp`, `.h`, `.css`, `.html`, `.json`, `.yaml`, `.yml`; up to 256 KiB.
- PDF: up to 5 MiB and 20 pages. Password-protected and textless/scanned-only PDFs
  return an explicit error. There is no OCR in this version.
- Extracted text is capped at 200,000 characters. Source text preserves blank
  lines and indentation, with one-based inclusive line citations. PDF chunks stay
  within an original page and cite that page, not invented original line numbers.
  Blank PDF pages are skipped with a warning, preserving subsequent page numbers.
- Uploaded code is read as text and never imported or executed. PDF parsing runs
  in a separate process with a 15-second wall-time limit. Linux also applies CPU
  and memory limits to that process.

## Browser sessions and retention

Uploads are held in server memory, scoped to a signed browser-session cookie, and
expire after one hour or a server restart. Uploading another valid file replaces
that browser session's previous upload. A failed upload preserves the previous
preview. **Remove upload** deletes the current upload from memory.

There are no student accounts yet: two tabs in the same browser session share
the session. A different browser session cannot read or delete an upload using
its source ID alone. The server holds at most 20 active uploads.

`SESSION_SECRET` signs these cookies. Local development generates a random secret
when it is absent. The Render Blueprint generates a runtime secret and sets
`SESSION_COOKIE_SECURE=1` for HTTPS. Keep one worker and one hosting instance.

## API

- `POST /sources`: multipart field `source_file`; returns 201 with `source_id`,
  filename, revision hash, snippets, citation metadata, counts, and warnings.
- `GET /sources/<source_id>`: returns evidence only to the owning browser session.
- `GET /sources/current`: restores the active upload, or returns 204 when there
  is none. Upload responses use `Cache-Control: no-store`.
- `DELETE /sources/<source_id>`: removes an owned upload and returns 204.
- Missing, expired, or another session's source returns 404. Invalid uploads
  return 400/415; oversized uploads return 413; capacity/processing contention
  returns 503. None of these endpoints calls Groq or Prisma.

The frontend development proxy forwards `/sources` to Flask. In production,
Flask serves both the React build and these endpoints on the same origin.

## Next step

`POST /questions` accepts `{"source_id": "..."}` and also defaults to the current
browser session's active upload. `POST /retrieve` follows the same rule. Unknown,
expired, or unowned upload IDs return 404; they never fall back to the demo.
Question sets use up to five uploaded snippets within a 12,000-character evidence
budget, rotating through the material on subsequent sets. Oversized snippets that
cannot fit are skipped; if none can fit the API returns 422. Each turn
stores its exact source snapshot so evaluation cannot switch to a different file.
Uploaded turns are also bound to their owning browser session. PDF page citations
are preserved in question generation, evaluation, and the evidence display.

## Questions, reference answers, and scoring

`POST /questions` generates up to three distinct questions in one Groq request.
For each question, Groq also creates a reference answer and 1–4 grading criteria,
each anchored to an exact quote from a known uploaded snippet. The server checks
those quotes before storing the question set. The response contains a `questions`
array with turn IDs and evidence; reference answers and rubrics remain server-side.

After submission, `POST /answers` compares the student's meaning with the saved
reference answer, rubric, and original evidence. Equivalent wording is accepted.
Each criterion earns 1 point for met, 0.5 for partial, or 0 for missed/contradicted.
If the source itself cannot establish a criterion, it is excluded from the
denominator and displayed as unverified. If all criteria are unverified there is
no numeric score. Factual claim quotes are independently checked against the
uploaded evidence before feedback is returned. The server, not the model's
suggested number or the client, calculates the percentage.

Successful feedback reveals the reference answer, per-criterion points, source
quotes, and the practice score. The browser supports Next question and a set
score across reviewed questions. Regrading replaces that turn's earlier result
rather than counting it twice. These are AI-assisted practice scores, not a
validated academic assessment.

`GET /health` identifies the `study-v2` API. The frontend rejects outdated backends
with an explicit restart message. Local `python -m backend.app` reloads Python
changes with the interactive debugger disabled; Vite polls files for WSL/Windows
edits. Production Gunicorn remains one worker with reloading off.

Extraction limits: https://pypdf.readthedocs.io/en/stable/user/extract-text.html
