# Google sign-in

RepoViva uses Google Identity Services directly. Students sign in with Google;
there is no email/password form, Clerk, or Supabase integration.

## Configure Google

1. Open [Google Cloud Console](https://console.cloud.google.com/) and choose a
   project. Configure Google Auth Platform branding and audience. For an external
   application in testing, add the Google accounts that will test it.
2. Create an OAuth client with application type **Web application**.
3. Add the exact origins used to open RepoViva under **Authorized JavaScript
   origins**. Local development uses `http://localhost:5173`; a local production
   check can use `http://localhost:8000`. Add the actual Render HTTPS origin when
   it exists. Origins include the scheme and port, without a path. If you open
   the app using `127.0.0.1`, register that origin separately.
4. Copy the client ID into the root `.env` as `GOOGLE_CLIENT_ID=...`. Keep a stable
   random `SESSION_SECRET` in that file too. It is ignored by Git. The sign-in
   button flow does not need a Google client secret or a redirect callback URL.
5. Install `requirements.txt` and restart Flask and Vite. Open the app and click
   **Sign in with Google**. Register any additional development port separately.

The Google script is loaded from Google's official URL. Only basic Google
identity is used; the app does not request access to Gmail, Drive, or Calendar.
The public client ID is returned by `/auth/session` at runtime, so changing it
does not require rebuilding React.

For Render, configure `GOOGLE_CLIENT_ID`, `SESSION_SECRET`, and
`SESSION_COOKIE_SECURE=1` alongside the existing provider keys. The Blueprint
already declares these values. Keep one worker and one service instance.

## Request flow

1. `GET /auth/session` returns the current student, a CSRF token, a sign-in nonce,
   the public Google client ID, and the session expiry time. It is not cached.
2. Google supplies an ID token to the browser callback. The browser sends it to
   `POST /auth/google` with the session's `X-CSRF-Token` header.
3. Flask verifies Google's signature, audience, issuer and expiry using
   `google-auth`, then checks the browser-bound nonce and verified identity.
4. Flask rotates the signed HttpOnly/SameSite cookie and creates a revocable
   session. The signed cookie contains a random session ID and browser security
   metadata; PostgreSQL stores only a hash of that session ID. Google ID tokens
   are not retained or stored in browser local storage.
5. Every study API requires a live signed-in session. Mutating requests also
   require `X-CSRF-Token`. Source and turn ownership uses Google's stable `sub`,
   not an email address or a user ID supplied by the browser.
6. `POST /auth/logout` revokes the server-side session and rotates cookie data.
   The frontend clears the workspace and releases microphone capture.

Invalid or expired authentication returns 401. Invalid CSRF returns 403.
Missing Google configuration or a Google verification outage returns 503;
neither condition enables anonymous study access. Static assets and `/health`
remain public.

Sessions last at most one hour and never outlive the sign-in ID token. With
`DATABASE_URL` configured, users and revocable login-session hashes persist in
PostgreSQL. A restart preserves unexpired sessions when `SESSION_SECRET` remains
stable; it does not extend their expiry. Saved uploads and practice survive login
expiry and are restored after the same Google identity signs in again. Each
identity has one active upload. See [POSTGRES.md](POSTGRES.md) for retention,
deletion and ownership.

A blank `DATABASE_URL` explicitly enables temporary development storage instead:
at most 1,000 live login sessions in one process, with sessions and study state
lost on restart. A configured PostgreSQL outage returns 503 without memory fallback.

## Verification

Run the regression suite from [checks/README.md](checks/README.md). Authentication
tests exercise Google's real verifier against a locally generated signing key,
including invalid signatures, audience, issuer, expiry and nonce. They also check
CSRF, ownership, cookie flags, session expiry and logout-cookie replay.

`checks/authentication_result.json` records the browser checks and their boundary.
The isolated browser fixture substitutes Google's SDK/certificates and AI/STT
responses. A real Google account sign-in must still be checked after the actual
client ID and its authorized origin are configured.

References: [Google setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid),
[server verification](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).
