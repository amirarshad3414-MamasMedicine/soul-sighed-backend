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
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parity_lib import (
    compare_pair,
    coverage,
    harvest_context,
    live_endpoints,
    load_pairs,
    resolve_refs,
)

# Sentinel for a pair whose @created_* prerequisite never ran locally.
SKIPPED = object()


# The local dev DB (docker Postgres on 5433). The write pairs replay into it,
# and get_children etc. read what add_children just created, so the run must
# start clean — otherwise a second run hits "email already in use" on signup and
# threads no token. Same tables the test suite truncates.
TABLES = ["children", "insights", "journey", "purchases", "email",
          "onboarding_visit", "user_01", "users"]


async def replay(pairs: list[dict], fallback_token: str, live_externals: bool,
                 truncate: bool):
    # Keep the diff fast, offline and repeatable: without a reachable insight
    # URL, submit_onboarding fails fast and returns status "failed" — which
    # still shape-matches Xano's "ready" (same keys, and empty-vs-full teaser is
    # data, not shape). Set before app.config is first imported, below.
    if not live_externals:
        os.environ["EXTERNAL_INSIGHT_API_URL"] = ""

    from httpx import ASGITransport, AsyncClient
    from sqlalchemy import text

    from app.database import engine
    from app.main import app

    if truncate:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))

    ctx: dict = {}
    if fallback_token:
        ctx["token"] = fallback_token

    out = []
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://local") as c:
        for pair in pairs:
            req = pair["request"]
            body, miss_b = resolve_refs(req.get("body"), ctx)
            params, miss_q = resolve_refs(req.get("query"), ctx)
            missing = miss_b | miss_q
            if req.get("auth") and not ctx.get("token"):
                # No token to thread (a subset run with no signup pair). Skip
                # rather than false-fail a happy 200 against a local 401.
                missing.add("auth-token")
            if missing:
                out.append((pair, SKIPPED, sorted(missing)))
                continue
            headers = {}
            if req.get("auth"):
                headers["Authorization"] = f"Bearer {ctx['token']}"
            r = await c.request(req["method"], req["path"],
                                params=params or None, json=body, headers=headers)
            try:
                resp, is_json = r.json(), True
            except ValueError:
                resp, is_json = r.text, False
            harvest_context(pair["endpoint"], pair["case"],
                            resp if is_json else None, ctx)
            out.append((pair, r.status_code, is_json, resp))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--endpoint", help="diff only this endpoint")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="also print warnings and per-pair OK lines")
    p.add_argument("--token", default="",
                   help="fallback bearer token for auth pairs when the run has "
                        "no auth/signup pair to thread one from (e.g. a subset)")
    p.add_argument("--live-externals", action="store_true",
                   help="do not blank the insight URL; let submit_onboarding "
                        "call the real service (slow, generates a real reading)")
    p.add_argument("--no-truncate", action="store_true",
                   help="do not wipe the local dev DB first (threading a token "
                        "then needs a clean DB or --token)")
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

    results = asyncio.run(replay(pairs, args.token, args.live_externals,
                                 truncate=not args.no_truncate))

    report, failed, skipped = [], 0, 0
    for pair, status, *rest in results:
        label = f"{pair['endpoint']} [{pair['case']}]"
        if status is SKIPPED:
            skipped += 1
            (missing,) = rest
            print(f"skip  {label}  — prerequisite not created locally: "
                  f"{', '.join(missing)}")
            report.append({"file": pair["_file"], "endpoint": pair["endpoint"],
                           "case": pair["case"], "skipped": missing})
            continue
        is_json, body = rest
        problems, warnings = compare_pair(pair, status, is_json, body)
        report.append({"file": pair["_file"], "endpoint": pair["endpoint"],
                       "case": pair["case"], "problems": problems,
                       "warnings": warnings})
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
    clean = len(results) - failed - skipped
    print(f"\n{len(pairs)} pairs · {clean} clean · {failed} with shape "
          f"problems · {skipped} skipped (no local prerequisite)")
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
