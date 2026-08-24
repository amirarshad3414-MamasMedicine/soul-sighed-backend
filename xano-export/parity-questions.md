# Open parity questions

Things the XanoScript does not fully determine, and which only a real response
from the live Xano API can settle. Answering them means sending requests to
production, which is **gated on Amir's approval** (migration plan, Phase 8).

Each entry names the assumption currently coded, so a wrong guess is one edit.

| # | Question | Currently assumed | Where |
|---|---|---|---|
| 1 | What HTTP status does a `precondition` with **no** `error_type` return? Used by `auth/login` for "Invalid Credentials." | 401 | `app/routers/auth.py` |
| 2 | What is the exact error body? `{code, message, payload}` is Xano's documented convention but unconfirmed. `message` is certain — the frontend reads it. | `{"code","message","payload"}` | `app/core/errors.py` |
| 3 | Does `error_type = "unauthorized"` return 401 (vs `accessdenied` → 403)? Both exist as distinct types, so the split is inferred from HTTP convention. | 401 | `app/core/errors.py` |
| 4 | Does Xano return `{"predictions": []}` or an error when Google returns `ZERO_RESULTS` for autocomplete? The stack only special-cases `REQUEST_DENIED`. | empty list | `app/routers/places.py` |
| 5 | Key order in JSON objects. Irrelevant to correctness; the diff must compare order-independently. | order-independent | `scripts/diff_responses.py` |

## Settled without needing a live call

- **`==?` in `add_children`** — behaves like SQL `=`; NULL never matches NULL.
  Proven by the 52 duplicate children rows, every group having a null dob.
- **`access=private` vs `internal`** — `private` columns (created_at) ARE
  returned; only `internal` (user.password) is suppressed. Proven against 505
  children and 332 Insights rows.
- **`created_at` defaults** — the Xano schema carries `default: "now"` on five
  tables; reproduced as a Postgres `server_default`.
