# Startup and connection recovery

The old UI made one `/health` request with a 30-second deadline. Failure latched
`backendReady=false` until manual retry. Every non-200 response was also classified
as an old API version, even though `/health` deliberately returns 503 when storage
is temporarily unavailable. Visitors then saw a local-development instruction to
start Flask rather than a recovery state.

The live hosted `/health` responded HTTP 200, `study-v2`, PostgreSQL, in 1.86 seconds
during this investigation. The failure was not present during that observation;
historical Render/Neon outage logs were not available. The repository's Render
configuration specifies Free, but the manually selected hosting plan was not
verified. Render documents Free spin-down after 15 minutes idle and roughly one
minute to wake: https://render.com/docs/free#spinning-down-on-idle.

`connection.ts` retries only safe bootstrap GETs: `/health` and `/auth/session`.
There are at most three attempts, each with a 25-second deadline, separated by
1.5 and 3 seconds. Temporary 408/502/503/504, network failures and successful HTML
warm-up pages are retried. Authentication rejections are not retried. Session
bootstrap has a 90-second outer deadline and all requests stop on cancellation.

`useBackendConnection` distinguishes successful health, storage outages, connection
failures and genuine version mismatch. Visible pages retry failed health after
30 seconds and on focus/online/visibility return. Successful checks stop polling,
so this is not an artificial hosting keep-alive. Failed API connections or
database-unavailable responses trigger a fresh readiness check. AI-provider
rate-limit errors do not mark the app backend as unavailable.

Existing material and answer drafts stay mounted during reconnection. Success
clears the connection error automatically. A real API mismatch asks the visitor
to save work and reload; storage/network failures never say to restart Flask.
Uploads, answer submissions, transcription and AI generation are never replayed
automatically. Failed actions still need explicit resubmission by the user.

Checks: `npm --prefix frontend run check:connection`, production build/lint and
browser network-fault injection against isolated local Flask/PostgreSQL. These
prove client recovery, not elimination of hosting/database outages. No hosting
plan, billing settings, database timeouts or backend health semantics were changed.
The updated frontend needs redeployment before this applies to Render.
