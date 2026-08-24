#!/usr/bin/env python3
"""Dump every XanoScript object in a Xano workspace to a local tree.

Token is read from $XANO_PAT or --token-file. Never pass it on the command line.

  export XANO_PAT="$(cat ~/.config/xano/pat)"
  python3 xano_dump.py --out ./xano-inventory
"""
import argparse, json, os, pathlib, sys, time, urllib.parse, urllib.request

BASE = "https://xnrw-fohw-scw8.a2.xano.io/api:meta"
WS = 1

# Every object type that carries XanoScript, per the Metadata API spec.
COLLECTIONS = [
    "function", "task", "trigger", "table/trigger", "middleware", "addon",
    "tool", "agent", "agent/trigger", "mcp_server", "mcp_server/trigger",
    "realtime/channel", "realtime/channel/trigger", "workflow_test",
]

def get(token, path, **params):
    params.setdefault("per_page", 100)
    out, page = [], 1
    while True:
        params["page"] = page
        url = f"{BASE}{path}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = json.load(r)
        except urllib.error.HTTPError as e:
            print(f"  !! {e.code} {path}: {e.read()[:200].decode(errors='replace')}", file=sys.stderr)
            return out
        items = body.get("items", body) if isinstance(body, dict) else body
        if not isinstance(items, list):
            return items          # single object, not a listing
        out += items
        if len(items) < params["per_page"]:
            return out
        page += 1
        time.sleep(0.2)           # the meta API rate-limits (429)

def slug(o, i):
    return str(o.get("name") or o.get("path") or o.get("verb") or f"item{i}").strip("/").replace("/", "_") or f"item{i}"

def write(root, rel, obj, i):
    d = root / rel
    d.mkdir(parents=True, exist_ok=True)
    stem = f"{obj.get('id', i)}_{slug(obj, i)}"
    (d / f"{stem}.json").write_text(json.dumps(obj, indent=2))
    xs = obj.get("xanoscript")
    if isinstance(xs, dict):          # the API wraps it as {"value": "..."}
        xs = xs.get("value")
    if isinstance(xs, str) and xs.strip():
        (d / f"{stem}.xs").write_text(xs)
        return True
    return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="xano-inventory")
    ap.add_argument("--token-file")
    a = ap.parse_args()
    token = (pathlib.Path(a.token_file).read_text().strip() if a.token_file
             else os.environ.get("XANO_PAT", "").strip())
    if not token:
        sys.exit("No token. Set XANO_PAT or pass --token-file.")

    root = pathlib.Path(a.out)
    manifest = {}

    # --- API groups, then every API inside each ---
    groups = get(token, f"/workspace/{WS}/apigroup", include_xanoscript="true")
    print(f"apigroup: {len(groups)}")
    for g in groups:
        gid, gname = g["id"], slug(g, g["id"])
        apis = get(token, f"/workspace/{WS}/apigroup/{gid}/api",
                   include_xanoscript="true", include_draft="true")
        print(f"  group {gid} {gname}: {len(apis)} endpoints")
        for i, ep in enumerate(apis):
            write(root, f"apigroup/{gid}_{gname}", ep, i)
        manifest[f"apigroup/{gid}_{gname}"] = [
            {"id": e.get("id"), "verb": e.get("verb"), "path": e.get("name") or e.get("path")}
            for e in apis]

    # --- tables: definition, schema and indexes ---
    tables = get(token, f"/workspace/{WS}/table", include_xanoscript="true")
    print(f"table: {len(tables)}")
    for i, t in enumerate(tables):
        tid = t["id"]
        t["_schema"] = get(token, f"/workspace/{WS}/table/{tid}/schema")
        t["_index"] = get(token, f"/workspace/{WS}/table/{tid}/index")
        write(root, "table", t, i)
    manifest["table"] = [{"id": t.get("id"), "name": t.get("name")} for t in tables]

    # --- everything else that carries XanoScript ---
    for c in COLLECTIONS:
        items = get(token, f"/workspace/{WS}/{c}", include_xanoscript="true")
        if not isinstance(items, list):
            continue
        print(f"{c}: {len(items)}")
        for i, o in enumerate(items):
            write(root, c, o, i)
        manifest[c] = [{"id": o.get("id"), "name": o.get("name")} for o in items]

    (root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nWrote {root.resolve()}/MANIFEST.json")

if __name__ == "__main__":
    main()
