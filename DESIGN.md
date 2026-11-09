---
name: RepoViva
description: A focused study desk in silver and charcoal.
colors:
  bg: "#111214"
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
- A bold two-tone introduction and upload flow beside a restrained session panel, contracting into a compact practice tray.
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

**Evidence Font:** the platform monospace stack recorded in the frontmatter. Use it for original source lines and quotations, not display headings.

Geist's compact forms combine the established product identity with Finora's bold two-tone headline treatment. The hierarchy uses observed role sizes rather than a fixed mathematical ratio.

### Hierarchy

- **Display:** “Know it. Explain it.” uses the frontmatter display role, with the first line in silver white and the second in muted silver. It reduces to (60px) at 1180px, (52px) at 900px, (48px) at 700px, and (44px) at 390px. Supporting introduction copy is (15px/1.85), (13px) at 900px, and (14px) at 700px, limited to (42ch).
- **Headline:** the active-practice heading uses the frontmatter headline role and reduces to (31px) at 700px. The welcome upload heading is (17px/500), and the session-panel heading is (19px/500).
- **Title:** the active question; reduces to (21px) on phones. Answer section headings use (17px); answer review uses (22px), reducing to (20px).
- **Body:** the base is (14px), not (16px). The answer field uses (14px) with (1.75) line height, increasing to (16px) on phones.
- **Label:** primary controls use the frontmatter label role. Metadata and supporting text use (10–13px); phone character-count and footer details use (9px).
- **Evidence:** source lines use the frontmatter evidence role; quoted feedback uses (11px) with (1.8) line height. Original indentation is preserved.

## Layout

The application shell is a single block with a horizontal header. Header and workspace are centered at a maximum width of (1320px), using `calc(100% - 112px)` at the desktop base. The header is (100px) tall, with brand left, navigation centered, and real backend status right. Workspace padding is (58px 0 30px); active practice uses (36px) top padding. Repeated gaps and padding use the observed spacing steps in the frontmatter; this is not a uniform spacing grid.

The initial grid uses (1.12:0.88) columns with a (340px) minimum session column, (76px) column gap, and (28px) row gaps. Introduction, upload, and Generate questions occupy the left column in that order; the session panel spans those rows on the right. The upload section sits directly on the canvas. Its target has a (146px) minimum height; the initial CTA has a (48px) minimum height and (13px 20px) padding. The session panel has a (580px) minimum height and (28px 30px) padding, with a native (64px) orb. Once a question exists, the large introduction and session panel disappear. A compact, full-width material tray remains above practice; the active question, answer form, and resulting review occupy the first practice column, with original source evidence beside them (1.5:1, with a 300px minimum evidence column).

- **At and below 1180px:** header and workspace use `calc(100% - 72px)`, the initial column gap tightens to (46px), and session padding becomes (26px). Practice becomes one column with evidence after the question, answer, and review. Evidence height is capped at (400px) instead of (720px).
- **At and below 900px:** header and workspace use `calc(100% - 48px)`, the header is (88px) tall, and workspace top padding is (38px). Setup remains two columns (1:0.85), with a (280px) minimum session column and (28px) gap; session padding becomes (23px). The initial CTA and its hint stack.
- **At and below 700px:** the header becomes a brand/status row above one navigation row and is (129px) tall. Setup stacks introduction, upload, Generate questions, then the session panel. The CTA spans the row, the session has no minimum height, and its orb sits beside state copy. Practice progress moves below the heading.
- **At and below 650px:** navigation uses “Study desk,” “Material,” and “Review,” retaining icons, full accessible names, and a (44px) minimum height. Practice panel padding is (22px 19px), answer text becomes (16px), and submit/next controls span their rows. The compact material tray remains.
- **At and below 390px:** header and workspace use `calc(100% - 40px)`, workspace top padding becomes (30px), and navigation padding becomes (10px 6px).

**The Contracting Setup Rule.** When practice starts, keep the uploaded file and replacement controls visible in the compact tray; move preview, full filename, requirements, and privacy copy into “Material details.” Keep the question and answer close to the top of the practice view.

Long prose and filenames wrap. The compact tray's visible filename is ellipsized; its full value is available in the title and expanded details. Original source lines retain whitespace and scroll inside their own evidence region.

## Elevation & Depth

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

Compact and tactile. Primary and secondary actions share a (44px) minimum height and the control radius. Primary controls use silver over ink, with a brighter hover and darker pressed fill. Disabled primary actions use a subdued solid fill and no shadow. Secondary controls use raised charcoal with a visible border. Text actions are underlined; icon controls are (32px) squares with accessible names. All keyboard-focusable controls retain a (2px) focus-silver outline with a (4px) offset. The compact tray's “Generate new set” action becomes “New set” on phones and uses a quiet outline with a (38px) minimum height.

### Cards / Containers

The welcome material section sits directly on the canvas; the restrained session panel supplies its complementary enclosure. Practice surfaces are quieter. The question sits on raised charcoal above the answer surface, separated by a crisp border. Source evidence has its own bordered container and darker source-text region. Review uses a more visible neutral outline and row dividers to separate criteria.

### Inputs / Fields

The editable answer is a full-width dark textarea with a (165px) minimum height, visible border, resize handle, placeholder, character count, and distinct disabled state. Hover brightens the border; keyboard focus adds the common outline. Typed and transcribed answers share this field. Recording and WAV upload produce an editable transcript; the student must explicitly press “Submit Answer.” Failed requests preserve the current draft.

The upload target supports one file through drag-and-drop or a native file picker, with visible size limits, processing states, and contextual errors. Its dashed border brightens on hover or drag, and focus within outlines the entire target.

### Navigation

Google sign-in gates the study workspace. Its screen reuses the two-tone study
introduction and a single charcoal panel containing Google's official sign-in
button. Loading, unavailable configuration, provider errors and retry are real
states. The signed-in header includes an ellipsized email and Sign out; phones
hide the email and retain Sign out. Session expiry and sign-out unmount the
workspace. Login does not imply saved study history.

Navigation is a horizontal labeled-icon row in the header, using (10px 14px) desktop padding, (12px) type, (8px) icon gaps, a flat `#232428` selected fill, and a subtle hover fill. At 900px, padding becomes (10px 9px) and type (11px); at 700px type returns to (12px) with equal-width controls. “Answer review” remains disabled until feedback exists. The header's status text reflects the actual backend health check. Compact labels appear at 650px while preserving complete accessible names.

### Thinking Orbs

**The State-Truth Rule.** Motion follows actual work: connecting for backend connection or microphone permission; searching for source extraction; composing for question generation; listening for recording; weaving for transcription; solving for grading. In-progress states outrank stale errors. Idle, answer-ready, review, and error states use a paused breathing frame. The orb is decorative (`aria-hidden`); adjacent text names the state. Preserve native sizes, offscreen/hidden-tab pausing, and a static frame for reduced motion.

### Material tray and evidence disclosures

During practice, the tray presents the file icon, ellipsized filename, actual source counts, Replace, Remove, “Material details,” and the new-set action. Details span the full tray when opened; the full filename wraps, and preview and requirements remain nested disclosures. Notice counts surface extraction warnings. Evidence navigation shows actual page or line ranges and snippet position. Source evidence can be shown or hidden without changing its text, line numbers, blank lines, or indentation.

### Progress and review

The progress count and segments come from questions actually reviewed in the current set. The score and criterion points come from the answer response; unavailable percentages display an em dash and “Insufficient evidence.” The set score appears only when total possible points exist. Reference answers stay hidden until submission, then appear inside a disclosure. Met/supported, missed/contradicted, and partly met/unverified use the monochrome treatments described above, always with text. Session copy explains expiration without implying accounts or persistent study history.

### Recorded verification boundary

`checks/orbs_ui_result.json` records the refinement matrix at (1440, 768, 390, 360px), using real Flask uploads, simulated AI/STT responses, and a fake microphone. No runtime errors or viewport overflow were observed. The failure → record → cancel regression and idle/active/reduced-motion/offscreen pixel checks passed. These checks do not establish live provider or real microphone behavior. Earlier build, lint, backend regression, and live Groq evidence remain recorded in `checks/ui_redesign_result.json` and `checks/live_pdf_citation_result.json`; they are separate from this refinement's simulated provider checks. Public deployment was not verified.

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
