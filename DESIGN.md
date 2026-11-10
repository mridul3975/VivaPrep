---
name: RepoViva
description: A focused study desk in silver and charcoal.
colors:
  bg: "#111214"
  page-dot: "rgb(165 166 174 / 0.3)"
  surface: "#1a1b1e"
  surface-raised: "#222326"
  surface-hover: "#2c2d31"
  border: "#35363b"
  border-soft: "#292a2e"
  text: "#f0f0f2"
  muted: "#a5a6ae"
  subtle: "#8d8e97"
  silver: "#dedee3"
  silver-hover: "#f4f4f7"
  ink: "#202125"
  error: "#edb8bb"
  focus: "#d9d9e0"
typography:
  display:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "68px"
    fontWeight: 600
    lineHeight: 1.04
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "34px"
    fontWeight: 550
    lineHeight: 1.15
    letterSpacing: "-0.04em"
  title:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "23px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "-0.025em"
  body:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "14px"
    lineHeight: 1.6
  label:
    fontFamily: "Geist Variable, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.5
  evidence:
    fontFamily: "ui-monospace, Cascadia Code, Consolas, monospace"
    fontSize: "11px"
    lineHeight: 1.9
rounded:
  verdict: "5px"
  small-control: "7px"
  control: "9px"
  navigation: "10px"
  upload: "11px"
  panel: "14px"
  setup-panel: "16px"
spacing:
  "4": "4px"
  "8": "8px"
  "12": "12px"
  "16": "16px"
  "20": "20px"
  "24": "24px"
  "26": "26px"
  "30": "30px"
components:
  button-primary:
    backgroundColor: "{colors.silver}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "11px 17px"
  button-primary-hover:
    backgroundColor: "{colors.silver-hover}"
  button-primary-active:
    backgroundColor: "#c5c5cd"
  button-secondary:
    backgroundColor: "{colors.surface-raised}"
    textColor: "#e0e0e6"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "11px 17px"
  button-text:
    textColor: "#c5c5cf"
    padding: "5px 0"
  navigation-item:
    textColor: "{colors.muted}"
    rounded: "{rounded.navigation}"
    padding: "10px 14px"
  navigation-item-active:
    backgroundColor: "#232428"
    textColor: "#f0f0f4"
  answer-field:
    backgroundColor: "#131417"
    textColor: "#eeeef3"
    rounded: "{rounded.control}"
    padding: "16px"
    width: "100%"
  evidence-panel:
    backgroundColor: "#17181b"
    rounded: "{rounded.panel}"
    padding: "22px 0 0"
  material-tray:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.setup-panel}"
    padding: "18px 22px"
  verdict-supported:
    backgroundColor: "#d7d7df"
    textColor: "#22232a"
    rounded: "{rounded.verdict}"
    padding: "3px 7px"
  verdict-contradicted:
    textColor: "#f0f0f4"
    rounded: "{rounded.verdict}"
    padding: "3px 7px"
  verdict-unverified:
    textColor: "#c2c3cc"
    rounded: "{rounded.verdict}"
    padding: "3px 7px"
---

# Design System: RepoViva

## Overview

**Creative North Star: "The Focused Study Desk"**

RepoViva uses silver type and actions on charcoal layers to make study practice feel calm and direct. The user-selected SpeakSpin reference informs the spacious shell and tactile controls. The supplied Finora artwork informs bold two-tone typography, and Meridial informs the restrained product-panel composition. These references concern the artwork, not Dribbble's hosting interface; RepoViva keeps its own book identity and source-evidence workflow.

The interface becomes denser as the student moves from preparation to answering. Clear questions, editable answers, and inspectable original evidence carry the visual weight. Small icons support text, and feedback uses explicit labels rather than relying on color.

**Key Characteristics:**

- Silver actions and typography on neutral charcoal surfaces.
- A bold two-tone introduction beside one session card containing upload and generation, contracting into a compact practice tray.
- Self-hosted Geist with a separate monospace treatment for evidence.
- Quiet borders, soft tonal gradients, and limited control shadows.
- Visible, truthful session, progress, and feedback states, with Thinking Orbs motion tied to actual work.

## Colors

The palette is predominantly neutral, with a restrained rose error treatment.

### Primary

- **Silver** (`silver`): primary actions and input accents; **Bright Silver** (`silver-hover`) supplies their hover state. **Charcoal Ink** (`ink`) keeps action labels dark and legible.
- **Focus Silver** (`focus`): keyboard outlines, independent of hover or selected state.

### Neutral

- **Desk Charcoal** (`bg`): the continuous page canvas.
- **Panel Charcoal** (`surface`) and **Raised Charcoal** (`surface-raised`): answer areas and question/control surfaces. `surface-hover` is retained as an incumbent CSS primitive; current controls also use local state colors.
- **Crisp Border** (`border`) and **Quiet Border** (`border-soft`): evidence divisions and the compact material tray.
- **Silver White** (`text`), **Muted Silver** (`muted`), and **Subtle Silver** (`subtle`): main copy, supporting labels, and low-emphasis session notes.
- **Error Rose** (`error`): request and input errors, accompanied by an icon and readable explanation. It is not a grading accent.

**The Labeled Verdict Rule.** Keep feedback monochrome and always pair its treatment with a written verdict. Filled silver means met or supported; a bright outline means missed or contradicted; a dashed outline means partly met or unverified.

## Typography

**Display and Body Font:** Geist Variable, with a sans-serif fallback, self-hosted through `@fontsource-variable/geist` in `frontend/src/main.tsx`.

**Evidence Font:** the platform monospace stack recorded in the frontmatter. Use it for original source lines, quotations, editable code and test inputs, not display headings. The Debug code editor uses (13px/1.9), increasing to (14px) on phones.

Geist's compact forms combine the established product identity with Finora's bold two-tone headline treatment. The hierarchy uses observed role sizes rather than a fixed mathematical ratio.

### Hierarchy

- **Display:** “Know it. Explain it.” uses the frontmatter display role, with the first line in silver white and the second in muted silver. It reduces to (60px) at 1180px, (52px) at 900px, (48px) at 700px, and (44px) at 390px. Supporting introduction copy is (15px/1.85), (13px) at 900px, and (14px) at 700px, limited to (42ch).
- **Headline:** the active-practice heading uses the frontmatter headline role and reduces to (31px) at 700px. The welcome session-card heading is (19px/500); its embedded upload has an accessible hidden heading.
- **Title:** the active question; reduces to (21px) on phones. Answer section headings use (17px); answer review uses (22px), reducing to (20px).
- **Body:** the base is (14px), not (16px). The answer field uses (14px) with (1.75) line height, increasing to (16px) on phones.
- **Label:** primary controls use the frontmatter label role. Metadata and supporting text use (10–13px); phone character-count and footer details use (9px).
- **Evidence:** source lines use the frontmatter evidence role; quoted feedback uses (11px) with (1.8) line height. Original indentation is preserved.

## Layout

The application shell is a single block with a horizontal header. Header and workspace are centered at a maximum width of (1320px), using `calc(100% - 112px)` at the desktop base. The header is (100px) tall, with brand left, navigation centered, and real backend status right. Workspace padding is (58px 0 30px); active practice uses (36px) top padding. Repeated gaps and padding use the observed spacing steps in the frontmatter; this is not a uniform spacing grid.

The initial grid uses (1:1.05) columns with a (390px) minimum session column and a (76px) gap. The introduction sits left; one gradient session card on the right contains its title and native (64px) orb in one header row, upload/preview, file limits and privacy disclosure, and Generate questions. Readiness paragraphs, the tutorial and CTA hints are omitted. The embedded upload has no separate panel border or heading, and success notices are announced without adding a visible caption. Its target has a (150px) minimum height; the full-width CTA has a (48px) minimum height and (13px 20px) padding. Card height follows its content, with (28px 30px) padding. Once a question exists, the introduction and card treatment disappear. The same upload component becomes the compact, full-width material tray above practice; the active question, answer form, and resulting review occupy the first practice column, with original source evidence beside them (1.5:1, with a 300px minimum evidence column).

- **At and below 1180px:** header and workspace use `calc(100% - 72px)`, the initial column gap tightens to (46px), and session padding becomes (26px). Practice becomes one column with evidence after the question, answer, and review. Evidence height is capped at (400px) instead of (720px).
- **At and below 900px:** header and workspace use `calc(100% - 48px)`, the header is (88px) tall, and workspace top padding is (38px). Setup remains two columns (0.85:1.15), with a (330px) minimum session column and (28px) gap; session padding becomes (23px). The CTA spans the card's content width.
- **At and below 700px:** the header becomes a brand/status row above one navigation row and is (129px) tall. Setup stacks the introduction above the single session card. The orb remains beside the card title; upload and generation remain inside the card. Practice progress moves below the heading.
- **At and below 650px:** Study, Debug, History and Profile retain their labels and icons in one navigation row with a (44px) minimum height. Practice panel padding is (22px 19px), answer text becomes (16px), and submit/next controls span their rows. The compact material tray remains.
- **At and below 390px:** header and workspace use `calc(100% - 40px)`, workspace top padding becomes (30px), and navigation padding becomes (10px 6px).

**The Contracting Setup Rule.** When practice starts, keep the uploaded file and replacement controls visible in the compact tray; move counts, preview, full filename, requirements, and privacy copy into “Material details.” Keep the question and answer close to the top of the practice view. The heading is simply “Practice,” with no subtitle. File citations live with source evidence rather than repeating under the question.

Long prose and filenames wrap. The compact tray's visible filename is ellipsized; its full value is available in the title and expanded details. Original source lines retain whitespace and scroll inside their own evidence region.

Debug extends the same workspace. Its catalogue pairs the challenge brief with a concrete failing call. A run uses editor and test-evidence columns (1.25:0.85) with a (30px) gap; below (900px) these stack in that order. Before and After counts remain paired. Hypothesis and explanation fields sit side by side below the run and stack below (700px). The code field preserves whitespace and scrolls locally, keeping the phone viewport contained.

## Elevation & Depth

The page canvas follows the user's [shadcn.io Dot Pattern reference](https://www.shadcn.io/background/dot-pattern): (2px) muted-silver dots with (24px) spacing over charcoal. Near the cursor, a soft (120px) silver light reveals (3.5px) dots, making them brighten and grow. Pointer positions update CSS variables outside React rendering, with (160ms) easing after the first position and (180ms) opacity fading on leave. A slow (12s) diagonal CSS wave crosses the base dots. The shared DotPattern decoration covers sign-in, welcome, practice, review, History, Profile and Debug, including long scrolling pages; it is hidden from assistive technology and never intercepts clicks. Touch omits the cursor light. Reduced motion stops the wave and easing while retaining immediate pointer feedback; hidden tabs pause the wave. Card and source-text surfaces remain opaque for legibility.

Depth comes mainly from charcoal surface steps and thin neutral borders. The welcome upload section is transparent and borderless; the session panel uses `linear-gradient(150deg, #383a42 0%, #202126 34%, #17181b 75%)` behind a (1px) `#3e4048` border. Practice panels use solid fills. Selected navigation uses a flat `#232428` fill without a shadow.

### Shadow Vocabulary

- **Brand mark:** (`0 3px 8px #0004`), beneath the small book tile.
- **Primary action:** (`0 3px 6px #0002`), removed when disabled and on the compact tray action.

State transitions use (180ms) for background, text, and border changes. Native Thinking Orbs (thinking-orbs 0.3.2) use tuned (20px) inline and (64px) session presets with the dark theme and silver color. The library pauses offscreen and hidden-tab animation and presents a static reduced-motion frame. Reduced-motion CSS also removes transitions and restores automatic scrolling.

## Shapes

Setup panels use the largest rounded corners, practice and review panels use the middle panel radius, and buttons and fields share the control radius. Question and answer sections join into one silhouette: only the question's top corners and answer area's bottom corners are rounded. Verdict labels have tighter corners; small icon controls and quotation blocks use the small-control radius. Borders are generally (1px). The upload target uses a dashed edge, and status dots are small circles.

Icons are authored inline SVG with a (24×24) viewBox, current-color strokes (1.65px), and rounded caps and joins. Typical interface icons are (14–24px); the welcome upload icon is (25px). The SVG favicon repeats the book tile. Thinking Orbs are native canvas components. No raster images ship with this redesign; reference and review PNGs are documentation evidence.

## Components

### Buttons

Compact and tactile. Primary and secondary actions share a (44px) minimum height and the control radius. Primary controls use silver over ink, with a brighter hover and darker pressed fill. Disabled primary actions use a subdued solid fill and no shadow. Secondary controls use raised charcoal with a visible border. Text actions are underlined; icon controls are (32px) squares with accessible names. All keyboard-focusable controls retain a (2px) focus-silver outline with a (4px) offset. The compact tray uses “New set” at every size, retaining the accessible name “Generate new set,” with a quiet outline and (38px) minimum height.

### Cards / Containers

The welcome session card encloses the complete upload-to-generation task. Its embedded material component adds no nested panel treatment; only the interactive drop target has a dashed boundary. Practice surfaces are quieter. The question sits on raised charcoal above the answer surface, separated by a crisp border. Source evidence has its own bordered container and darker source-text region. Review uses a more visible neutral outline and row dividers to separate criteria.

### Inputs / Fields

The editable answer is a full-width dark textarea with a (165px) minimum height, visible border, resize handle, placeholder, character count, and distinct disabled state. Hover brightens the border; keyboard focus adds the common outline. Typed and transcribed answers share this field. Recording and WAV upload produce an editable transcript; the student must explicitly press “Submit Answer.” Failed requests preserve the current draft. Record answer shows a short inline 60-second limit; recording status appears only during capture. Upload audio and the character count share one row below the field, while submit has no extra caption or separator.

The upload target supports one file through drag-and-drop or a native file picker, with visible size limits, processing states, and contextual errors. Its dashed border brightens on hover or drag, and focus within outlines the entire target.

### Navigation

Google sign-in gates the study workspace. Its screen reuses the two-tone study
introduction and a single charcoal panel containing Google's official sign-in
button. Loading, unavailable configuration, provider errors and retry are real
states. The signed-in header includes an ellipsized email and Sign out; phones
hide the email and retain Sign out. Session expiry and sign-out unmount the
workspace. When PostgreSQL is configured, the sign-in screen explains that
material and submitted answers are saved; temporary memory mode keeps its
expiry notice. A successful Google response is followed by a session check
before the workspace opens.

Navigation is a horizontal labeled-icon row for Study, Debug, History and Profile, using (10px 14px) desktop padding, (12px) type, (8px) icon gaps, a flat `#232428` selected fill, and a subtle hover fill. At 900px, padding becomes (10px 9px) and type (11px); at 700px the four controls use (7px) horizontal padding, (5px) icon gaps and (11px) type. The header's status text reflects the actual backend health check. A shared Back control sits below the header. Route changes, including Back and opening saved runs, focus the destination main without forcing a scroll jump; the skip link targets the visible page.

### Thinking Orbs

**The State-Truth Rule.** Motion follows actual work: connecting for backend connection or microphone permission; searching for source extraction; composing for question generation; listening for recording; weaving for transcription; solving for grading. In-progress states outrank stale errors. Idle, answer-ready, review, and error states use a paused breathing frame. The orb is decorative (`aria-hidden`); adjacent text names the state. Preserve native sizes, offscreen/hidden-tab pausing, and a static frame for reduced motion.

### Material tray and evidence disclosures

During practice, the tray presents the file icon, ellipsized filename, actual source counts, Replace, Close, “Material details,” and the new-set action. Details span the full tray when opened; the full filename wraps, and preview and requirements remain nested disclosures. Notice counts surface extraction warnings. Evidence navigation shows actual page or line ranges and snippet position. Source evidence can be shown or hidden without changing its text, line numbers, blank lines, or indentation.

### Progress and review

The progress count and segments come from questions actually reviewed in the current set. The score and criterion points come from the answer response; unavailable percentages display an em dash and “Insufficient evidence.” The set score appears only when total possible points exist. Reference answers stay hidden until submission, then appear inside a disclosure. Met/supported, missed/contradicted, and partly met/unverified use the monochrome treatments described above, always with text. PostgreSQL restores saved practice, text drafts, submitted answers and feedback after reload. Closing material preserves history; permanent deletion in History requires confirmation because its associated practice records are deleted.

Question activity labels appear only during active work. Source text keeps its original lines and whitespace without an explanatory caption; PDF extraction cautions remain visible. The review keeps criterion explanations and quotes, the score, reference answer, and a concise AI-feedback note. Cumulative set score appears only for multi-question sets. Decorative footer slogans are removed.

### History and profile

History uses quiet file rows, then dated practice rows with real progress and
completed scores. Profile pairs editable student details with backend usage
counts, stacking on narrow screens. Both preserve charcoal surfaces, silver
actions, Geist, focus rings and the shared dot canvas. Closing preserves history;
deletion is explicitly permanent and confirmed. Profile shows the backend's
remaining 10 question-set, 30 answer-review and 10 transcription daily defaults,
with the next midnight-UTC reset in local time. See
[HISTORY_PROFILE.md](HISTORY_PROFILE.md) for behavior and limits.

### Debugging practice

An Operate extension of the study desk, with the editor and concrete test evidence
carrying the visual weight. Debug starts from the student's active source or a
direct source upload. The filename, section selector and original excerpt precede
the generation action. Source-matched exercises retain filename and global line
numbers. The dark monospace editor has a (12px) radius, visible border, resize
handle and focus outline. Run tests is the primary action; reset and graduated
hints remain quieter actions, with reset confirmed.

Generated JavaScript cases show inputs, expected values, actual returns and written
pass/fail labels beside monochrome icons. Original code must pass all cases and
practice code must fail at least one. Before and After counts reflect real runs.
Other languages show a local test plan and download action, with execution marked
unverified. Original source comparison is an explicit disclosure. Changing
code visibly marks the old result stale until rerun. Three hints reveal one at a
time, with an actual revealed count. Typed or transcribed hypothesis and
explanation fields stay editable and autosave, matching the visible save status
and transcript copy. Completion means current tests pass and both explanations
exist; no LLM supplies a correctness verdict.

Saved runs appear in Debug and History, with confirmed deletion. The evidence
footer identifies the results as browser practice observations, not a certified
assessment. The Worker runs inside an opaque sandboxed iframe with connections
blocked and a three-second deadline; no submitted code runs on the server. Voice
uses the existing transcription allowance. Generation shares the question-set
allowance; resuming, hinting and testing use no additional allowance. See [DEBUGGING.md](DEBUGGING.md) for the execution and
storage boundary.

### Recorded verification boundary

`checks/clean_workspace_result.json` records the welcome, question and review simplification at (1440, 768, 390, 360px). Upload, evidence visibility, recording cancellation, editable audio transcription, explicit submission, review disclosures and upload removal passed with no overflow or runtime errors. Google, AI/STT and microphone inputs are fixtures; no live providers or Neon data were exercised in this UI pass.

`checks/orbs_ui_result.json` records the refinement matrix at (1440, 768, 390, 360px), using real Flask uploads, simulated AI/STT responses, and a fake microphone. No runtime errors or viewport overflow were observed. The failure → record → cancel regression and idle/active/reduced-motion/offscreen pixel checks passed. These checks do not establish live provider or real microphone behavior. Earlier build, lint, backend regression, and live Groq evidence remain recorded in `checks/ui_redesign_result.json` and `checks/live_pdf_citation_result.json`; they are separate from this refinement's simulated provider checks. Public deployment was not verified.

The History/Profile and Debug extensions passed 94 backend tests, frontend build
and lint. `.impeccable/review/history/result.json` and
`.impeccable/review/debug/result.json` record browser checks at
(1440, 768, 390, 360px), with no runtime errors or page overflow. Debug's
`catalogue`, `before` and `after` captures show the final four-tab shell; the checks
cover actual sandbox execution, 7/10 and 10/10 results, syntax/timeout/isolation
failures, graduated hints, editable fixture voice input, stale-result invalidation,
saved-run restoration and destination focus including Back. Flask, CSRF and
isolated PostgreSQL are real; Google, AI/STT and microphone inputs are fixtures.
`checks/debugging_neon_result.json` separately records actual Neon migration 003,
run persistence and restoration after a server-process restart, using a disposable
identity and test-observation fixtures. The finish review in
`.impeccable/review/debug/finish-review.md` marks both transcript-save copy and
route-focus corrections resolved. Live account/provider/microphone operation and
certified assessment are outside these checks. No new shipping assets were added.

## Do's and Don'ts

### Do:

- **Do** use the silver and charcoal tokens and reserve rose for explained errors.
- **Do** keep the compact practice tray and the single-row phone navigation.
- **Do** preserve original source formatting inside its scrollable evidence region.
- **Do** keep transcripts editable and require explicit answer submission.
- **Do** pair monochrome verdict treatments with text and show only actual session progress.
- **Do** retain visible keyboard focus and the reduced-motion behavior.
- **Do** animate Thinking Orbs only for real ongoing actions and let active work outrank stale errors.

### Don't:

- **Don't** introduce fabricated history, account activity, scores, or saved progress.
- **Don't** use color alone to communicate grading or connection status.
- **Don't** repeat the large preparation invitation once a question is active.
- **Don't** silently submit a recording or transcript for evaluation.
- **Don't** replace preserved source whitespace with prose wrapping to hide overflow.
