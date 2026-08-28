# Where this stands — 2026-08-25 (updated 2026-08-27)

FastAPI port of the Soul Sighted Xano backend. **Read this file first.**
The plan lives in the frontend repo at
`../mamas-medicine-frontend/xano-to-fastapi-migration-plan.md` (v4.1).

## Update — 2026-08-27 (read this on top of everything below)

**Now runs on Neon (Postgres 18), not local docker.** Set `NEONDB=<neon url>` in
`.env`; `app/config.py` `_prefer_neon` converts it to the asyncpg **direct**
endpoint (strips `-pooler`), drops libpq `?sslmode=`/`?channel_binding=`, and
applies TLS via `db_connect_args`. Remove `NEONDB` to fall back to docker (5433).
Alembic and the app both honour it. All Xano data is migrated in (indexes match
Xano). Tools: `scripts/migrate_from_xano.py`, `scripts/copy_local_to_neon.py`.
The Neon DB currently has **test pollution** — re-migrate clean before cutover.

**Password answer shipped.** Xano hashes are peppered → unverifiable (settled).
`auth/login` now returns `PASSWORD_RESET_REQUIRED` (409) for any non-Argon2 hash;
the frontend redirects the user to reset, which re-hashes to Argon2. Deliberate
parity exception. Pushed as `c4ef1cb`; Neon support as `1fe1905`. **Frontend
changes for the redirect (+ the names-label fix) are uncommitted** — the user
pushes those.

**Klaviyo:** the marketing list-subscribe key (`pk_ab8…`) is **dead/revoked
(401)** in both `.env` and the live Xano checkout stack — subscribe silently
no-ops. The reading/teaser key is separate, lives in Vercel's env, and works.
Fix = a fresh valid key in the backend `.env`.

Everything below remains accurate except the "Postgres 16 / docker" runtime.

## Quick start

```bash
cd ~/Documents/soul-sighted-backend
docker compose up -d --wait        # Postgres 16 on port 5433 (5432 is taken by a native install)
./.venv/bin/alembic upgrade head
./.venv/bin/pytest -q              # 153 tests, all passing
                                   # NOTE: the suite TRUNCATEs the dev database.
                                   # Running it wipes whatever you just signed
                                   # up in the browser. Separating it is an open
                                   # item; for now, do not run it mid-session.
./.venv/bin/uvicorn app.main:app --reload
```

## Done

All **21** endpoints of the Xano `scripters` group are ported with tests.
`xano-export/inventory.csv` is the tracker — one row per endpoint, with a triage
column.

### The frontend has been run against this backend — 2026-08-25

The real product was driven through a browser against this port, with live
Google, Stripe and insight-provider keys and the real Klaviyo flow. **Both
funnel variants complete end to end**: child and parent, all 17 stages tracked,
passwordless registration, geocoding, a real AI reading, Stripe session created,
purchase recorded, password set, and the insight email delivered to a real
inbox. 17 of 21 endpoints have now been exercised locally.

That run found **four defects the 147 passing tests could not**, every one a
data-shape difference hidden by a mocked external service:

| Defect | Impact had it shipped |
|---|---|
| Stripe `line_items` sent as Python repr, not bracket notation | **no purchase could complete** |
| Insight row not JSON-serialisable in `send_insight` | **no paying customer received their reading** — and it failed silently |
| `<input type="time">` sends `"14:30"`, rejected as a datetime | no reading for anyone who filled in a birth time |
| omitted optional text sent as `null`, provider type-checks | no reading for anyone who skipped the free-text question |

**The lesson worth keeping: a green test suite and a clean parity diff did not
mean the product worked.** Mocked externals cannot catch an encoding error, and
the parity capture sends hand-built requests, so it validates the
reconstruction rather than what the browser actually sends. Both are necessary;
neither is sufficient. Exercise the real UI before trusting either.

`scripts/simulate_purchase.py` posts the webhook body Stripe would, so the
post-purchase flow can be tested without a card (Stripe cannot reach localhost).
It refuses any non-local target.

**Measured, and it settles an open question:** Klaviyo delivered the
`Insight Ready` email **~20 minutes** after accepting the event. The reset OTP
expires in 300 seconds, so Klaviyo cannot carry that email — see item 2 below.

The **Phase 8 parity tooling exists** as of 2026-08-25 and has sent no live
traffic. Four files in `scripts/`, plus 33 tests on the diff logic itself:

| Script | What it does |
|---|---|
| `parity_lib.py` | shared shape comparison + Appendix A as executable rules |
| `capture_responses.py` | the 28 targeted calls of plan 1.4 against live Xano |
| `diff_responses.py` | replays those pairs against the local app; shape diff |
| `cleanup_test_data.py` | deletes the rows a capture run created |
| `backup_tables.py` | snapshots every table to JSON — 1,488 rows, ~8 MB, under two minutes. Read-only. Step one of the data migration |
| `simulate_purchase.py` | posts the Stripe webhook body locally, so the post-purchase flow is testable without a card. Refuses non-local targets |

`python3 scripts/capture_responses.py --list` prints the call plan and its
coverage and **sends nothing** — start there. Capture refuses to run without
`--i-have-approval`, and its write calls need `--allow-writes` on top. The plan
currently covers all 21 PORT endpoints, so the 8.3 coverage gate can pass.

The diff sends no Xano traffic at all: it calls the local app in-process, so
nothing needs to be running. It compares **shape, not values** — status, key
sets, JSON type per key, null-vs-empty, error bodies, Appendix A formats —
because Xano holds real data and FastAPI holds seed data (plan 8.2). Where the
live response contradicts Appendix A, reality wins: that key is excused locally
and both sides are reported, per key, so one drift cannot blind the rest of the
body.

Four are **deliberately not ported**, all Memberstack-era: `validate_user`,
`sync_user`, `sync_purchase`, `dashboard_state`. The last cannot succeed today
regardless — it requires `child.user_01_id` to match, and that column is null in
all 505 rows. **The `User_01` table and its 33 rows stay. Amir's decision.**

## Settled facts — do not re-derive these

| Question | Answer | How it was settled |
|---|---|---|
| Password hashes exportable? | **YES — this reverses the earlier answer.** The old "no" was inferred from `visibility = "internal"` on the column, on the assumption that hid it from the Metadata API too. It does not: `internal` hides the field from the *app* API (`auth/me`), while `GET /workspace/1/table/1/content` returns it. A full table backup on 2026-08-25 came back with **84 non-empty hashes**, format `<16 hex>.<64 hex>` — an 8-byte salt and a 32-byte digest, so salted SHA-256 family, not bcrypt. **Still unanswered: whether the port can VERIFY a login against them**, which needs the exact algorithm. If it can, the forced password reset, the ~200-email reset wave and the whole email-transport problem disappear. One test settles it — see Next item 1. | `scripts/backup_tables.py`, 2026-08-25 |
| How long does Klaviyo take to deliver? | **~20 minutes** from accepting the event to the mail arriving. Fine for `Insight Ready`; fatal for the OTP, which expires in 300s | measured twice, 2026-08-25 |
| What moves Insights `processing → ready`? | Nothing external — it is an inline retry loop inside `submit_onboarding`. No background tasks, triggers or middleware exist at all | the dump |
| What does `==?` do? | Behaves like SQL `=` — NULL never matches NULL | 52 duplicate children, every group with a null dob |
| `access=private` vs `internal`? | `private` IS returned (created_at); only `internal` is suppressed | 505 children + 332 Insights rows |
| Which API group is real? | Group 4 `scripters` only. Groups 1–3 are Xano's starter template, group 5 is the Stripe template writing the empty `session` table | request history, zero traffic |
| Where is the live Stripe webhook? | `POST api:uUEiFEze/checkout` in group 4, **not** group 5's `webhooks` | the source; `session` has 0 rows, `Purchases` 400+ |

## Rules already agreed with Amir

1. **Auth parity.** Every endpoint keeps exactly the auth it has in Xano.
   Nothing gains a lock, nothing loses one. Only five require `auth = "user"`.
2. **No live-Xano traffic without approval.** Reading structure via the Metadata
   API is fine. Sending requests to the app's API is not — the write replays
   create real rows on real accounts.
3. **Data migration is out of scope** for now, planned separately later.

## Next, in order

1. **Settle the password-hash question — do this first, it is the cheapest way
   to delete the largest blocker.** The hashes ARE exportable (see the settled
   table). What is unknown is whether this port can verify a plaintext against
   one. Create a single user through the live Xano API with a password you
   choose, read that row's hash back through the Metadata API, and try the
   candidate algorithms locally against the known pair — salted SHA-256 in its
   usual arrangements, then PBKDF2/HMAC. A match removes the forced reset, the
   reset wave, and item 2 below entirely. Needs approval: it is one write to
   live Xano, and `cleanup_test_data.py` removes the row afterwards.

2. **Triage decisions — Amir's, and several change code.** See the table in the
   plan: the duplicate-children index, the 7 stuck insights, whether birth times
   should reach the calculation, `update_password`, Stripe signature checks.
   Two more were added by the first live parity capture: `add_children` returns
   HTTP 500 in Xano when a birthplace will not resolve (the port saves the child
   with blank coordinates instead), and `places_details` answers HTTP 200 with
   the error inside the body (the port returns 500).
3. **Fix how the OTP email is sent — but do item 1 first, it may delete this.**
   This is only mandatory *if* the hashes turn out to be unverifiable and the
   forced reset stands. Reset mail goes out through a personal Gmail with
   credentials inline and will not survive ~200 resets at once — Gmail's cap,
   and no SPF/DKIM alignment with the brand domain, so it lands in spam, and
   under a forced reset spam means locked out. Even with no reset wave, the
   day-to-day reset path still runs on a personal Gmail account.

   **Scope, corrected 2026-08-25.** This used to read "replace the email
   transport", which implied the `Email` queue and its cron. Those are dead
   (see the map below). It is two routes: `forgot-password` (the OTP) and
   `send-teaser`, both sending to customers through Gmail.

   **Do not route the OTP through Klaviyo** without checking one thing first.
   It looks attractive — Klaviyo already sends this product's customer mail on
   a verified domain — but Klaviyo is a marketing platform, and a flow will not
   deliver to a profile that has unsubscribed or been suppressed. That would
   tie "can reset my password" to "accepts marketing", and at cutover every
   password user needs a reset. **And latency now settles it outright: measured
   2026-08-25, Klaviyo delivered ~20 minutes after accepting the event, while
   the OTP expires in 300 seconds.** A code arriving four times later than its
   own expiry is useless on every attempt. Klaviyo does offer transactional
   sending that bypasses suppression, but the latency disqualifies it here
   regardless unless that mode is demonstrably faster.

   Default recommendation: a transactional provider (Resend/Postmark/SES) on a
   verified soul-sighted.com domain, for the OTP and the teaser. That is what
   `EMAIL_PROVIDER_API_KEY` and `EMAIL_FROM` in `.env` are for; they stay.
4. **Re-run the parity capture.** Run 1 went out 2026-08-25 (approved): 26
   pairs, 22 shape-clean, four port bugs found and fixed. The four remaining
   mismatches all trace to one stale Google place id in the test data, since
   corrected in the script — a re-capture should reach 26/26. Two calls stay
   manual because they reach Stripe: `create_checkout_session` needs a Stripe
   **test** key, and `checkout` must be captured by firing a test event
   (`stripe trigger checkout.session.completed`), never by POSTing a
   handwritten body — that would write a real Purchase. **Note what the diff
   cannot do:** it sends hand-built requests, so it validates the
   reconstruction, not what the browser sends. It found four bugs; driving the
   real UI found four more, and worse ones.
5. Smaller: `profile_tables.py` + `xano-export/formats.md` (Appendix A was
   derived by hand for two tables, not generated for all 13); webhook
   idempotency (the no-account branch of `checkout` does not dedupe); Sentry;
   load tests; deployment; the six hardcoded Xano URLs in the frontend
   (**line 111, not line 4, is the real one in `forgot-password`** — line 4
   declares an unused `XANO_BASE`, so repointing it looks right and changes
   nothing); separating the test database from the dev one.
6. **Data migration plan** — still the real gate on cutover. Production
   Postgres is empty. `scripts/backup_tables.py` already exports all 1,488 rows
   (~8 MB, under two minutes) and is step one of this.

## Known defects, reproduced on purpose

Each has a test that documents it. If one starts failing, someone fixed
something deliberately — that is not a regression.

- `update_password` takes an email and a new password, with no auth and no check
  that `verify_otp` ran. Account takeover from an address alone.
- `checkout` (the Stripe webhook) has no signature verification.
- `add_children` lets duplicates through whenever the dob is null. 52 duplicate
  rows exist; one child is recorded 22 times.
- Birth times are collected, confirmed on screen, and never used. All 331 live
  payloads carry `T00:00`.
- `submit_onboarding` generates readings with no purchase check — the
  precondition is commented out in Xano.
- Seven Insights rows are stuck at `processing` forever, because the row is
  written before a retry loop that can die with the request.
- A failed login answers **HTTP 500 `ERROR_FATAL`**, not 401 — a Xano
  precondition with no `error_type` throws rather than returning a 4xx.
  Measured against live Xano, not assumed.

## Defects found in the FRONTEND — these are live on the production site

Found while driving the real product on 2026-08-25. None are migration
problems; all three are broken against Xano today. Fixed in the frontend repo
but **not yet committed there**.

- **`/signup` cannot create an account.** The submit handler was attached to the
  inner `FormForm`, but the devlink `FormWrapper` only ever calls its *own*
  `onSubmit` and overwrites the child's — so the handler never ran, no request
  was sent, and the wrapper still displayed "Thank you! Your submission has been
  received!". A false success on every attempt.
- **`onboardingMain` read `data?.child_id`** from the add-children response,
  which returns the row under `id`. Always undefined, so `submit_onboarding` was
  called with no child. The signup-flow page already had the `|| id` fallback;
  this one did not.
- **The "your insight has been sent to your email" popup is unconditional**, and
  the block that would have sent it is empty (`if (email) { }`). Nothing sends
  there. The insight email actually comes from the backend, so users are told
  something true by accident on one path and untrue on another. Not yet fixed —
  it is a behaviour change, not a port fix.

## The dump is not in git

`xano-export/` holds the XanoScript source of every Xano object and is the
specification this port is written against — but it is **gitignored**, because
it reproduces verbatim whatever the stacks contain, including the Klaviyo key
hardcoded in `checkout`. A fresh clone will not have it.

Regenerate it with a valid Metadata API token:

```bash
XANO_PAT=$(cat ~/.config/xano/pat) python3 scripts/dump_xano.py --out xano-export
```

Four derived, secret-free files stay tracked: `inventory.csv`, `formats.md`,
`parity-questions.md`, `REDACTIONS.md`.

`xano-export/responses/` is gitignored for a second reason: a capture run stores
live response bodies, which carry mothers' emails and children's names and birth
dates. Pairs land in `responses/pairs/`, cleanup manifests in `responses/runs/`.

## Environment

`.env` is gitignored and **eight keys are blank** — Stripe, Klaviyo, both Google
keys, the insight API URL, email. The code runs and the tests pass without them
(every external call is replaced in tests), but nothing can reach a real service.

`~/.config/xano/pat` holds the Metadata API token. **It expires 2026-08-31 and
was pasted into a chat transcript, so it should be rotated.**
