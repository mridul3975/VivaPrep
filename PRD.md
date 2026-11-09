# RepoViva — Product Requirements Document

Version 0.2. October 30, 2026 (IST). Status: planned; no implementation or validation results yet.

## 1. Product purpose

Help students practice explaining how a software project actually works. RepoViva asks a question about supplied source snippets, accepts an answer, and shows which implementation claims the available evidence supports, contradicts or cannot verify.

The builder must also be able to implement, test and explain each component personally. The deadline is November 10, so familiarity and completion take priority over adding technologies.

## 2. Users and problem

Primary user: a student preparing to discuss a project in an internship interview or viva. They can describe the product but struggle when asked to trace a feature or justify an implementation claim.

Current alternatives include reading code manually, asking a general chatbot, and memorizing project summaries. RepoViva's proposed value is connecting each question and correction to inspectable source evidence, while allowing spoken English/Hinglish answers and transcript correction.

This is practice feedback, not an employment assessment or proof of technical proficiency. The model may misinterpret code; a valid citation is not a guarantee of a correct judgment.

## 3. Release boundary

The challenge release supports one bundled, sanitized project and a small set of deliberately selected feature flows. It does not claim to analyze any GitHub URL. Real users can try the example project; bringing their own repository is a later feature.

If SpeakSpin is used, source behavior must be established from actual shareable code. Until then, synthetic fixtures must be labeled. A conversation or résumé bullet is not source evidence.

The distinctive demonstration is a spoken answer that makes one incorrect implementation claim, followed by feedback showing the conflicting code. Also demonstrate an unverified claim so the product does not falsely penalize missing evidence.

## 4. User journey

1. Open the app and see the bundled project, source label, supported features and limitations.
2. Choose a feature, such as matchmaking, whose snippets can be retrieved and checked against a reviewed baseline.
3. Receive a code-grounded question; choose to play its spoken version if Timbre is enabled.
4. Type an answer or record up to 60 seconds using the microphone.
5. See the Prisma transcript and correct mistakes before submitting.
6. See claim-level feedback and expand each citation to inspect the source.
7. Continue for up to three questions, then review a short list of corrections and topics to inspect.

A single complete turn is the fallback release if the larger session cannot be finished reliably.

## 5. Scope

| Capability | Priority | User-visible completion condition |
| --- | --- | --- |
| Bundled project and supported feature selection | Must | User knows which code the app can discuss |
| Grounded question | Must | Relevant source evidence is available and question references are checked |
| Typed answer | Must | User can complete the flow without microphone access |
| Real Gnani speech integration | Must for contest build | At least one actual Gnani voice service is used visibly and named accurately |
| Prisma transcription and transcript review | Primary voice target | User can speak and edit the transcript before feedback |
| Timbre question playback | Target | Question audio plays; text remains usable on failure |
| Supported / contradicted / unverified feedback | Must | Labels have explanations; supported/contradicted claims have valid references |
| Source evidence panel | Must | User sees file, line range and exact cited text |
| Up to three turns and revision summary | Target | Session ends with a clear list of what to revise |
| Public hosted demo and working video | Must for delivery | Fresh user can try it; user publishes and submits valid links |
| Arbitrary repository upload or GitHub ingestion | Later | Excluded from deadline commitment |
| Embeddings, vector search, agents, graphs | Later | Only considered after an observed need |

No multiplayer, formal hiring score, junior/senior label, automatic execution of uploaded code or personalized long-term history in the first release. Google-only sign-in was added at the user's request; persistent storage remains a separate milestone.

## 6. Feedback rules

- Judge meaning, not mandatory keyword presence.
- Mark contradictions only when available evidence conflicts with the claim.
- Missing evidence produces **unverified**, not a wrong-answer deduction.
- Evaluate current behavior separately from proposed improvements and business rationale.
- Code can show a timeout; it may not explain why the author chose that value.
- Show concise corrections, evidence and one useful follow-up. Avoid presenting a generated reference answer as the only valid wording.
- If the model returns an invalid citation, show a retryable failure rather than a fabricated verdict.

## 7. Experience and error behavior

Display the question, answer area, submission status and feedback clearly. Use simple React components and familiar styling; polish follows the working flow.

Microphone denial offers typing. An empty or partial transcript offers editing/retry, not an automatic zero. Preserve typed/reviewed answers across provider failures. Explain a session reset after a backend restart. Disable duplicate submission while an answer is being evaluated. Text questions remain visible when playback fails.

Do not require users to understand retrieval, prompts or model infrastructure to operate the app. Product copy should explain what evidence is available and what the feedback means.

## 8. Implementation constraint

Use Python + Flask for the backend and React + Vite with TypeScript for the frontend. TypeScript is a frontend language choice and does not replace the Python Flask backend. Start with source loading and chunking in Python, then simple keyword retrieval with a reviewed feature-map baseline. Supply the retrieved snippets to the hosted LLM: this is the small RAG pipeline the builder will learn by implementing it.

Use a project-local `.venv` for Python packages; its setup is taught before coding, and activation is optional. No required FastAPI, Pydantic, embeddings, vector database or RAG framework. Flask is the preferred API framework for this implementation. See architecture.md for the component design and trd.md for contracts and limits.

## 9. Release validation

Proposed checks, not achieved results:

- A fresh user can complete one full deployed turn without developer intervention.
- All displayed citations pass structural checks against the bundled source snapshot.
- A labeled set includes correct, paraphrased, contradictory and unverified claims; investigate all false contradictions.
- Test English and Hinglish audio and record what worked and what failed. Do not advertise broader language quality from a few trials.
- Record stage latency and provider usage; no invented speed or accuracy claim.
- Ask three to five student testers for feedback if reachable. This is a usability goal, not a prerequisite for calling the source checks complete.
- Builder can explain each completed stage and one actual bug fix without reading AI-generated explanations.

Detailed evaluation targets and failure checks are in trd.md. Real user feedback does not replace technical testing, and passing schema checks does not prove semantic correctness.

## 10. Timeline and delivery

| Date, IST | Intended result |
| --- | --- |
| Oct 30 | Environment check and Stage 1 source loader in Python |
| Oct 31–Nov 1 | Simple RAG retrieval, feature baseline and early Gnani API feasibility |
| Nov 2 | Typed question/answer/feedback through Flask |
| Nov 3–4 | Voice and transcript review through React |
| Nov 5 | Narrow deployed session |
| Nov 6–7 | Tests, fixes, student feedback and public working video |
| Nov 8–9 | Freeze, final demo and submission materials |
| Nov 10 | User submits and checks confirmation, targeting 6 PM IST |

Assumes 4–5 focused hours daily. If behind, keep one project, one feature, one turn and real Gnani use. Cut session length, extra features and TTS if necessary, following trd.md. If no Gnani API works, resolve access with official support; a purely substituted pipeline must not be represented as a qualifying Gnani build.

Official deadline: November 10, 2026, 11:59 PM IST. Working public demo video, Gnani attribution, required hashtags and nominated post links are part of submission. Internship selection is not guaranteed by completing the app. Rules source: [Gnani challenge](https://www.gnani.ai/internship), previously checked October 30; recheck the actual form before submitting.

## 11. Learning and progress

Follow readme.md: one stage, one working outcome, meaningful checks, explanation, then review. Only Stage 1 is assigned in detail. Record actual implementation, checks, blockers, contribution and AI assistance after each session.

Maintain these documents as the plan changes. Never turn a planned capability into a completed résumé claim without building and verifying it.
