"""Klaviyo list subscription, extracted from the Xano `checkout` stack.

The API key is hardcoded in the XanoScript. It lives in configuration here
instead — the same value, but not written into source.
"""
import httpx

from app.config import settings

SUBSCRIPTION_URL = "https://a.klaviyo.com/api/profile-subscription-bulk-create-jobs/"
REVISION = "2024-02-15"
TIMEOUT = 15.0


async def subscribe(email: str | None) -> None:
    """Add an address to the marketing list. Failures are swallowed, as in Xano,
    where the response is logged and never checked."""
    if not email:
        return
    payload = {"data": {
        "type": "profile-subscription-bulk-create-job",
        "attributes": {"profiles": {"data": [
            {"type": "profile", "attributes": {"email": email}}]}},
        "relationships": {"list": {"data": {
            "type": "list", "id": settings.klaviyo_list_id}}},
    }}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            await client.post(SUBSCRIPTION_URL, json=payload, headers={
                "Authorization": f"Klaviyo-API-Key {settings.klaviyo_api_key}",
                "Content-Type": "application/json",
                "revision": REVISION,
            })
    except Exception:
        return
