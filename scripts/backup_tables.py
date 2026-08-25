#!/usr/bin/env python3
"""Snapshot every Xano table's rows to local JSON.

Read-only: it pages `GET /workspace/1/table/{id}/content` through the Metadata
API and writes what comes back. It sends nothing to the app's own API and
mutates nothing, so it is covered by the standing rule's read allowance.

    export XANO_PAT="$(cat ~/.config/xano/pat)"
    python3 scripts/backup_tables.py                    # -> backups/<stamp>/
    python3 scripts/backup_tables.py --out backups/pre-cutover
    python3 scripts/backup_tables.py --tables children,Insights

Two jobs in one script:

  * **the safety snapshot** — 1,488 rows across 8 tables, about 5 MB, under two
    minutes;
  * **the input to the data migration** (plan M9), which is what actually gates
    cutover. The JSON here is what gets loaded into Postgres.

**`user.password` will not be in the output.** The column is `access=internal`,
so the Metadata API suppresses it — this is the settled finding behind the
forced password reset, not a bug in this script. Every other column exports.
`manifest.json` records, per table, whether the row count came back as expected,
so a partial dump cannot quietly look complete.

The output contains real user data — emails, children's names, birth dates and
birthplaces. `backups/` is gitignored. Keep it that way.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://xnrw-fohw-scw8.a2.xano.io/api:meta"
WORKSPACE = 1
PER_PAGE = 100
PAUSE = 0.2  # the Metadata API rate-limits (429)

# Table name -> id, from xano-export/table/*.json (filename prefix is the id).
# account(2), event_log(3), agent_conversation(4), agent_message(5) and
# session(11) are Xano's starter/Stripe templates and hold no real rows; they
# are listed so --tables can still reach them, but skipped by default.
TABLES = {
    "user": 1, "User_01": 6, "children": 7, "Journey": 8, "Insights": 9,
    "Purchases": 10, "Email": 12, "onboarding_visit": 13,
}
TEMPLATE_TABLES = {"account": 2, "event_log": 3, "agent_conversation": 4,
                   "agent_message": 5, "session": 11}


def token() -> str:
    tok = os.environ.get("XANO_PAT", "").strip()
    if not tok:
        sys.exit('XANO_PAT is not set. Run: export XANO_PAT="$(cat ~/.config/xano/pat)"')
    return tok


def get_page(tok: str, table_id: int, page: int):
    query = urllib.parse.urlencode({"per_page": PER_PAGE, "page": page})
    req = urllib.request.Request(
        f"{BASE}/workspace/{WORKSPACE}/table/{table_id}/content?{query}",
        headers={"Authorization": f"Bearer {tok}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read()[:200].decode(errors='replace')}"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:200]}"


def dump_table(tok: str, name: str, table_id: int, out_dir: Path) -> dict:
    rows, page, expected, error = [], 1, None, None
    while True:
        body, err = get_page(tok, table_id, page)
        if err:
            error = err
            break
        items = body.get("items", body) if isinstance(body, dict) else body
        if isinstance(body, dict) and expected is None:
            expected = body.get("itemsTotal")
        if not isinstance(items, list):
            error = "unexpected response shape (not a list of rows)"
            break
        rows += items
        if len(items) < PER_PAGE:
            break
        page += 1
        time.sleep(PAUSE)

    path = out_dir / f"{name}.json"
    path.write_text(json.dumps(rows, indent=2, default=str))
    complete = error is None and (expected is None or len(rows) == expected)
    return {
        "table": name, "table_id": table_id, "rows": len(rows),
        "expected": expected, "complete": complete, "error": error,
        "bytes": path.stat().st_size, "file": path.name,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", help="output directory (default backups/<timestamp>)")
    p.add_argument("--tables", help="comma-separated subset, e.g. children,Insights")
    p.add_argument("--include-templates", action="store_true",
                   help="also dump the unused starter/Stripe template tables")
    args = p.parse_args()

    wanted = dict(TABLES)
    if args.include_templates:
        wanted |= TEMPLATE_TABLES
    if args.tables:
        known = TABLES | TEMPLATE_TABLES
        wanted = {}
        for name in (t.strip() for t in args.tables.split(",") if t.strip()):
            if name not in known:
                sys.exit(f"unknown table {name!r}. Known: {', '.join(sorted(known))}")
            wanted[name] = known[name]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out) if args.out else ROOT / "backups" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    tok = token()

    print(f"Backing up {len(wanted)} tables -> {out_dir}\n")
    results = []
    for name, table_id in wanted.items():
        info = dump_table(tok, name, table_id, out_dir)
        results.append(info)
        mark = "ok  " if info["complete"] else "FAIL"
        count = f"{info['rows']}"
        if info["expected"] is not None and info["expected"] != info["rows"]:
            count += f" of {info['expected']}"
        print(f"  [{mark}] {name:18} {count:>12} rows  "
              f"{info['bytes'] / 1024:8.1f} KB"
              + (f"  {info['error']}" if info["error"] else ""))
        time.sleep(PAUSE)

    total_rows = sum(r["rows"] for r in results)
    total_bytes = sum(r["bytes"] for r in results)
    incomplete = [r["table"] for r in results if not r["complete"]]

    manifest = {
        "taken_at": datetime.now(UTC).isoformat(),
        "workspace": WORKSPACE,
        "source": BASE,
        "total_rows": total_rows,
        "total_bytes": total_bytes,
        "incomplete": incomplete,
        "known_omission": (
            "user.password is access=internal and is NOT included. This is why "
            "cutover forces a password reset; see the migration plan, Phase 7."
        ),
        "tables": results,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"\n{total_rows} rows, {total_bytes / 1024 / 1024:.2f} MB -> {out_dir}")
    print(f"manifest: {out_dir / 'manifest.json'}")
    if incomplete:
        print(f"\n!! INCOMPLETE: {', '.join(incomplete)} — do not treat this as "
              f"a backup until they succeed.", file=sys.stderr)
        return 1
    print("\nReminder: user.password is not in here (access=internal), and this "
          "directory holds real user data. backups/ is gitignored.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
