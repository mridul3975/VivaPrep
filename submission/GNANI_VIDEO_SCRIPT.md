# RepoViva: 60-second demo narration

**Completed:** the final `RepoViva-Gnani-60s-YourVoice.mp4` now uses your edited
Recording (4) and Recording (5), with synchronized captions and no generated
voice. The table below is the original recording guide; use the YourVoice SRT
for the final spoken-caption timings.

Read naturally at about 135 words per minute. Record your own voice over the
captioned MP4. The prerecorded sample answer plays at 18–29 seconds; pause your
narration there rather than speaking over it.

| Time | Narration | Picture |
| --- | --- | --- |
| 00–04 | “Can you explain the code you build?” | RepoViva start screen |
| 04–09 | “RepoViva turns uploaded project files into source-grounded viva practice.” | Upload and extracted evidence |
| 09–16 | “Groq generates source-grounded questions and keeps reference answers hidden until I submit.” | Generated questions and source |
| 16–30 | At 16–18: “Powered by Gnani Prisma.” Then let the sample audio play. | Actual Prisma transcript; prerecorded synthetic sample labeled |
| 30–37 | “I correct the transcript, submit my answer, and inspect feedback against the original evidence.” | Real answer review and source quotes |
| 37–48 | “Debugging practice adds reproducible failures, real tests, and graduated hints. I repair the code and verify the result.” | Controlled recording challenge, before/after tests |
| 48–54 | “History brings back saved material, answers, and debugging practice.” | Saved study and debug runs |
| 54–60 | “Neon preserves progress. Speech transcription is powered by Gnani Prisma v3.0.” | Profile; closing attribution |

## Recording notes

The captioned demo is an edited screen recording of the running app. Processing
waits are omitted; do not claim an end-to-end latency measurement. The demo account
and source material are illustrative. The spoken sample is synthesized locally;
the upload, Prisma transcription, Groq generation/review and browser tests are
actual operations. Debugging is a curated exercise with optional project context,
not automatic mutation of any arbitrary repository. No face, real email or API
key is required on screen.

## Gnani submission notes

The [official challenge](https://www.gnani.ai/internship) requires a working-app
video, identification of the Gnani technology and contributions, and a public
LinkedIn/X post before submission. Tag Gnani AI and include **#GnaniAI** and
**#GreatIndianAIInternshipChallenge**. Nominate the post link in the final form.
The page lists **November 10, 2026, 11:59 PM IST** and a separate best-60-second-demo
award. Public posting and final submission remain your actions.

## Suggested post

I built **RepoViva**, a voice-first practice tool for explaining and debugging
your own project code.

Upload source files or PDFs, answer grounded viva questions, correct your spoken
transcript, and inspect evidence-linked feedback. A controlled debugging exercise
adds executable tests and graduated hints, with saved practice in History.

**Gnani integration:** Prisma v3.0 speech-to-text through the Vachana API.
**Other components:** React, Flask, Groq, Google sign-in and Neon PostgreSQL.

The demo uses an illustrative project and labeled prerecorded sample audio.

Tag Gnani AI's official account using the platform's tag picker.

#GnaniAI #GreatIndianAIInternshipChallenge

## Written project explanation

RepoViva helps students check whether they can explain code they have built.
The application extracts uploaded material into cited snippets, generates
source-grounded questions and hidden reference/rubric packages with Groq, and
accepts typed answers or audio transcribed by Gnani Prisma v3.0. Students can
correct transcripts before explicitly submitting answers for evidence-linked
review. PostgreSQL stores owned material, practice, drafts and results, with
server-enforced daily API allowances. The first debugging exercise lets learners
fix a controlled JavaScript recording validator and compare executable before/
after tests. Browser test results are practice observations, not certified
assessments. Add your accurate personal/team contribution details in the form.
