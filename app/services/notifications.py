"""Outbound notification calls made by the Xano `checkout` stack.

Both targets are hardcoded in XanoScript, and both are called without checking
the result — the response is logged and discarded. Reproduced, including the
swallowing, so a failing notification cannot break a payment being recorded.
"""
from typing import Any

import httpx

from app.config import settings

PURCHASE_EMAIL_TIMEOUT = 30.0
SEND_INSIGHT_TIMEOUT = 300.0   # Xano sets timeout = 300 on this one


async def send_purchase_email(customer: Any, purchase_id: str | None,
                              child_name: str | None) -> None:
    payload = {"data": {
        "customer": customer,
        "product_purchase": "Your Parenting Dynamic",
        "purchase_id": purchase_id,
        "child_name": child_name,
    }}
    try:
        async with httpx.AsyncClient(timeout=PURCHASE_EMAIL_TIMEOUT) as client:
            await client.post(settings.purchase_email_url, json=payload)
    except Exception:
        return


async def send_insight(child_name: str | None, parent_name: str | None,
                       email: str | None, insight: Any) -> None:
    payload = {"childName": child_name, "parentName": parent_name,
               "email": email, "insight": insight}
    try:
        async with httpx.AsyncClient(timeout=SEND_INSIGHT_TIMEOUT) as client:
            await client.post(settings.send_insight_url, json=payload,
                              headers={"Content-Type": "application/json"})
    except Exception:
        return
