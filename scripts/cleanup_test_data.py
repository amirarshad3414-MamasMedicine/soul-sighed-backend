#!/usr/bin/env python3
"""Delete the rows a capture run created in live Xano.

Deletes through the Metadata API (`DELETE /workspace/1/table/{id}/content/{id}`),
which needs a token with **Workspace Content: Delete** — a wider scope than the
read-only one used for dumping. It deletes production rows, so:

  * it only ever touches ids recorded in responses/runs/<run>.cleanup.json,
    written by capture_responses.py — it never searches or guesses;
  * every id is fetched and shown before deletion, and anything whose row does
    not carry the parity-test marker is skipped, not deleted;
  * --dry-run is the default; deleting needs --i-have-approval --confirm.

    export XANO_PAT="$(cat ~/.config/xano/pat)"
    python3 scripts/cleanup_test_data.py --run r1                 # dry run
    python3 scripts/cleanup_test_data.py --run r1 --i-have-approval --confirm

Rows written *indirectly* by a capture — a `user` row from auth/signup, the
Insights row from submit_onboarding, a Purchases row — are listed by
capture_responses.py only when it saw their id in a response. Anything it could
not see is reported at the end as "check by hand" rather than hunted for.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from parity_lib import META_BASE, RUNS_DIR, TABLE_IDS, WORKSPACE

TEST_TAG = "parity-test"


def api(token: str, method: str, path: str):
    req = urllib.request.Request(
        f"{META_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode(errors="replace")


def looks_like_test_row(row) -> bool:
    """The marker capture_responses.py stamps on everything it creates."""
    return TEST_TAG in json.dumps(row, default=str)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", required=True, help="the run label to clean up")
    p.add_argument("--i-have-approval", action="store_true")
    p.add_argument("--confirm", action="store_true",
                   help="actually delete (default is a dry run)")
    p.add_argument("--force-unmarked", action="store_true",
                   help="also delete recorded rows that carry no test marker")
    args = p.parse_args()

    manifest = RUNS_DIR / f"{args.run}.cleanup.json"
    if not manifest.is_file():
        print(f"No cleanup manifest at {manifest}. Nothing recorded for run "
              f"{args.run!r}.", file=sys.stderr)
        return 1
    rows = json.loads(manifest.read_text())["rows"]

    token = os.environ.get("XANO_PAT", "").strip()
    if not token:
        print("XANO_PAT is not set.", file=sys.stderr)
        return 1

    deleting = args.confirm and args.i_have_approval
    if args.confirm and not args.i_have_approval:
        print("--confirm needs --i-have-approval too (standing rule: no live "
              "Xano traffic without approval).", file=sys.stderr)
        return 2
    print(f"{'DELETING' if deleting else 'DRY RUN'} — {len(rows)} recorded rows "
          f"from run {args.run!r}\n")

    deleted = skipped = errors = 0
    for row in rows:
        table, rid = row["table"], row["id"]
        tid = TABLE_IDS.get(table)
        if tid is None:
            print(f"  ?  {table}/{rid}: unknown table, skipping")
            skipped += 1
            continue
        base = f"/workspace/{WORKSPACE}/table/{tid}/content"
        status, body = api(token, "GET", f"{base}/{urllib.parse.quote(str(rid))}")
        if status == 404:
            print(f"  -  {table}/{rid}: already gone")
            continue
        if status >= 400:
            print(f"  !  {table}/{rid}: GET failed {status} {body}")
            errors += 1
            continue
        marked = looks_like_test_row(body)
        if not marked and not args.force_unmarked:
            print(f"  ?  {table}/{rid}: no {TEST_TAG!r} marker — NOT deleting. "
                  f"Inspect it, then re-run with --force-unmarked if it is "
                  f"genuinely ours.")
            skipped += 1
            continue
        if not deleting:
            print(f"  ·  would delete {table}/{rid}"
                  f"{'' if marked else '  (unmarked!)'}")
            continue
        status, body = api(token, "DELETE",
                           f"{base}/{urllib.parse.quote(str(rid))}")
        if status >= 400:
            print(f"  !  {table}/{rid}: DELETE failed {status} {body}")
            errors += 1
        else:
            print(f"  ✓  deleted {table}/{rid}")
            deleted += 1

    print(f"\n{deleted} deleted · {skipped} skipped · {errors} errors")
    print(
        "Check by hand, since a capture cannot always see the ids it creates:\n"
        f"  · `user` rows for {TEST_TAG}+{args.run}-*@soul-sighted.test\n"
        "  · the `Insights` row from submit_onboarding (child_id above)\n"
        "  · any `Purchases` row, if a Stripe test event was replayed\n"
        f"  · `onboarding_visit` rows for session_id {TEST_TAG}-{args.run}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
