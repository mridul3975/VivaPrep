# RepoViva

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Students preparing for viva questions from their own study material and source files.

## Product Purpose

Upload a document, practice AI-generated questions, and review source-backed feedback and a practice score.

## Stack

React and TypeScript with Vite; Flask API; PostgreSQL with psycopg 3 for persistence; Groq for question generation and grading; Gnani Prisma for speech transcription.

## Capabilities and Constraints

- Google-only sign-in; verified identities own their source material and question turns.
- One active source/text file or searchable PDF per signed-in Google identity.
- Generate a set of up to three questions with hidden reference answers and grading criteria.
- Type an answer, record up to 60 seconds, or upload WAV audio. Students review the editable transcript before explicitly submitting.
- Feedback contains criterion points, factual claim labels, original source quotations, and the AI reference answer.
- PostgreSQL saves Google identities, expiring login-session hashes, extracted material, question sets, submitted answers, feedback and scores across restarts. Reload resumes saved practice; history is available through an owned API. Replacements archive old material; explicit removal deletes linked practice. Blank `DATABASE_URL` enables temporary memory development mode. Real Google account sign-in and Render hosting remain unverified.
- PDF extraction has no OCR. Existing file limits and API behavior remain unchanged by the visual redesign.

## Brand Commitments

The user requested visual inspiration from https://speakspin-nine.vercel.app/ with a silver and charcoal palette. Adapt its spacious shell and material hierarchy to study practice. The supplied [Finora artwork](https://dribbble.com/shots/27042362-Finora-scrolling-page) informs bold two-tone type; [Meridial artwork](https://dribbble.com/shots/27592314-Meridial-Fintesh-Management-Landing-Page) informs quiet product-panel composition. Use the artwork itself, not Dribbble's hosting interface. The requested [Libraries.dev Thinking Orbs](https://libraries.dev/orbs) reflect real actions, pause at rest, and respect reduced motion. Retain the existing RepoViva name, book identity, and silver/charcoal palette.

## Product Principles

- Make the next study action clear.
- Keep source evidence inspectable and unchanged.
- Preserve editable drafts on request failures.
- Show real session state and scores; never fabricate activity, history, or performance.

## Evidence on Hand

The working frontend and API, regression tests in `checks`, live provider verification recorded in `checks/live_pdf_citation_result.json`, and the user-confirmed working upload-to-score flow.
