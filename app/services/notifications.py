"""Outbound notification calls made by the Xano `checkout` stack.

Both targets are hardcoded in XanoScript, and both are called without checking
the result — the response is logged and discarded. Reproduced, including the
swallowing, so a failing notification cannot break a payment being recorded.
"""
import logging
from typing import Any

import httpx

from app.config import settings

PURCHASE_EMAIL_TIMEOUT = 30.0
SEND_INSIGHT_TIMEOUT = 300.0   # Xano sets timeout = 300 on this one

# Xano discards both responses and so does the port, which means a silently
# failing notification looks exactly like a working one — there is no way to
# tell from the outside whether the call was even attempted. Under DEBUG the
# outcome is logged so local testing can answer "was the API actually hit?".
_log = logging.getLogger("uvicorn.error")


def _trace(name: str, url: str, status: object) -> None:
    if not settings.debug:
        return
    if not url:
        _log.warning("NOTIFY %s NOT SENT — url is blank in .env", name)
    else:
        _log.warning("NOTIFY %s -> %s : %s", name, url, status)


async def send_purchase_email(customer: Any, purchase_id: str | None,
                              child_name: str | None) -> None:
    payload = {"data": {
        "customer": customer,
        "product_purchase": "Your Parenting Dynamic",
        "purchase_id": purchase_id,
        "child_name": child_name,
    }}
    if not settings.purchase_email_url:
        _trace("purchase_email", "", None)
        return
    try:
        async with httpx.AsyncClient(timeout=PURCHASE_EMAIL_TIMEOUT) as client:
            r = await client.post(settings.purchase_email_url, json=payload)
        _trace("purchase_email", settings.purchase_email_url, f"HTTP {r.status_code}")
    except Exception as exc:
        _trace("purchase_email", settings.purchase_email_url, f"FAILED {exc!r}")
        return


def _serialise_insight(insight: Any) -> Any:
    """Turn the Insight row into the JSON Xano sends.

    Xano passes the whole `Insights` record (`insight: $Insights1`) and the
    receiving Vercel route reads `insight.deep_text` / `insight.summary_text`.
    Handing httpx the SQLModel instance instead raised
    `TypeError: Object of type Insight is not JSON serializable` *before* the
    request was made — and because this function discards its result to match
    Xano, the failure was invisible: the insight email simply never sent.
    Found with notification tracing on, 2026-08-25.

    InsightOut carries the same column set and the Appendix A formats
    (created_at as epoch ms), so the body matches Xano's on the wire.
    """
    if insight is None or isinstance(insight, (dict, list, str)):
        return insight
    from app.schemas.insight import InsightOut
    return InsightOut.model_validate(insight, from_attributes=True).model_dump(
        mode="json")


async def send_insight(child_name: str | None, parent_name: str | None,
                       email: str | None, insight: Any) -> None:
    payload = {"childName": child_name, "parentName": parent_name,
               "email": email, "insight": _serialise_insight(insight)}
    if not settings.send_insight_url:
        _trace("send_insight", "", None)
        return
    try:
        async with httpx.AsyncClient(timeout=SEND_INSIGHT_TIMEOUT) as client:
            r = await client.post(settings.send_insight_url, json=payload,
                                  headers={"Content-Type": "application/json"})
        _trace("send_insight", settings.send_insight_url,
               f"HTTP {r.status_code} {r.text[:120]}")
    except Exception as exc:
        _trace("send_insight", settings.send_insight_url, f"FAILED {exc!r}")
        return
