# Practice languages

The language menu on the entry screen and Study supports English, Roman Hinglish,
Hindi (`hi`), Tamil (`ta`), Bengali (`bn`), Telugu (`te`), Marathi (`mr`) and
Kannada (`kn`). The new options request native-script questions, reference answers
and grading explanations. The surrounding application controls remain in English.
Saved questions carry their language into feedback, follow-ups and history.
Changing the selection affects new practice; it does not translate an old turn.

The prepared prime-checker has provider-free questions and references in all
eight choices. Its internal source-backed rubric remains in English. Code,
identifiers and evidence quotations are preserved. Uploaded sources use the
existing question provider with the chosen language instruction. The server
rejects generated questions/references lacking the selected script; this is a
presentation check, not a fluency or translation-quality measurement.

Prisma v3.0 already receives `indic-auto` and detects the spoken language,
independently of the chosen question language. It does not translate the audio
to match the menu. Learners must review their transcript before assessment.
See [Gnani's supported languages](https://docs.gnani.ai/api/STT/languages).

The selector adapts the [shadcn Base UI dropdown menu](https://ui.shadcn.com/docs/components/base/dropdown-menu),
using its portal, positioning, trigger, radio group and radio item composition
with `@base-ui/react/menu`. It keeps RepoViva's existing theme.

Verification: seven unit tests cover the eight choices, prepared follow-ups,
verbatim citations, native-script feedback and technical-token preservation.
Live Hindi, Tamil and Bengali question generation passed source validation.
Browser fixture checks cover both entry and Study selectors, radio state,
keyboard open/Escape/focus return, and 360/390/1440px positioning. Build and lint
passed. Build reports a JavaScript chunk-size advisory after adding Base UI.

Native-speaker review, real speech recordings in the six new languages, live
grading accuracy across those languages, and deployed-browser verification are
still pending. These are initial language options, not benchmarked fluency or
speech-accuracy claims.
