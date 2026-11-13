# Inspectable evaluation candidate v1

Open `/evaluation` on the Flask-served app. It is public and read-only. Links on
the entry screen and at the bottom of the workspace open it without using quota.
The report, dataset, prompts, model outputs, frozen hashes and synthetic WAVs
ship with the app. No real learner material, credentials or session cookies are
included. Deployment must include the root `evaluation/` directory.

## What this establishes

This candidate contains 40 cases: 16 assessment, 12 repair, eight speech and four
reliability cases. There are four assessment source families and four repair
families; variants are correlated, not 40 independent learners. The functions
are synthetic, short and self-contained. They were authored for this evaluation
and are separate from development examples under `checks/`, including the prime
demo used while building Hinglish support. Do not use these results to tune
production prompts and then claim the same set is held out.

Expected labels and rationales were drafted and inspected by the coding assistant.
They have **not** been independently human-reviewed. Until review is collected,
agreement is against draft expectations, not reviewer accuracy. The report says
this next to its metrics. Speech scripts are intended TTS inputs, not verified
human transcriptions. No real learner corrections have yet been collected.

The dataset, baseline prompt, runner and relevant production code are SHA-256
frozen before live calls in `freeze.json`. This is an auditable local record,
not external timestamp notarization. The run retains raw prompts and outputs,
the model name, temperature, token budget, ordering and errors. One attempt per
system/case is retained. Errors are not automatically retried. Resuming skips
attempted cases, including failed ones. Replications get separate checkpoints.

## Fair baseline

Both systems use Groq `openai/gpt-oss-120b`, temperature 0.2, maximum 4,000 tokens
and structured JSON. The general-assistant baseline receives the same source,
question, reference, criteria and answer; it is explicitly asked to judge meaning
and require explanations when requested. For repairs, both receive the same
original, mutation, contract and proposed fix. Neither sees expected labels or
test outputs. The first system alternates by case. `baseline.json` contains the
complete baseline instructions; all actual prompts are in `results.json`.

RepoViva retains its production validation, reference comparison and optional
feedback-language call. The baseline has no app workflow or source-comparison
fast path. Those differences are the comparison, not hidden model advantages.
It is a same-model general-assistant baseline, **not the ChatGPT product**. No
claim of beating ChatGPT follows from these results.

## Metrics fixed before model calls

- Assessment: two required criteria worth one point each; partial = half a point.
  A contradictory claim/criterion makes the case label contradicted. Otherwise,
  two points = supported, positive partial credit = partial, zero = unsupported.
  Acceptance requires the supported label. Report four-way label agreement,
  point agreement, incorrect acceptances among 12 non-correct answers, incorrect
  rejections among four correct answers and separately unavailable verdicts.
- Repair: correct/incorrect/uncertain static verdict against the draft expectation.
  Incorrect acceptances and rejections are separate from provider errors. Actual
  browser test observations are a separate measure. Four reviewed test suites
  check original and candidate code in the production browser sandbox. A finite
  passing suite is not proof over all inputs; Python/project execution is not
  evaluated here. The supplied original is a baseline, not proof of correctness.
- Speech: one stock Timbre Yashraj synthetic voice, four English and four mixed
  Hindi/English clips, real Prisma with codemix and substitution disabled. Raw
  WER = word-level edit distance / reference word count, case/punctuation ignored;
  numbers and scripts are not normalized. It therefore counts script/format
  differences too. Report edits and denominator, protected-expression omissions
  as lexical flags only, original transcripts and correction drafts. No learner
  corrections or accent/general-population accuracy are invented.
- Reliability: live two-second silent WAV, plus an injected provider outage,
  malformed feedback and invalid citation. Real Flask and isolated PostgreSQL
  routes check no new score, unchanged saved draft under a new session, released
  lease and refunded allowance. Other than silence, provider faults are injected
  deliberately. This is not deployed uptime or a real-provider outage sample.

Every planned case stays in its denominator. Errors, abstentions and missing
outputs do not count as agreement. No composite percentage mixes speech errors,
label agreement and reliability into a misleading single accuracy number.

## Reproduce

Use Python with the project's `backend/requirements.txt`, Node **24+**, Playwright
with Chromium and ffmpeg. The Node requirement supports `stripTypeScriptTypes`.
Install optional browser tooling in an ignored local directory, for example:

```sh
npm install --prefix .eval-tools playwright
.eval-tools/node_modules/.bin/playwright install chromium
# Set EVAL_PLAYWRIGHT_MODULE to the absolute .eval-tools/node_modules/playwright path.
# Optionally set EVAL_CHROME_PATH to an installed Chrome executable.
node evaluation/run-repairs.cjs
```

This uses the actual browser sandbox in `frontend/src/debug/runner.ts`, not a
server-side JavaScript approximation. It executes only committed evaluation
fixtures. The first harness setup attempt used an insecure blank page and failed
because `crypto.randomUUID` was unavailable; it was corrected to use localhost
before the candidate was frozen. No production code changed for that correction.

For live calls, configure `GROQ_API_KEY` and `VACHANA_API_KEY` privately in `.env`.
Live runs consume provider credits. Set `TEST_DATABASE_URL` to a dedicated local
PostgreSQL database named `repoviva_test`. Never use the app's `DATABASE_URL`.
The runner validates the database name, creates a unique fixture identity and
deletes only that identity and its owned rows afterward. It never truncates
tables. Without that test URL, reliability is explicitly skipped.

The checked-in candidate is already frozen; do not overwrite it. Run an independent
replication, keeping the original observations:

```sh
python -m evaluation.verify
# If Git converted only LF/CRLF, restore the exact frozen bytes before replicating:
python -m evaluation.verify --restore-line-endings
python -m evaluation.run --run-name replication-1 --gap 30
```

The verifier tries only LF/CRLF conversion and accepts it only if the resulting
bytes match the original pre-run SHA-256. It rejects actual content changes and
never updates the frozen hashes. The report lists newline-only conversions
separately so a Linux deployment does not mistake Git's conversion for new code.

Only unattempted cases run when that command is resumed. `--sections assessment
repairs` can limit a run; omitted areas remain missing. `--gap 6` sets the minimum
seconds between Groq calls. A new candidate/version needs a separate directory,
new fixtures and a fresh pre-run freeze (`python -m evaluation.run --freeze` was
used once for this version). Never delete errors to get a cleaner score.

```sh
python -m evaluation.report
npm run build
npm run lint
python -m unittest checks.test_evaluation -v
```

The report command regenerates static HTML/Markdown and summaries from the
original `results.json`; it never calls a provider or rewrites an existing review
sheet. The general app regression suite remains under `checks/`.

## Finish independent review

Open `review.csv`, `dataset.json` and the report. For each case:

1. Read the source, question and answer/fix before inspecting model verdicts.
2. For assessment, trace the source and check both criteria and the draft label.
   For repairs, inspect the contract, expected outputs and actual before/after
   test observations; consider edge cases omitted by the finite suite.
3. For speech, listen to the actual WAV. Check whether the intended script is a
   valid reference, inspect identifiers/numbers/negations, and note actual errors.
   An intended correction is not a real learner correction; collect that separately.
4. For reliability, inspect the fault mode and persisted-state observations.
5. Set `decision` to `approve` or `dispute`, add your real reviewer name, an ISO
   date in `reviewed_at` and a short note. Do not change the dataset hash or pretend
   the coding assistant is an independent human reviewer.

Run `python -m evaluation.report` again. It validates case IDs and dataset hashes
and shows the number approved and disputed. Disputes remain visible and prevent
the report being labeled approved. Do not simply change labels after seeing
which answer a preferred system gave. Resolve ambiguities with an independent
reviewer, retain the original candidate and publish a new version if necessary.
Even 40 approved cases would not establish broad real-learner effectiveness.

## First-run findings

Both static repair reviewers agreed with all 12 draft labels, and the actual
browser tests agreed on 12/12. The four reliability checks passed, including live
silence and preservation of the draft under a new session. All eight synthetic
speech clips were transcribed; raw word edits were 16/136 (11.76%). Many edits
are number formatting; examples also include `mean` -> `main`, `can` -> `ten`
and `untagged` -> `untag`. Listen before attributing an error to STT rather than
the synthetic pronunciation. Correction drafts are not actual learner edits.

The assessment comparison is inconclusive. Groq returned 429 for 12 RepoViva
cases and seven baseline cases. Returned assessment labels matched the draft
expectations, but unavailable cases prevent a credible accuracy comparison.
A separate diagnostic response exposed an 8,000-token rate-limit bucket; the
six-second request gap was insufficient for these prompt sizes. The optional
30-second replication gap above is a starting point, not a quota guarantee.
The original run's failures remain retained; no successful retry replaces them.
Both full prompts and every attempted system result are inspectable.

Provider references checked during implementation:
[Prisma REST](https://docs.gnani.ai/api/STT/speech-to-text),
[Groq structured outputs](https://console.groq.com/docs/structured-outputs).
