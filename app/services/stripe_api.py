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


async def create_checkout_session(params: dict[str, Any]) -> dict[str, Any]:
    """POST a checkout session and return Stripe's body verbatim."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.post(CHECKOUT_SESSIONS_URL, data=params,
                                     headers=_auth_header())
        return response.json()
