#!/usr/bin/env python3
"""Grant a purchase on the LOCAL backend without paying Stripe.

Sends the same `checkout.session.completed` body Stripe posts to the webhook,
so the Purchase row is created exactly the way a real payment creates it. Use
this to test everything downstream of checkout without a card.

    # by child (what the dashboard/journey purchase does):
    python3 scripts/simulate_purchase.py --child-id <uuid>

    # by email (the "paid before signing up" branch):
    python3 scripts/simulate_purchase.py --email someone@example.com

    # list children to pick from:
    python3 scripts/simulate_purchase.py --list

Refuses any target that is not localhost — this must never be pointed at the
live Xano webhook, which would write a real Purchase row on a real account.

Note the notification side effects are real unless PURCHASE_EMAIL_URL and
SEND_INSIGHT_URL are blank in .env (they are, for local testing).
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid


def post(url: str, body: dict) -> tuple[int, str]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=310) as r:
            return r.status, r.read().decode()[:400]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", default="http://127.0.0.1:8000",
                   help="local backend (default %(default)s)")
    p.add_argument("--child-id", help="grant the purchase to this child")
    p.add_argument("--email", help="no-account branch: record against this email")
    p.add_argument("--send-email", action="store_true",
                   help="set metadata.send_email so the insight email fires")
    p.add_argument("--list", action="store_true", help="list local children")
    args = p.parse_args()

    if "localhost" not in args.base and "127.0.0.1" not in args.base:
        sys.exit(f"Refusing a non-local target: {args.base}. This simulates a "
                 f"Stripe webhook and must never hit live Xano.")

    if args.list:
        import subprocess
        out = subprocess.run(
            ["docker", "compose", "exec", "-T", "db", "psql", "-U", "app",
             "-d", "app_db", "-c",
             "SELECT c.id, c.name, u.email FROM children c "
             "JOIN users u ON u.id = c.user_id ORDER BY c.created_at DESC LIMIT 20;"],
            cwd="/Users/macuser/Documents/soul-sighted-backend",
            capture_output=True, text=True)
        print(out.stdout or out.stderr)
        return 0

    if not args.child_id and not args.email:
        p.error("pass --child-id or --email (or --list to see children)")

    # The shape Stripe posts, trimmed to the fields the webhook reads.
    session_id = f"cs_test_sim_{uuid.uuid4().hex[:20]}"
    event = {
        "id": f"evt_sim_{uuid.uuid4().hex[:16]}",
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": session_id,
            "client_reference_id": args.child_id,
            "customer_details": {"email": args.email or "sim@example.test",
                                 "name": "Simulated Buyer"},
            "metadata": {"send_email": bool(args.send_email)},
            "amount_total": 2100,
            "currency": "aud",
            "payment_status": "paid",
        }},
    }

    status, body = post(f"{args.base.rstrip('/')}/checkout", event)
    print(f"POST /checkout -> {status}")
    print(body)
    if status == 200:
        target = f"child {args.child_id}" if args.child_id else f"email {args.email}"
        print(f"\nPurchase recorded for {target} (session {session_id}).")
        print("Reload the dashboard — the journey should now read as purchased.")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
