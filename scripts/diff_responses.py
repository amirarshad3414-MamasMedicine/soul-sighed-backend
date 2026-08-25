#!/usr/bin/env python3
"""Replay captured Xano pairs against the local FastAPI port and diff the SHAPE.

Sends **no** traffic to Xano — it reads the pairs `capture_responses.py` wrote
and calls the local app in-process (ASGI), so no server needs to be running.

What it proves and what it does not (migration plan 8.2): Xano holds real data,
FastAPI holds seed data, so values differ by construction and only shape is
comparable — status code, key sets, JSON type per key, null-vs-empty per key,
error bodies, plus the Appendix A formats from xano-export/formats.md. Value
parity waits on data migration.

    ./.venv/bin/python scripts/diff_responses.py
    ./.venv/bin/python scripts/diff_responses.py --endpoint add_children -v

Exit codes: 0 clean · 1 shape problems · 2 coverage gate failed (8.3: every
PORT endpoint in the inventory needs ≥1 pair, or a green run means "diff ran on
12 of 21").
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parity_lib import compare_pair, coverage, live_endpoints, load_pairs


async def replay(pairs: list[dict], token_for) -> list[tuple[dict, int, bool, object]]:
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    out = []
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://local") as c:
        for pair in pairs:
            req = pair["request"]
            headers = {}
            if req.get("auth"):
                headers["Authorization"] = f"Bearer {token_for(pair)}"
            r = await c.request(req["method"], req["path"],
                                params=req.get("query") or None,
                                json=req.get("body"), headers=headers)
            try:
                body, is_json = r.json(), True
            except ValueError:
                body, is_json = r.text, False
            out.append((pair, r.status_code, is_json, body))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--endpoint", help="diff only this endpoint")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="also print warnings and per-pair OK lines")
    p.add_argument("--user-id", type=int, default=None,
                   help="mint a local token for this user id, for the five "
                        "auth=user pairs (the row must exist in the local DB)")
    p.add_argument("--token", default="",
                   help="use this bearer token instead of minting one")
    p.add_argument("--no-coverage-gate", action="store_true",
                   help="report coverage but do not fail on it")
    p.add_argument("--json", dest="as_json", help="write the full report here")
    args = p.parse_args()

    pairs = load_pairs(args.endpoint)
    if not pairs:
        where = f" for {args.endpoint}" if args.endpoint else ""
        print(f"No captured pairs{where}. Run capture_responses.py first "
              f"(it needs approval — see the standing rule).", file=sys.stderr)
        return 2

    token = args.token
    needs_auth = [p for p in pairs if p["request"].get("auth")]
    if needs_auth and not token:
        if args.user_id is None:
            print(f"{len(needs_auth)} pairs need auth. Pass --user-id (a user "
                  f"in the local DB, whose token is minted here) or --token.",
                  file=sys.stderr)
            return 2
        from app.core.security import create_access_token
        token = create_access_token(args.user_id)

    results = asyncio.run(replay(pairs, lambda _: token))

    report, failed = [], 0
    for pair, status, is_json, body in results:
        problems, warnings = compare_pair(pair, status, is_json, body)
        report.append({"file": pair["_file"], "endpoint": pair["endpoint"],
                       "case": pair["case"], "problems": problems,
                       "warnings": warnings})
        label = f"{pair['endpoint']} [{pair['case']}]"
        if problems:
            failed += 1
            print(f"FAIL  {label}")
            for msg in problems:
                print(f"        {msg}")
            for msg in warnings:
                print(f"        (warn) {msg}")
        elif args.verbose:
            print(f"ok    {label}")
            for msg in warnings:
                print(f"        (warn) {msg}")
        elif warnings:
            print(f"warn  {label}")
            for msg in warnings:
                print(f"        {msg}")

    endpoints = live_endpoints()
    covered, missing = coverage(pairs, endpoints)
    print(f"\n{len(pairs)} pairs · {len(results) - failed} clean · {failed} "
          f"with shape problems")
    print(f"coverage: {len(covered)}/{len(endpoints)} PORT endpoints have "
          f"≥1 pair")
    if missing:
        print(f"  no pair for: {', '.join(missing)}")

    if args.as_json:
        Path(args.as_json).write_text(json.dumps(
            {"pairs": report, "covered": covered, "missing": missing}, indent=2))

    if failed:
        return 1
    if missing and not args.endpoint and not args.no_coverage_gate:
        print("\nCOVERAGE GATE FAILED (plan 8.3) — 'diff clean' would mean "
              "'diff ran on some of them'.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
