# Wire-format contract

Derived from live rows, not from the OpenAPI spec — the spec describes declared
I/O, and none of what follows is expressible in it. FastAPI responses must match
these exactly: a correct query in the wrong shape still breaks the frontend.

Enforced in `app/schemas/base.py` and `app/models/*.py`, and asserted in
`tests/test_get_children.py`.

## Rules

| Kind | On the wire | Note |
|---|---|---|
| `created_at` | **integer, epoch milliseconds** — `1787561676634` | Not ISO. Appears in no XanoScript; Xano writes it from a `default: "now"` column |
| `date_of_birth` | **string `YYYY-MM-DD`** — `"2019-04-11"` | A different date format in the same row |
| uuid columns | **string** | `id`, `child_id`, `journey_id`, `request_id` |
| `user_id`, `real_user_id` | **integer** | Mixed PK conventions across tables |
| `lat`, `lon` | JSON number — float in 357 rows, plain integer in 148 | Model as float; do not assume a decimal point |
| JSON columns | **object** | `insights_api_payload` keys: `p1Lat p1Lon p2Lat p2Lon person_1 person_2` |
| booleans | **`false`** | Not `0`, not `""` |
| Missing keys | **never** — every row carries every key | Never enable `exclude_none` / `exclude_unset` |

## Null vs empty is per column, and the tables disagree

Not a matter of taste — it is what the live tables do.

| Table | Uses `null` | Uses `""` |
|---|---|---|
| `children` | `user_01_id`, `date_of_birth`, `time_of_birth`, `pronoun` | `name`, `relationship_focus` |
| `Insights` | *(nothing — no column is ever null)* | `status`, `deep_text`, `summary_text`, `teaser_text`, `last_error` |
| `Purchases` | `user_id`, `child_id`, `email` | — |

## Two rules this implies for the models

1. **`nullable` describes the column; `required` describes the input.** Treating
   "not required" as nullable lets NULLs into columns Xano forbids —
   `children.name` is `required=False, nullable=False`, and every live row holds
   `""`.
2. **No strict enums on Xano text columns.** Every one can hold `""`. `status` is
   documented `processing|ready|failed` but one row is empty;
   `relationship_focus` is documented `child|parent` but 384 of 505 are empty. A
   strict Enum rejects rows that exist today.

## Coverage

Verified against **505 `children`**, **332 `Insights`** and **200 `Purchases`**
rows. `user`, `Email`, `onboarding_visit`, `Journey` and `User_01` are covered by
their schema flags but have not been profiled against live rows — the
`profile_tables.py` script named in the plan is still to be written.
