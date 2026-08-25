# Open parity questions

Things the XanoScript does not fully determine, and which only a real response
from the live Xano API can settle. Answering them means sending requests to
production, which is **gated on Amir's approval** (migration plan, Phase 8).

Each entry names the assumption currently coded, so a wrong guess is one edit.

| # | Question | Answer | How settled |
|---|---|---|---|
| 1 | What HTTP status does a `precondition` with **no** `error_type` return? Used by `auth/login` for "Invalid Credentials." | **500**, `{"code":"ERROR_FATAL","message":...,"payload":""}` — a bare precondition throws a fatal error, it is not a 4xx | **MEASURED** run1, 2026-08-25 (`004_auth_login__error_bad_credentials`) |
| 2 | What is the exact error body? `{code, message, payload}`? | **Confirmed** `{code, message, payload}`, and **payload is `""`** for a precondition, not null | MEASURED run1 (every error pair) |
| 3 | Does `error_type = "unauthorized"` return 401 (vs `accessdenied` → 403)? | signup-duplicate uses `accessdenied` → **403** confirmed; a bare `unauthorized` was not exercised (login uses no type → fatal) | MEASURED run1 (`002_auth_signup__error_duplicate`) |
| 4 | Does Xano return `{"predictions": []}` or an error when Google returns `ZERO_RESULTS`? | **empty list** confirmed | MEASURED run1 (`018_places_autocomplete__zero_results`) |
| 5 | Key order in JSON objects. | order-independent; the diff compares that way | by design |
| 6 | What does an **input-filter** rejection return? `places_autocomplete` declares `q filters=trim\|min:3`. | 400 `{"code":"ERROR_CODE_INPUT_ERROR","message":"Input does not meet minimum length requirement of 3 characters","payload":{"param":"q"}}` — payload is an **object** here, not "" | **MEASURED** run1 (`019_places_autocomplete__error_too_short`) |

## New findings from run1 (2026-08-25) — need triage

- **`add_children` with an unresolvable `place_of_birth_id` → HTTP 500.** Xano
  crashes reading `google_response.response.result.result.geometry.location.lat`
  when Google returns no geometry (an invalid/NOT_FOUND place id). This
  **contradicts** the plan's Phase 6 assumption that a failed lookup "leaves
  lat/lon null and the record still saves" — that is the REQUEST_DENIED path; an
  invalid id is different and fatal. The port currently saves gracefully. Decide:
  reproduce the 500, or keep the graceful save as a deliberate fix.
- **`places_details` with a bad place id → HTTP 200**, body
  `{"payload":"Failed to fetch place details: NOT_FOUND ...","statement":"Throw Error"}`.
  Xano's `throw` inside the try/catch returns 200 with the error as the body. The
  port raises 500. Decide whether to reproduce the 200-with-error-body.

## Settled without needing a live call

- **`==?` in `add_children`** — behaves like SQL `=`; NULL never matches NULL.
  Proven by the 52 duplicate children rows, every group having a null dob.
- **`access=private` vs `internal`** — `private` columns (created_at) ARE
  returned; only `internal` (user.password) is suppressed. Proven against 505
  children and 332 Insights rows.
- **`created_at` defaults** — the Xano schema carries `default: "now"` on five
  tables; reproduced as a Postgres `server_default`.
