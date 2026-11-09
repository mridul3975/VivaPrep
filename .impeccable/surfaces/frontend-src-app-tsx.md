---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: ["frontend/src/index.css","frontend/src/components/SourceUpload.tsx","frontend/src/components/VoiceRecorder.tsx","frontend/src/components/ActivityOrb.tsx"]
---

# Study workspace

Visitor mode: Operate. Route: /. Students upload source material, generate a practice set, answer by voice or text, then inspect evidence and a score. Preserve all API contracts and transcript-review behavior.

## Direction contract

THESIS: A focused study desk with bold two-tone introductory type, a direct upload-to-practice path, and a restrained session companion whose orb reflects actual work.

OWN-WORLD: Silver typography and actions on neutral charcoal layers. Self-hosted Geist, 14–16px body text, restrained icons, 12–16px panel radii, crisp neutral borders, and tactile controls. No fabricated history, account, activity, or scores.

STORY: Upload material, see what was extracted, generate questions, answer in your own words, and review the original source beside feedback.

FIRST VIEWPORT: A horizontal brand/navigation/status header and a centered workspace capped at 1320px. “Know it. Explain it.” uses 68px/600 type at 1.04 line height in white and muted silver. Introduction, upload, and Generate questions occupy the left column; a restrained session panel with a native 64px orb spans the right. At 700px and below, upload and CTA precede the companion. Active practice retains its compact material tray and a 34px heading (31px on phones), with source evidence beside answering on desktop and after it on smaller screens.

FORM: Adapt SpeakSpin's spacious product shell, Finora's bold two-tone artwork typography, and Meridial's quiet product-panel composition into RepoViva's silver and charcoal identity. Use the supplied artwork rather than Dribbble's hosting interface. Native Libraries.dev Thinking Orbs provide action-driven motion. Historical seed:4ba15896a5c35ec6. Code-led.

## Orb and editorial refinement

The user supplied [Finora scrolling-page artwork](https://dribbble.com/shots/27042362-Finora-scrolling-page) and [Meridial landing-page artwork](https://dribbble.com/shots/27592314-Meridial-Fintesh-Management-Landing-Page), and specifically requested [Libraries.dev Thinking Orbs](https://libraries.dev/orbs). Reference only the artwork, not Dribbble's hosting interface. Adapt Finora's bold two-tone type and Meridial's restrained product-panel composition. Keep the silver/charcoal identity and the working study flow.

The initial desktop view has a horizontal navigation bar, large two-tone study introduction, real upload controls, and a session panel with a native 64px orb. Active practice remains compact; the source and answer keep their priority. Phones stack the upload before the session controls.

Motion thesis: the orb explains actual work. Connecting, searching, composing, listening, weaving, and solving map to backend connection/microphone permission, extraction, generation, microphone capture, transcription, and grading. In-progress states outrank stale errors. Idle/review/error displays are paused. Use thinking-orbs 0.3.2 native tuned 20px and 64px presets, with library-managed offscreen/hidden-tab pausing and a static reduced-motion frame. No page-load choreography, fake live activity, or financial data.

Verification: `checks/orbs_ui_result.json` records real Flask uploads with simulated AI/STT and a fake microphone at 1440/768/390/360px, with no runtime errors or overflow. The failure → record → cancel regression and idle/active/reduced-motion/offscreen pixel checks passed; live provider and real microphone behavior were not established by these checks.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
