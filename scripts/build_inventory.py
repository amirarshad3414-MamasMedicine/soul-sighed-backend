#!/usr/bin/env python3
"""Parse the XanoScript dump into xano-export/inventory.csv — one row per endpoint.

Columns are what Phase 2 triage needs to decide port-as-is / fix / drop.
Everything here is derived from the .xs source; nothing is guessed.
"""
import csv, pathlib, re, sys

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "xano-export")
LIVE_GROUP = "4_scripters"          # the only group with traffic
TEMPLATE_GROUPS = {"1_Authentication", "2_Members & Accounts", "3_Event Logs"}

# endpoints the frontend actually calls (grepped from the Next.js repo)
FRONTEND_CALLS = {
    "add_children", "get_children", "get_child_by_id", "submit_onboarding",
    "create_checkout_session", "track_onboarding_visit", "onboarding_visit_stats",
    "auth/login", "auth/signup", "auth/me", "register_passwordless",
    "update_password", "otp/store", "verify_otp", "places_autocomplete",
    "get_pending_emails", "deliver_email",
}

def parse(path: pathlib.Path) -> dict:
    src = path.read_text()
    head = src.split("stack {", 1)[0]
    def first(pat, s=src, d=""):
        m = re.search(pat, s, re.M)
        return m.group(1).strip() if m else d
    tables = sorted({m.group(2) for m in
                     re.finditer(r'\bdb\.(add|edit|get|query|patch|delete)\s+([A-Za-z_][\w]*)', src)})
    writes = sorted({m.group(2) for m in
                     re.finditer(r'\bdb\.(add|edit|patch|delete)\s+([A-Za-z_][\w]*)', src)})
    ext = sorted({re.sub(r'\?.*$', '', m.group(1)) for m in
                  re.finditer(r'url\s*=\s*"([^"]+)"', src)})
    envs = sorted({m.group(1) for m in re.finditer(r'\$env\.([A-Z0-9_]+)', src)})
    inputs = re.findall(r'^\s{4}(\w+\??)\s+(\w+\??)', head, re.M)
    return {
        "verb": first(r'query\s+\S+\s+verb=(\w+)'),
        "auth": first(r'^\s*auth\s*=\s*"([^"]+)"') or "none",
        "lines": src.count("\n") + 1,
        "inputs": " ".join(f"{t}:{n}" for t, n in inputs),
        "tables_read_or_written": ",".join(tables),
        "tables_written": ",".join(writes),
        "external_calls": " | ".join(ext),
        "env_vars": ",".join(envs),
        "has_retry_loop": "yes" if re.search(r'\bfor\s*\(', src) else "",
        "errors": " | ".join(sorted({m.group(1) for m in re.finditer(r'error\s*=\s*"([^"]+)"', src)})),
        "description": first(r'^//\s*(.+)$'),
    }

rows = []
for group_dir in sorted((ROOT / "apigroup").iterdir()):
    if not group_dir.is_dir():
        continue
    g = group_dir.name
    for xs in sorted(group_dir.glob("*.xs")):
        eid, _, name = xs.stem.partition("_")
        meta = xs.with_suffix(".json")
        if meta.exists():                     # real path, e.g. "auth/login"
            import json as _j
            name = _j.load(open(meta)).get("name") or name
        d = parse(xs)
        if g in TEMPLATE_GROUPS:
            triage, why = "DROP", "Xano starter template; zero traffic"
        elif g == "5_stripe_checkout":
            triage, why = "DROP?", "Stripe template; writes `session` (0 rows). CONFIRM Stripe is not pointed here"
        elif name in FRONTEND_CALLS:
            triage, why = "PORT", "called by the frontend"
        else:
            triage, why = "DECIDE", "in the live group but the frontend never calls it — find the caller"
        rows.append({"group": g, "id": eid, "endpoint": name, **d,
                     "triage": triage, "triage_reason": why})

out = ROOT / "inventory.csv"
cols = ["group", "id", "endpoint", "verb", "auth", "lines", "triage", "triage_reason",
        "tables_written", "tables_read_or_written", "external_calls", "env_vars",
        "has_retry_loop", "errors", "inputs", "description"]
with open(out, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

print(f"wrote {out} — {len(rows)} endpoints")
from collections import Counter
for k, v in Counter(r["triage"] for r in rows).most_common():
    print(f"  {k:8} {v}")
