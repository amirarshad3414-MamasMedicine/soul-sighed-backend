# Soul Sighted API

FastAPI port of the Xano `scripters` API group.

**New here? Read [STATE.md](STATE.md) first** — it says what is done, what is
already settled, and what to pick up next.

## Run it

```bash
docker compose up -d --wait          # Postgres 16 on port 5433
./.venv/bin/alembic upgrade head
./.venv/bin/pytest -q                # 153 tests
./.venv/bin/uvicorn app.main:app --reload
```

Port 5433, not 5432 — a native Postgres install already owns 5432 on this
machine, and it silently wins for localhost connections.

**`pytest` TRUNCATEs the dev database.** The suite and the dev server share one
database, so running the tests deletes any account you just created in the
browser. Do not run it mid-session; separating the two is an open item.

**`--reload` watches `.py` files only.** Editing `.env` does *not* restart the
server — the old settings stay live, and you will spend a while debugging a
config change that never took effect. Restart by hand after touching `.env`.

### Pointing the frontend at this backend

In `../mamas-medicine-frontend`, create `.env.local`:

```
NEXT_PUBLIC_API_BASE=http://localhost:8000/
```

Every hardcoded Xano URL in that app reads this and falls back to Xano when it
is unset, so deleting the file switches back. Delete `.next` after changing it —
browser-side values are baked in at build time. CORS for `localhost:3000` is
already configured here.

Stripe cannot reach localhost, so a real payment can never complete the loop.
`scripts/simulate_purchase.py --list`, then `--child-id <uuid>`, grants a
purchase exactly as the webhook would so everything downstream can be tested.

## Layout

```
app/
  config.py       settings from .env
  database.py     async engine, per-request session
  main.py         app factory
  core/           security.py (JWT, Argon2), deps.py (current_user), errors.py
  models/         one module per domain, generated from the Xano schema
  schemas/        request/response shapes
  routers/        one per area
  services/       logic extracted from the Xano stacks
scripts/          dump_xano.py, gen_models.py, build_inventory.py
                  backup_tables.py      snapshot every table to JSON (read-only)
                  simulate_purchase.py  grant a purchase without Stripe (local only)
                  capture_responses.py  parity capture vs live Xano (needs approval)
                  diff_responses.py     replay those pairs here; shape diff
                  cleanup_test_data.py  delete rows a capture created
                  parity_lib.py         shared shape + Appendix A rules
xano-export/      the dumped Xano backend — the spec this port is written against
tests/            153 tests
```

## The dump is the specification

**It is gitignored and not in a fresh clone.** Regenerate it with
`XANO_PAT=$(cat ~/.config/xano/pat) python3 scripts/dump_xano.py --out xano-export`.

`xano-export/` holds the XanoScript source of every endpoint, function and
table. When behaviour is in question, read the `.xs` file — do not guess.

- `inventory.csv` — every endpoint with a triage decision
- `formats.md` — the wire-format contract the responses must satisfy
- `parity-questions.md` — what only a live Xano response can settle
- `REDACTIONS.md` — the one credential removed before committing

## Two standing rules

1. **Auth parity.** Every endpoint keeps exactly the auth Xano gives it. Only
   five require a token. Security hardening is separate work, after cutover.
2. **No live-Xano traffic without approval.** Reading structure through the
   Metadata API is fine; sending requests to the app's API is not.
