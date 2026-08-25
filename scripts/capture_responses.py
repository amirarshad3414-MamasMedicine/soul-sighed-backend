#!/usr/bin/env python3
"""Capture real Xano responses — the corpus the shape-diff (8.2) runs against.

**This sends traffic to the live Xano app API.** Per the standing rule, that
needs Amir's approval, so the script refuses to run without --i-have-approval,
and every WRITE call additionally needs --allow-writes. Reads are replayed
freely; writes run only under a dedicated test account this script creates, and
`cleanup_test_data.py` removes what they leave behind.

    export XANO_PAT="$(cat ~/.config/xano/pat)"      # only for cleanup bookkeeping
    python3 scripts/capture_responses.py --list                 # no traffic
    python3 scripts/capture_responses.py --i-have-approval --reads-only
    python3 scripts/capture_responses.py --i-have-approval --allow-writes

Output: one pair per call under xano-export/responses/pairs/ (gitignored). Each
pair records the request, the classification, and Xano's status + body. A write
call also appends the rows it created to responses/runs/<run>.cleanup.json.

Non-table-shaped responses (1.4), one failing call per endpoint for the error
envelope, and table-shaped spot-checks are all represented. Stripe checkout is
NOT driven live here (it would hit Stripe and the real webhook); it is captured
separately in Stripe test mode — see the note on `create_checkout_session`.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from parity_lib import (
    RUNS_DIR,
    XANO_APP_BASE,
    live_endpoints,
    save_pair,
)

# A test-account marker so cleanup can find and delete only what we created.
TEST_TAG = "parity-test"


def _email(run: str, n: int) -> str:
    return f"{TEST_TAG}+{run}-{n}@soul-sighted.test"


# --- one call in the plan ----------------------------------------------------

class Call:
    def __init__(self, endpoint, case, method, path, *, rw, body=None,
                 query=None, auth=False, expect_status=None, note=None,
                 skip_live=False):
        self.endpoint = endpoint        # inventory endpoint name (coverage key)
        self.case = case                # "happy", "error:duplicate", ...
        self.method = method
        self.path = path                # e.g. "/add_children"
        self.rw = rw                    # "read" or "write"
        self.body = body
        self.query = query
        self.auth = auth                # needs a Bearer token
        self.expect_status = expect_status
        self.note = note
        self.skip_live = skip_live      # in the plan, not driven by this script


def build_plan(run: str) -> list[Call]:
    """The ~24 targeted calls of migration-plan 1.4, classified read/write.

    `run` scopes every test email so parallel/rerun captures never collide."""
    child_payload = {
        "name": "Parity Child",
        "relationship_focus": "child",
        "dob": "2020-05-01",
        "place_of_birth": "Lahore, Pakistan",
        "place_of_birth_id": "ChIJj8xkAyUEGTkRAmqmZma0feo",
        "pronoun": "she/her",
    }
    onboarding_payload = {
        "username": "Parity Parent",
        "childname": "Parity Child",
        "user_dob": "1990-01-01T00:00",
        "user_birth_place_id": "ChIJj8xkAyUEGTkRAmqmZma0feo",
        "child_dob": "2020-05-01T00:00",
        "child_birth_place_id": "ChIJj8xkAyUEGTkRAmqmZma0feo",
        "parentPronouns": "they/them",
        "childPronouns": "she/her",
    }
    return [
        # -- auth: non-table-shaped responses + error envelopes --------------
        Call("auth/signup", "happy", "POST", "/auth/signup", rw="write",
             body={"name": "Parity", "email": _email(run, 1),
                   "password": "Parity-pw-123"}),
        Call("auth/signup", "error:duplicate", "POST", "/auth/signup",
             rw="write", body={"name": "Parity", "email": _email(run, 1),
                               "password": "Parity-pw-123"},
             expect_status=400,
             note="second signup of email #1 → 'This account is already in use.'"),
        Call("auth/login", "happy", "POST", "/auth/login", rw="read",
             body={"email": _email(run, 1), "password": "Parity-pw-123"},
             note="read: verifies, issues a token; creates no row"),
        Call("auth/login", "error:bad-credentials", "POST", "/auth/login",
             rw="read", body={"email": _email(run, 1), "password": "wrong"},
             expect_status=401,
             note="pins parity-question #1: status of a no-error_type precondition"),
        Call("auth/me", "happy", "GET", "/auth/me", rw="read", auth=True),
        Call("register_passwordless", "happy", "POST", "/register_passwordless",
             rw="write", body={"name": "Parity PL", "email": _email(run, 2)}),
        Call("otp/store", "happy", "POST", "/otp/store", rw="write",
             body={"email": _email(run, 2), "otp": "123456", "expiresIn": 600},
             note="open endpoint (open-items) — captured under a test address only"),
        Call("verify_otp", "happy", "POST", "/verify_otp", rw="read",
             body={"email": _email(run, 2), "otp": "123456"}),
        Call("verify_otp", "error:wrong-otp", "POST", "/verify_otp", rw="read",
             body={"email": _email(run, 2), "otp": "000000"}, expect_status=400),
        Call("update_password", "happy", "POST", "/update_password", rw="write",
             body={"email": _email(run, 2), "newPassword": "Parity-pw-456"},
             note="account-takeover endpoint; test address only"),

        # -- children: table-shaped spot-checks + the conditional graft ------
        Call("add_children", "happy:with-place", "POST", "/add_children",
             rw="write", auth=True, body=child_payload,
             note="place_of_birth_id set → response should carry place_id"),
        Call("add_children", "happy:no-place", "POST", "/add_children",
             rw="write", auth=True,
             body={**child_payload, "place_of_birth": None,
                   "place_of_birth_id": None},
             note="no place_of_birth_id → place_id must be absent (the graft)"),
        Call("add_children", "error:duplicate", "POST", "/add_children",
             rw="write", auth=True, body=child_payload, expect_status=400,
             note="declares 'Record already exists'; body shape unknown "
                  "(env.js reads data?.message)"),
        Call("get_children", "happy", "GET", "/get_children", rw="read",
             auth=True),
        Call("get_child_by_id", "happy", "GET", "/get_child_by_id", rw="read",
             auth=True, query={"child_id": "@created_child"},
             note="child_id filled from add_children happy:with-place"),

        # -- onboarding ------------------------------------------------------
        Call("submit_onboarding", "happy", "POST", "/submit_onboarding",
             rw="write", auth=True,
             body={"child_id": "@created_child",
                   "journey_id": "fff90478-924f-4ec7-95a1-68b5549a0ec9",
                   "onboarding_payload": onboarding_payload,
                   "user_relation": "parent"},
             note="generates a reading; runs the insight retry loop live"),

        # -- places (reads; external Google calls, no DB write) --------------
        Call("places_autocomplete", "happy", "GET", "/places_autocomplete",
             rw="read", query={"q": "Lahore"}),
        Call("places_autocomplete", "zero-results", "GET",
             "/places_autocomplete", rw="read",
             query={"q": "zzzzzzzznowhere"},
             note="parity-question #4: {predictions:[]} vs error on ZERO_RESULTS"),
        Call("places_autocomplete", "error:too-short", "GET",
             "/places_autocomplete", rw="read", query={"q": "ab"},
             expect_status=400,
             note="q declares filters=trim|min:3. An input-filter rejection is "
                  "a different error path from a precondition, and its body "
                  "shape is in no XanoScript. The port answers 400 here."),
        Call("places_details", "happy", "GET", "/places_details", rw="read",
             query={"place_id": "ChIJj8xkAyUEGTkRAmqmZma0feo"}),

        # -- email queue -----------------------------------------------------
        Call("scheduled_email", "happy", "POST", "/scheduled_email", rw="write",
             body={"email": _email(run, 3), "subject": "Parity",
                   "body": "<p>parity</p>",
                   "scheduled_time": "2020-01-01T00:00:00Z"},
             note="scheduled in the past so get_pending_emails returns it"),
        Call("get_pending_emails", "happy", "GET", "/get_pending_emails",
             rw="read", query={"current_time": "2099-01-01T00:00:00Z"}),
        Call("deliver_email", "happy", "POST", "/deliver_email", rw="write",
             body={"email_id": "@created_email"},
             note="marks the scheduled_email row delivered"),

        # -- analytics -------------------------------------------------------
        Call("onboarding_visit_stats", "happy", "GET",
             "/onboarding_visit_stats", rw="read"),
        Call("track_onboarding_visit", "happy", "POST",
             "/track_onboarding_visit", rw="write",
             body={"session_id": f"{TEST_TAG}-{run}", "flow": "child",
                   "step": "relationship", "step_index": 1}),

        # -- misc ------------------------------------------------------------
        Call("Profile", "happy", "POST", "/Profile", rw="read",
             note="input {} / response null — a null-shape spot check"),

        # -- checkout: NOT driven live from here -----------------------------
        Call("create_checkout_session", "happy", "POST",
             "/create_checkout_session", rw="write", auth=True,
             body={"client_reference_id": "@created_child",
                   "success_url": "https://example.test/ok?flow=child",
                   "cancel_url": "https://example.test/cancel?payment_failed",
                   "line_items": [{"price": "price_TEST", "quantity": 1}],
                   "send_email": False},
             skip_live=True,
             note="hits Stripe live; run only with a Stripe TEST key and "
                  "capture the returned url shape. Left in the plan for the "
                  "coverage gate, not auto-sent."),
        Call("checkout", "happy", "POST", "/checkout", rw="write",
             skip_live=True,
             note="the live Stripe webhook. Capture by sending a Stripe TEST "
                  "event via `stripe trigger checkout.session.completed`, not "
                  "by POSTing here — a forged body would write a real Purchase."),
    ]


# --- HTTP --------------------------------------------------------------------

def http(method: str, url: str, body=None, token=None):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    text = raw.decode(errors="replace")
    try:
        return status, json.loads(text), True
    except json.JSONDecodeError:
        return status, text, False


def to_pair(call: Call, order: int, status: int, body, is_json: bool) -> dict:
    resp: dict = {"status": status}
    if is_json:
        resp["json"] = body
    else:
        resp["text"] = body
    return {
        "order": order,
        "endpoint": call.endpoint,
        "case": call.case,
        "rw": call.rw,
        "request": {"method": call.method, "path": call.path,
                    "query": call.query, "body": call.body, "auth": call.auth},
        "response": resp,
        "note": call.note,
    }


# --- run ---------------------------------------------------------------------

def run(args) -> int:
    plan = build_plan(args.run)
    if args.list:
        gate = set(live_endpoints())
        print(f"{'ENDPOINT':<26} {'CASE':<22} {'RW':<6} LIVE?")
        for c in plan:
            live = "skip" if c.skip_live else ("read" if c.rw == "read"
                                               else "WRITE")
            print(f"{c.endpoint:<26} {c.case:<22} {c.rw:<6} {live}")
        missing = gate - {c.endpoint for c in plan}
        if missing:
            print(f"\n!! coverage gap — no planned call for: "
                  f"{', '.join(sorted(missing))}")
        else:
            print(f"\nall {len(gate)} PORT endpoints have ≥1 planned call")
        return 0

    if not args.i_have_approval:
        print("Refusing to send live Xano traffic. This is gated on Amir's "
              "approval (standing rule). Re-run with --i-have-approval once "
              "you have it, or use --list to review the plan with no traffic.",
              file=sys.stderr)
        return 2

    token = None
    created_child = created_email = None
    cleanup: list[dict] = []
    order = 0
    for call in plan:
        if call.skip_live:
            print(f"-- skip (manual/Stripe): {call.endpoint} [{call.case}] "
                  f"— {call.note}")
            continue
        if call.rw == "write" and not args.allow_writes:
            print(f"-- skip write (no --allow-writes): {call.endpoint} "
                  f"[{call.case}]")
            continue
        if args.reads_only and call.rw == "write":
            continue

        body = json.loads(json.dumps(call.body)) if call.body else None
        query = dict(call.query) if call.query else None
        for holder in (body or {}), (query or {}):
            for k, v in list(holder.items()):
                if v == "@created_child":
                    holder[k] = created_child
                elif v == "@created_email":
                    holder[k] = created_email
        url = XANO_APP_BASE + call.path
        if query:
            url += "?" + urllib.parse.urlencode(query)

        status, resp_body, is_json = http(
            call.method, url, body, token if call.auth else None)
        order += 1
        pair = to_pair(call, order, status, resp_body, is_json)
        path = save_pair(pair)
        flag = "" if (call.expect_status in (None, status)) else \
            f"  [expected {call.expect_status}]"
        print(f"[{order:02d}] {call.method:<4} {call.path:<26} "
              f"{call.case:<22} → {status}{flag}  {path.name}")

        # Thread created ids forward; note rows for cleanup.
        if is_json and isinstance(resp_body, dict):
            if call.endpoint in ("auth/signup", "auth/login") and \
                    resp_body.get("authToken"):
                token = resp_body["authToken"]
            elif "authToken" in resp_body:
                token = resp_body["authToken"]
            if call.endpoint == "add_children" and call.case.startswith("happy"):
                created_child = resp_body.get("child_id") or resp_body.get("id")
                if created_child:
                    cleanup.append({"table": "children", "id": created_child})
            if call.endpoint == "scheduled_email":
                created_email = resp_body.get("id")
                if created_email:
                    cleanup.append({"table": "Email", "id": created_email})
        time.sleep(0.3)  # be gentle with the live API

    if cleanup:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        out = RUNS_DIR / f"{args.run}.cleanup.json"
        out.write_text(json.dumps(
            {"run": args.run, "test_tag": TEST_TAG, "rows": cleanup}, indent=2))
        print(f"\n{len(cleanup)} test rows recorded for cleanup → {out}")
        print("Run: python3 scripts/cleanup_test_data.py "
              f"--run {args.run} --i-have-approval")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--list", action="store_true",
                   help="print the plan and coverage; send no traffic")
    p.add_argument("--i-have-approval", action="store_true",
                   help="required to send any live Xano traffic")
    p.add_argument("--allow-writes", action="store_true",
                   help="also run the write calls (test accounts only)")
    p.add_argument("--reads-only", action="store_true",
                   help="run reads even if --allow-writes is set")
    p.add_argument("--run", default="r1",
                   help="short label scoping this run's test emails/session")
    return run(p.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
