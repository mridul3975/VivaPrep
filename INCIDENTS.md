# Running application incidents

Open **Debug → Running incidents**. This is separate from static code-repair
practice. Start the explicitly prepared booking incident, use a runnable Python
source already uploaded in Study, or upload a `.py` app / project ZIP.

The first version supports Python HTTP apps with disposable local data and an
optional local SQLite database. It does not start arbitrary frameworks, external
databases, services requiring credentials, Docker Compose projects or remote
production systems. The base E2B template supports the prepared standard-library
app; other dependencies must already exist in an owner-configured template.
There are no automatic package installs or arbitrary shell commands from speech.

## Learner flow

1. Setup selects a controlled, exact source mutation and bounded checks. Uploaded
   code is treated as data on the Flask server. The original runs remotely and
   must pass the reproduction plus regression checks. The changed app must start
   and demonstrably fail the reproduction. Otherwise setup fails and refunds its
   allowance; a prepared project is never substituted for an uploaded project.
2. Record an instruction or hypothesis, or type one. Prisma transcribes the
   recording; review/edit it and explicitly confirm before preparing a plan.
   The original transcript and final wording stay distinguishable. No automatic
   terminology replacement or technical-claim repair is performed.
3. “Send two booking requests at the same time” becomes a preview of a concurrent
   request pair. Simple English/Hinglish/Hindi imperatives can reuse the verified
   reproduction without an AI call. Other instructions use bounded AI planning.
   An explicit different HTTP method/path is never silently mapped to that pair.
4. Nothing executes until **Run approved experiment** is clicked. Experiments
   address only localhost inside that project's sandbox. Each run starts with
   fresh application files/data; persistent cross-experiment live state is not
   supported in this release. A single experiment can send 1–4 sequential or
   concurrent requests. Different experiments cannot contaminate each other.
5. Inspect actual requests, responses, database before/after snapshots, executed
   source lines and logs. Line coverage is bounded and does not prove exact event
   timing. Hypothesis feedback can quote source lines and refer to those actual
   observations; it remains advisory, not a test result or correctness score.
6. Edit/save a project file. This invalidates the current experiment plan and
   any previous repair verification for different code. Investigation drafts,
   transcript confirmation and patches persist in PostgreSQL.
7. **Test my fix** prepares the original incident plus all regression checks.
   Approve execution. Only matching actual HTTP/database observations can mark
   the current repair verified. A custom investigation is unscored; an AI opinion
   cannot pass a repair. Finite tests are not proof for every possible input.

The prepared example has one remaining seat. Its original uses an atomic
conditional update. The controlled version separates an availability read from
an unconditional decrement, with a small deliberate delay to reproduce the
interleaving. Two concurrent requests then create two bookings and a negative
seat count. The example is synthetic and explicitly labeled prepared; it is not
a claim about a defect in the learner's original project.

## Execution and ownership boundary

Production uses E2B SDK 2.5.0 and a fresh remote sandbox per experiment batch.
The default base image is used unless `E2B_TEMPLATE_ID` is configured. Outbound
internet is disabled. RepoViva's Groq, Gnani, Google, database, session and E2B
keys are never copied into the student VM. The SDK control connection remains
on the Flask side. No user code is run by Flask or a subprocess on its host.

The trusted remote supervisor runs as root; the project runs as unprivileged
UID/GID 65534 with empty supplementary groups and an explicit environment limited
to PATH, PORT, HOME and PYTHONUNBUFFERED. Source tracing collects file/line/thread
observations, not local variable values. The app has per-process CPU, memory,
file-size, descriptor and process limits. Remote commands are fixed supervisor
commands, never model-generated shell. A batch times out after 45 seconds; its
VM has a 65-second lifetime and is killed in `finally`. A failed kill still leaves
the provider TTL. An expired/interrupted job never fabricates a new result.

Uploads are bounded to 1 MiB compressed, 256 KiB extracted text, 30 files and
32 KiB per file. Files stay in PostgreSQL until copied to the VM. ZIP content is
read as bounded UTF-8 text, never extracted on the application host. Absolute,
parent, hidden, duplicate and symlink paths, credential formats, binaries and
encrypted entries are rejected. Omit `.env`, dependencies and real database
files. Uploaded source and bounded execution excerpts are sent to Groq for
planning; the entire execution bundle goes to E2B. The source-analysis window
is explicitly bounded to 9,000 source characters with exact line ranges and
omissions identified. Unsupported/omitted context must fail setup rather than
be invented.

The supervisor records requests and SQLite snapshots itself. Host validation
recomputes pass/fail against the original fixed checks, binds observations to a
source fingerprint and copies trace quotes from that exact snapshot. Browser
submissions cannot claim a pass or supply their own execution results. A learner
could still deliberately overfit finite tests; this is learning practice, not
tamper-proof proctoring or a security certification.

Only authenticated owners (including distinct guest identities) can access a
lab. CSRF protects writes. Guest upgrades transfer incident ownership and usage;
jobs bind to an internal lease so an upgrade does not orphan the in-flight result.
Deleting the account/expired guest cascades to its labs. A lab is an independent
project snapshot; deleting a Study file does not delete that incident project.
Delete saved incidents from their own list.

## Limits and recovery

- `DAILY_INCIDENT_LIMIT=10` per signed-in owner/day.
- `GUEST_INCIDENT_LIMIT=3` per guest/day.
- `SHARED_INCIDENT_LIMIT=30` provider attempts across all owners/day, limiting
  sandbox spend. Failed attempts remain in this shared ceiling even when the
  personal allowance is refunded. Guest expiry/account deletion anonymizes an
  entry instead of resetting this shared ceiling.
- At most one active job per owner, two globally, and 30 saved labs per owner.
- Setup (original + controlled failure) consumes one incident use. Each approved
  experiment consumes another. Known setup/provider failures refund the personal use;
  an interrupted call with unknown provider outcome remains counted.
- AI investigation responses use the existing answer-review allowance. Replay,
  trace, test-fix and simple concurrent-request shortcuts require no Groq call.
  Audio uses the existing transcription allowance. Limits reset at midnight UTC.

Profile and the incident catalogue show remaining incident uses. Jobs are stored
with leases and run in bounded background threads, so requests return 202 rather
than waiting for remote startup. Polling can recover after a connection failure.
Expired leases expose an interruption message and preserve code/older evidence.
Provider failures never convert into a successful repair. Saved drafts and
previous execution remain inspectable while the runner is unavailable.

## Add E2B after the implementation

1. Create/sign into an [E2B account](https://e2b.dev/). Open the
   [dashboard](https://e2b.dev/dashboard) and its API keys section; create/copy an
   API key. Do not post it in chat or commit it. Sandbox runs may consume credits.
2. Add this **privately** to the existing root `.env`:

   ```dotenv
   E2B_API_KEY=your_actual_key
   ```

   Leave `E2B_TEMPLATE_ID` blank for the prepared standard-library booking app.
   A custom dependency template is optional later; it must include Python 3.
3. Local setup uses `pip install -r requirements.txt`, then
   `python -m backend.database migrate`, then restart Flask. Under WSL use the
   project's `.venv/bin/python`. Do not run the destructive test fixtures against
   the app database. Migration 007 only creates incident tables/indexes.
4. In Render's service **Environment**, add `E2B_API_KEY` with the same private
   value. Deploy these code changes and save/restart the service. Keep the
   existing Groq/Gnani/database/session settings. The container startup migrates
   PostgreSQL. Keep one service instance; the database admission lock coordinates
   bounded jobs. No client-side `VITE_` sandbox key is used.
5. Open Debug → Running incidents → Start booking incident. Confirm original
   checks pass, the last-seat incident fails, and a reviewed spoken instruction
   triggers real requests only after approval. Restore the conditional update,
   approve Test my fix and verify all four checks pass. This is the required live
   E2B verification; local tests below do not replace it.

Optional local operator check after adding the key: `python -m checks.live.incidents`.
It makes real E2B calls and creates three short-lived VMs to check the original,
controlled failure and restored repair. This uses provider credits directly,
outside a learner's application quota. It has not been run without the key.

Without a key, the app shows that running incidents are unavailable and disables
starting them. Existing code repairs remain available. It never substitutes a
simulated VM or fake success screen.

## Verification boundaries

`checks/test_incidents.py` covers bundle boundaries, local-only plans, remote SDK
configuration/cleanup, replay/patch persistence, ownership, CSRF, quota/refunds,
stale evidence, transcript confirmation and invalid citations using offline
provider/observation fixtures. These tests do not establish live E2B execution.

The developer separately exercised the actual supervisor and prepared app in
disposable Linux mount/PID/network namespaces with a chroot and unprivileged app,
real concurrent HTTP requests and SQLite. The original and restored app pass;
the controlled race and a plausible wrong repair fail. This local development
adapter is private, not shipped, not a production fallback and not a microVM
certification. Browser development checks use that adapter with actual Prisma
and Groq and synthetic stock speech. The E2B API key is intentionally pending
the owner's setup; cloud creation/network isolation/cleanup remain unverified.

Provider API reference: [E2B Sandbox SDK 2.5.0](https://docs.e2b.dev/sdk-reference/python-sdk/v2.5.0/sandbox_sync).
