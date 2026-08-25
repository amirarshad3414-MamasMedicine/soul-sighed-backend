# Where this stands — 2026-08-24

FastAPI port of the Soul Sighted Xano backend. **Read this file first.**
The plan lives in the frontend repo at
`../mamas-medicine-frontend/xano-to-fastapi-migration-plan.md` (v4.1).

## Quick start

```bash
cd ~/Documents/soul-sighted-backend
docker compose up -d --wait        # Postgres 16 on port 5433 (5432 is taken by a native install)
./.venv/bin/alembic upgrade head
./.venv/bin/pytest -q              # 105 tests, all passing
./.venv/bin/uvicorn app.main:app --reload
```

## Done

All **21** endpoints of the Xano `scripters` group are ported with tests.
`xano-export/inventory.csv` is the tracker — one row per endpoint, with a triage
column.

Four are **deliberately not ported**, all Memberstack-era: `validate_user`,
`sync_user`, `sync_purchase`, `dashboard_state`. The last cannot succeed today
regardless — it requires `child.user_01_id` to match, and that column is null in
all 505 rows. **The `User_01` table and its 33 rows stay. Amir's decision.**

## Settled facts — do not re-derive these

| Question | Answer | How it was settled |
|---|---|---|
| Password hashes exportable? | **No.** `user.password` is `access=internal` | table schema |
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

1. **`git init` is done; there is no remote.** Add one when you want it.
2. **Triage decisions — Amir's, and several change code.** See the table in the
   plan: the duplicate-children index, the 7 stuck insights, whether birth times
   should reach the calculation, `update_password`, Stripe signature checks.
3. **Replace the email transport.** Password hashes are not exportable, so the
   forced reset is confirmed, which makes this mandatory. Today reset mail sends
   from a personal Gmail with credentials inline — it will not survive ~200
   resets. `KLAVIYO_API_KEY` and the Gmail credentials both need rotating.
4. **Parity comparison** — needs Amir's approval. Three scripts named in the
   plan do not exist yet: `capture_responses.py`, `diff_responses.py`,
   `cleanup_test_data.py`.
5. Smaller: `profile_tables.py` + `xano-export/formats.md` (Appendix A was
   derived by hand for two tables, not generated for all 13); webhook
   idempotency (the no-account branch of `checkout` does not dedupe); Sentry;
   load tests; deployment; the six hardcoded Xano URLs in the frontend.
6. **Data migration plan** — still the real gate on cutover.

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

## Environment

`.env` is gitignored and **eight keys are blank** — Stripe, Klaviyo, both Google
keys, the insight API URL, email. The code runs and the tests pass without them
(every external call is replaced in tests), but nothing can reach a real service.

`~/.config/xano/pat` holds the Metadata API token. **It expires 2026-08-31 and
was pasted into a chat transcript, so it should be rotated.**
