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

PAGE CANVAS: Uilora Kinetic Raster replaces the old dots across sign-in and all routes, including Debug. Fluid circular cells oscillate and grow near the pointer. Keep the charcoal/silver effect subdued beneath readable content. Uilora Aurora replaces gradients only on existing gradient surfaces (brand marks, session/start and material panels); never put Aurora on the page background. Native WebGL renders at up to 30fps/1.5 DPR, pauses hidden/offscreen and freezes for reduced motion. Effects are decorative and ignore input.

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

Viva extension: keep voice-to-editable-transcript and explicit submission.
After answer review, offer one source/answer-grounded follow-up with an allowance
note; the prepared example stays free. Show its earlier answer in a disclosure,
focus the new question, and preserve typing/recording. Restore follow-ups directly
after their original question in the same saved practice. No recursive branches.
Evidence: `.impeccable/review/viva/result.json`, actual local guest/Flask/PostgreSQL
with STT fixture; physical microphone and live STT not exercised in this change.

Guest refinement: Try as guest opens a real isolated session before optional
Google sign-in. A compact bar reports backend allowances and offers upgrade;
save drafts before switching to the upgrade screen. Study and Debug expose
Use Python example beside own upload, with explicit prepared-example labeling.
The prime-checker example's questions, Boolean feedback and restored-source
checks are free. Guest Profile describes temporary access and remaining quota.
Existing Uilora surfaces and responsive behavior apply. Browser evidence:
`.impeccable/review/guests/result.json` (actual local guest creation/PostgreSQL,
simulated own-file AI; real Google account and voice not exercised).

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

Pre-exercise setup follows the user's second screenshot/HTML: a serif heading,
1:2 example/configuration row, full-width numbered/highlighted preview, then
full-width creation action. Maximum content width is 1060px, stacking below
760px. Use current palette variables and existing Kinetic Raster/Aurora;
the reference's background and colors are not adopted. Preserve source upload,
section selection, free example, empty states and saved runs. Real local
Flask/PostgreSQL browser evidence: `.impeccable/review/debug-setup-layout/`.

November 12 active-exercise refinement: user-supplied screenshot and pasted HTML
are the visual authority for this route. Use the solid #08090c canvas, compact
navigation, Newsreader rose-accented title, Work Sans controls, IBM Plex Mono
editor, source line numbers and a quiet result panel. All content and result
colors derive from the actual saved exercise. Place full-width hint/source
disclosures below the 7:5 editor/result split; stack below 760px. Keep reasoning,
voice, autosave and quota disclosure. The latest Uilora canvas specification replaces the dotted charcoal
world. Fonts and their licenses live in `frontend/public/fonts/debug`.
Verified with production-build Chrome at 1440/1040/390/360px, API fixtures and
real browser JavaScript tests; evidence is in
`.impeccable/review/editorial-debug/result.json`. This overrides the older visual
description for active runs only.

Mode: Operate. The same silver/charcoal, Geist, focus and interactive Kinetic Raster
world extends to Debug. The entry shows the student's active source file, a new
upload action, section selector and original excerpt. No source produces a real
upload empty state. Groq creates a deliberate change to an exact source excerpt,
with its filename, global lines, hints and test plan. This is not a detected defect.

A run places the code editor left and generated JavaScript cases right on desktop,
stacking below 900px with locally scrolling code. Before/After counts are real;
the original code must pass the cases and practice code must fail at least one.
Check solution is the primary action for every language. Its result gets focus
and scrolls into view after checking. Other languages use direct source comparison
or labeled AI review: accepted/incorrect scores are 100/0, inconclusive has no
score. JavaScript scores are the percentage of cases passed. AI review explicitly
does not execute code. A disclosure can reveal the original source.
Written pass/fail labels, actual returns and expected values keep evidence
inspectable. Editing code makes the old verdict stale until rerun. Three
graduated hints reveal individually. Hypothesis and why-the-fix-works fields
accept typed or editable voice transcripts and autosave with code, hints and
observations. Save feedback and transcript copy must describe this behavior.
Completion requires current passing tests or an accepted repair and both
explanations. Saved runs reopen from Debug and History; deletion is confirmed.

The browser executes learner code in a Worker inside an opaque sandboxed iframe,
with CSP-blocked connections and a three-second deadline; no submitted code runs
server-side. Results are client observations, not certified assessment. Generation
uses one question-set allowance; alternative-repair AI review uses one answer-review
allowance. Direct source checks, resuming, hinting and browser tests are free. Voice uses the daily
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
