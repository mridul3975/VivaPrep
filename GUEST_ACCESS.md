# Guest access and the prepared Python example

Visitors can choose **Try as guest** without an email or Google credential.
Each gets a randomly generated identity and an opaque, revocable session in the
existing HttpOnly/SameSite cookie. Uploads, history, practice and Debug remain
owner-scoped. Guest work is temporary for up to 24 hours; clearing cookies or
ending the session can prevent access. Google sign-in while the guest session
is valid transfers sources, practices, drafts, attempts, Debug runs and usage
into the account and revokes guest tokens. Existing account material stays in
History, with at most one active source.

## The example

Study and Debug both offer **Use Python example**. The backend supplies a correct
`is_prime` function, explicitly labeled as prepared. Study has three True/False
return-value questions and deterministic feedback. Debug changes the loop boundary
so 9 is accepted as prime. Restoring the source earns 100/100 without a provider
request. Different repairs can receive a quota-controlled AI review. Reopening
the sample reuses owned prepared practice/Debug where possible.

Personal uploads use the existing source-grounded AI flow, without silent sample
fallbacks. Prepared questions, Boolean feedback, exercise creation and source
comparison remain free when personal or shared AI allowances are exhausted.
Voice and AI review of alternative repairs still use their allowances.

## Limits

| Limit | Default | Environment variable |
|---|---:|---|
| AI question sets or Debug generations per guest/day | 1 | `GUEST_QUESTION_LIMIT` |
| AI answer/repair reviews per guest/day | 3 | `GUEST_REVIEW_LIMIT` |
| Transcriptions per guest/day | 1 | `GUEST_TRANSCRIPTION_LIMIT` |
| All guest question generations/day | 60 | `GUEST_DAILY_QUESTIONS_LIMIT` |
| All guest reviews/day | 180 | `GUEST_DAILY_ANSWERS_LIMIT` |
| All guest transcriptions/day | 30 | `GUEST_DAILY_TRANSCRIPTIONS_LIMIT` |
| New guest identities/day | 200 | `GUEST_DAILY_SESSIONS_LIMIT` |
| New guest identities/network/day | 10 | `GUEST_SESSIONS_PER_NETWORK` |

Reservations are atomic, count in-flight requests and refund known failures.
Daily limits reset at midnight UTC and persist across server restarts with
PostgreSQL. Guest aggregate use stays counted after upgrade; ordinary account
allowances are separate. Personal guest use transfers into account daily usage.
Ending/reopening a guest session in the same browser reuses its identity/quota
while valid. Cookie clearing can create another guest; aggregate and network
limits bound the impact, but cannot guarantee one allowance per person.

Guests can keep five personal files plus the example under existing upload-size
limits. On new guest admission, accounts older than 24 hours are deleted with
their linked work; deletion is not promised at the exact expiry instant. Memory
development storage resets on restart; History and Debug still need PostgreSQL.

## Deployment

Migration **004_guest_limits.sql** adds the aggregate reservation table. Run the
existing migration startup before serving traffic. Settings have defaults;
`.env.example` lists overrides.

Network admission stores only an HMAC hash of the request peer. Behind a proxy,
set `TRUSTED_PROXY_HOPS` only after verifying the host's forwarded chain. It
controls ProxyFix's `x_for` count and defaults to zero. See [Flask's proxy
guidance](https://flask.palletsprojects.com/en/stable/deploying/proxy_fix/).
On Render without trusted hops, the small network threshold is disabled so all
visitors are not grouped under a shared proxy address; global admission and AI
limits remain active. See [Render's proxy
behavior](https://render.com/articles/how-render-handles-ddos-attacks). Never
trust forwarded client headers on a directly exposed server.

## Checks

`checks/test_guests.py` covers actual guest cookies, CSRF, isolation, free examples,
quotas, concurrent requests, refunds, logout/resume and transfer/revocation.
The backend suite passed 117 tests with isolated PostgreSQL. Browser checks used
real anonymous guest creation and local Flask/PostgreSQL at 1440/390/360px;
own-file AI was simulated. Real Google account and microphone interaction were
not exercised. See `checks/guest_access_result.json`.
