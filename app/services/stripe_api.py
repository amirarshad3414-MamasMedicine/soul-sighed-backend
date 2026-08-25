"""Stripe calls, extracted from the Xano stacks.

Xano authenticates with `Authorization: Basic base64(secret_key)`, which is the
older form of Stripe's scheme. Reproduced so the request Stripe receives is
byte-identical to today's.
"""
import base64
from typing import Any

import httpx

from app.config import settings

CHECKOUT_SESSIONS_URL = "https://api.stripe.com/v1/checkout/sessions"
TIMEOUT = 30.0


def _auth_header() -> dict[str, str]:
    encoded = base64.b64encode(settings.stripe_secret_key.encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def encode_form(value: Any, prefix: str = "") -> dict[str, str]:
    """Flatten nested structures into Stripe's bracket form encoding.

    Stripe's API is form-encoded and expects nested data as
    `line_items[0][price]=…`, `metadata[send_email]=false`. Xano's `api.request`
    does this flattening for you; httpx does NOT — handed a list or dict it
    writes Python's repr, so Stripe received

        line_items={'price': 'price_123', 'quantity': 1}

    and answered `{"error": {"message": "Invalid array"}}`. Every purchase would
    have failed at cutover. Found by clicking Purchase in the dashboard against
    the local backend, 2026-08-25.

    Booleans are lowercased ("true"/"false") — Python's str(False) is "False",
    which Stripe does not accept. None is dropped, matching Xano's behaviour of
    omitting empty optionals rather than sending the string "None".
    """
    out: dict[str, str] = {}
    if value is None:
        return out
    if isinstance(value, dict):
        for key, item in value.items():
            out |= encode_form(item, f"{prefix}[{key}]" if prefix else str(key))
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            out |= encode_form(item, f"{prefix}[{i}]")
    elif isinstance(value, bool):
        out[prefix] = "true" if value else "false"
    else:
        out[prefix] = str(value)
    return out


async def create_checkout_session(params: dict[str, Any]) -> dict[str, Any]:
    """POST a checkout session and return Stripe's body verbatim."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(CHECKOUT_SESSIONS_URL,
                                     data=encode_form(params),
                                     headers=_auth_header())
        return response.json()
