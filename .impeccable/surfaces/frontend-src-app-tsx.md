---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: ["frontend/src/index.css","frontend/src/components/SourceUpload.tsx","frontend/src/components/VoiceRecorder.tsx","frontend/src/components/ActivityOrb.tsx","frontend/src/navigation.ts","frontend/src/pages/HistoryPage.tsx","frontend/src/pages/ProfilePage.tsx","frontend/src/pages/DebugPage.tsx","frontend/src/debug/runner.ts"]
---

# Study workspace and saved practice

Visitor mode: Operate. Route: / with Study/setup, Debug, History and Profile hash routes. Students upload source material, generate a practice set, answer by voice or text, then inspect evidence and a score. Debug derives a controlled code-repair exercise from the student's uploaded source. Preserve the study flow's explicit transcript-review/submission behavior; Debug explanations autosave.

## Direction contract

THESIS: A focused study desk with bold two-tone introductory type, a direct upload-to-practice path, and a restrained session companion whose orb reflects actual work.

OWN-WORLD: Silver typography and actions on neutral charcoal layers. Self-hosted Geist, 14–16px body text, restrained icons, 12–16px panel radii, crisp neutral borders, and tactile controls. No fabricated history, account, activity, or scores.

PAGE CANVAS: The user's shadcn.io Dot Pattern reference supplies an interactive dot treatment across the entire site: 2px muted-silver dots, 24px spacing, charcoal base. Dots near the cursor brighten and grow to 3.5px within a soft 120px light. A slow CSS wave crosses the dots. Touch omits cursor lighting; reduced motion stops the wave and easing. Keep cards, evidence and inputs solid so their content remains clear. The shared decoration persists before and after Google sign-in and throughout long review pages, without intercepting controls.

STORY: Upload material, see what was extracted, generate questions, answer in your own words, and review the original source beside feedback.

FIRST VIEWPORT: A horizontal brand/navigation/status header and a centered workspace capped at 1320px. “Know it. Explain it.” uses 68px/600 type at 1.04 line height in white and muted silver. The introduction occupies the left column; one gradient session card on the right contains a single title/orb header row, upload and evidence preview, file limits/privacy, and Generate questions. Readiness paragraphs, tutorial and CTA hints are removed. At 700px and below, the introduction precedes the single card. Active practice retains its compact material tray and a 34px “Practice” heading (31px on phones), with source evidence beside answering on desktop and after it on smaller screens. Captions are reduced; recording and submission controls retain their functional states, limits and editable transcript.

FORM: Adapt SpeakSpin's spacious product shell, Finora's bold two-tone artwork typography, and Meridial's quiet product-panel composition into RepoViva's silver and charcoal identity. Use the supplied artwork rather than Dribbble's hosting interface. Native Libraries.dev Thinking Orbs provide action-driven motion. Historical seed:4ba15896a5c35ec6. Code-led.

## Orb and editorial refinement

The user supplied [Finora scrolling-page artwork](https://dribbble.com/shots/27042362-Finora-scrolling-page) and [Meridial landing-page artwork](https://dribbble.com/shots/27592314-Meridial-Fintesh-Management-Landing-Page), and specifically requested [Libraries.dev Thinking Orbs](https://libraries.dev/orbs). Reference only the artwork, not Dribbble's hosting interface. Adapt Finora's bold two-tone type and Meridial's restrained product-panel composition. Keep the silver/charcoal identity and the working study flow.

The initial desktop view has a horizontal navigation bar, large two-tone study introduction, and a single session card with real upload controls and a native 64px orb. Upload, preview and generation stay together on phones. Active practice remains compact; the source and answer keep their priority.

Motion thesis: the orb explains actual work. Connecting, searching, composing, listening, weaving, and solving map to backend connection/microphone permission, extraction, generation, microphone capture, transcription, and grading. In-progress states outrank stale errors. Idle/review/error displays are paused. Use thinking-orbs 0.3.2 native tuned 20px and 64px presets, with library-managed offscreen/hidden-tab pausing and a static reduced-motion frame. No page-load choreography, fake live activity, or financial data.

Verification: `checks/orbs_ui_result.json` records real Flask uploads with simulated AI/STT and a fake microphone at 1440/768/390/360px, with no runtime errors or overflow. The failure → record → cancel regression and idle/active/reduced-motion/offscreen pixel checks passed; live provider and real microphone behavior were not established by these checks.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Saved study screens

Mode: Operate. Hash routes cover Study/setup, Debug/runs, History/files and Profile. Keep
the study state mounted across navigation, persist drafts and restore selected
saved sets. History and Profile use the incumbent visual world, without invented
analytics or decorative cards. Real remaining allowances are shown only after
the server responds: daily defaults are 10 question sets, 30 answer reviews and
10 transcriptions, resetting at midnight UTC with local reset-time display. Back
follows in-app history with a Study fallback. Route changes, including Back and
opening a saved run, focus the destination main without forcing a scroll jump.
Closing material retains saved practice; permanent deletion is confirmed in History.
Verification: .impeccable/review/history/result.json; reviewed desktop and phone
captures, real isolated DB and fixture identity, simulated AI/STT.

## Debugging from uploaded source

Mode: Operate. The same silver/charcoal, Geist, focus and interactive dot-pattern
world extends to Debug. The entry shows the student's active source file, a new
upload action, section selector and original excerpt. No source produces a real
upload empty state. Groq creates a deliberate change to an exact source excerpt,
with its filename, global lines, hints and test plan. This is not a detected defect.

A run places the code editor left and generated JavaScript cases right on desktop,
stacking below 900px with locally scrolling code. Before/After counts are real;
the original code must pass the cases and practice code must fail at least one.
Other languages show local verification instructions and a download action,
explicitly without execution claims. A disclosure can reveal the original source.
Written pass/fail labels, actual returns and expected values keep evidence
inspectable. Editing code makes the old verdict stale until rerun. Three
graduated hints reveal individually. Hypothesis and why-the-fix-works fields
accept typed or editable voice transcripts and autosave with code, hints and
observations. Save feedback and transcript copy must describe this behavior.
Completion requires current passing tests and both explanations, without an LLM
correctness verdict. Saved runs reopen from Debug and History; deletion is confirmed.

The browser executes learner code in a Worker inside an opaque sandboxed iframe,
with CSP-blocked connections and a three-second deadline; no submitted code runs
server-side. Results are client observations, not certified assessment. Generation
uses one question-set allowance; resuming, hinting and tests use no extra allowance. Voice uses the daily
transcription allowance. Original source files remain unchanged.

Verification: `.impeccable/review/debug/result.json` and
`{catalogue,before,after}-{1440,768,390,360}.png` record the browser matrix, baseline
and repaired execution, syntax/timeout/isolation cases, hints, fixture voice,
restoration, stale verdicts and route focus including Back. No runtime errors or
page overflow were observed. Flask/CSRF/isolated PostgreSQL are real; Google,
AI/STT and microphone inputs are fixtures. Backend tests: 94 passed; frontend
build and lint passed. `checks/debugging_neon_result.json` separately verifies
migration 003, create/save/hints/list/delete and actual process-restart restoration
in Neon with a disposable identity and test-observation fixtures. This does not
establish live sign-in, live provider/microphone behavior or certified correctness.
`.impeccable/review/debug/finish-review.md` records Ship with transcript-save copy
and route-focus fixes resolved. No shipping assets were added.
