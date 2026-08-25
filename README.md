# Soul Sighted API

FastAPI port of the Xano `scripters` API group.

**New here? Read [STATE.md](STATE.md) first** — it says what is done, what is
already settled, and what to pick up next.

## Run it

```bash
docker compose up -d --wait          # Postgres 16 on port 5433
./.venv/bin/alembic upgrade head
./.venv/bin/pytest -q                # 105 tests
./.venv/bin/uvicorn app.main:app --reload
```

Port 5433, not 5432 — a native Postgres install already owns 5432 on this
machine, and it silently wins for localhost connections.

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
xano-export/      the dumped Xano backend — the spec this port is written against
tests/            105 tests
```

## The dump is the specification

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
