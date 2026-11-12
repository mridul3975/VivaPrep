# RepoViva

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Students preparing for viva questions from their own study material and source files.

## Product Purpose

Upload a document, practice AI-generated questions, and review source-backed feedback and a practice score. Diagnose a controlled code bug through executable tests and your own explanation.

## Stack

React and TypeScript with Vite; Flask API; PostgreSQL with psycopg 3 for persistence; Groq for question generation and grading; Gnani Prisma for speech transcription.

## Capabilities and Constraints

- Google-only sign-in; verified identities own their source material and question turns.
- One active source/text file or searchable PDF per signed-in Google identity.
- Generate a set of up to three questions with hidden reference answers and grading criteria.
- Type an answer, record up to 60 seconds, or upload WAV audio. Students review the editable transcript before explicitly submitting.
- Feedback contains criterion points, factual claim labels, original source quotations, and the AI reference answer.
- PostgreSQL saves Google identities, expiring login-session hashes, extracted material, question sets, drafts, submitted answers, feedback, scores and debugging runs across restarts. Reload resumes saved practice; History reopens owned work. Replacements archive old material and closing keeps its history; confirmed permanent deletion removes linked practice. Blank `DATABASE_URL` enables temporary memory development mode. Real Google account sign-in and Render hosting remain unverified.
- PDF extraction has no OCR. Existing file limits and API behavior remain unchanged by the visual redesign.

## Brand Commitments

The user requested visual inspiration from https://speakspin-nine.vercel.app/ with a silver and charcoal palette. Adapt its spacious shell and material hierarchy to study practice. The supplied [Finora artwork](https://dribbble.com/shots/27042362-Finora-scrolling-page) informs bold two-tone type; [Meridial artwork](https://dribbble.com/shots/27592314-Meridial-Fintesh-Management-Landing-Page) informs quiet product-panel composition. Use the artwork itself, not Dribbble's hosting interface. The requested [Libraries.dev Thinking Orbs](https://libraries.dev/orbs) reflect real actions, pause at rest, and respect reduced motion. Retain the existing RepoViva name, book identity, and silver/charcoal palette.

## Product Principles

The user also requested the [shadcn.io dot pattern](https://www.shadcn.io/background/dot-pattern) as the page background throughout the site. Muted-silver dots on charcoal must glow and grow near the cursor, with a slow background wave, across sign-in and all study states. Retain solid reading and input surfaces, disable cursor lighting on touch, and respect reduced motion.

- Make the next study action clear.
- Keep source evidence inspectable and unchanged.
- Preserve editable drafts on request failures.
- Show real session state and scores; never fabricate activity, history, or performance.

## Evidence on Hand

The working frontend and API, regression tests in `checks`, live provider verification recorded in `checks/live_pdf_citation_result.json`, and the user-confirmed working upload-to-score flow.

The History/Profile and Debug extensions passed 94 backend tests, frontend build and lint, and browser checks at 1440/768/390/360px without runtime errors or page overflow. `.impeccable/review/history/result.json` and `.impeccable/review/debug/result.json` use real Flask/isolated PostgreSQL with fixture Google, AI/STT and microphone inputs. `checks/debugging_neon_result.json` separately records migration 003, create/save/hints/list/delete and restoration after an actual server-process restart in Neon, using a disposable identity and test-observation fixtures. These checks do not establish live account sign-in, live voice-provider behavior or a certified assessment.

## Saved work and account usage

History reopens uploaded material, unfinished practice, saved feedback and scores.
Identical bytes restore owned work without another generation request. Closing
keeps history; permanent deletion lives in History. Profile includes editable
student details and daily limits of 10 question sets, 30 answer reviews and 10
transcriptions, enforced on the backend and reset at midnight UTC. See
[HISTORY_PROFILE.md](HISTORY_PROFILE.md).

Study, Debug, History and Profile are separate screens. Back follows in-app
navigation with a Study fallback; route changes, including Back, focus the
destination's main content. Remaining allowances are real backend counts, with
the next UTC-midnight reset displayed in local time.

## Debugging practice

Debug uses the student's active source upload or a new file uploaded directly
there. Students select a section; Groq introduces one controlled change to an
exact source excerpt, with source lines, three graduated hints and a test plan.
Self-contained JavaScript functions run generated JSON tests in the browser;
the original must pass and the broken version must fail before tests are accepted.
Other languages and dependencies require local testing, explicitly unverified here.
Typed or transcribed hypotheses and explanations remain editable and autosave
with the code, hints and observations. Saved runs reopen from Debug or History.
Code edits mark previous results stale until tests run again.

Every new exercise is bound to an owned code source, not optional context for a
preset example. PDFs and notes remain Study material. Learner JavaScript runs
in a Worker inside an opaque sandboxed iframe, with blocked connections and a
three-second deadline; submitted code is never executed server-side. Results
are browser observations rather than certified correctness or an LLM verdict.
Generation consumes one question-set allowance, refunded on known failures.
Resuming, testing and hinting use no additional allowance; voice transcription
uses the existing daily transcription allowance. Original files are unchanged. See
[DEBUGGING.md](DEBUGGING.md).

<!-- specs: multi-language debug validation capabilities -->
