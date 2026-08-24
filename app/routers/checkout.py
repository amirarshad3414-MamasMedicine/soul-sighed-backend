"""Stripe endpoints, ported from the Xano `scripters` API group."""
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.errors import XanoError
from app.database import get_session
from app.models import Child, Insight, Purchase, User
from app.schemas.checkout import JOURNEY_ID, CreateCheckoutSessionIn, WebhookAck
from app.services import klaviyo, notifications, stripe_api

router = APIRouter(tags=["checkout"])


@router.post("/create_checkout_session")
async def create_checkout_session(body: CreateCheckoutSessionIn) -> dict[str, Any]:
    """Open a Stripe checkout session and hand its object back untouched.

    Ported from .../61_create_checkout_session.xs. The response is Stripe's own
    body, so it is returned as a dict rather than reshaped.
    """
    params: dict[str, Any] = {
        "success_url": body.success_url,
        "cancel_url": body.cancel_url,
        "payment_method_types[0]": "card",
        "client_reference_id": body.client_reference_id,
        "line_items": body.line_items,
        "mode": "payment",
        "allow_promotion_codes": "true",
        "metadata": {"send_email": bool(body.send_email)},
    }
    # Xano uses set_ifnotempty for this one field only: an empty customer_email
    # is dropped rather than sent as blank.
    if body.customer_email:
        params["customer_email"] = body.customer_email

    session = await stripe_api.create_checkout_session(params)

    if session.get("error"):
        raise XanoError("standard", session["error"].get("message"))
    return session


@router.post("/checkout", response_model=WebhookAck)
async def checkout(
    request: Request,
    db: AsyncSession = Depends(get_session),
) -> WebhookAck:
    """Stripe's webhook: record the purchase, then fire the follow-up emails.

    Ported from .../62_checkout.xs.

    SECURITY, reproduced under the auth-parity rule: there is no signature
    check. Xano takes the raw body as `json __self` and trusts it, so anyone who
    knows this URL can forge a completed payment — granting paid content with a
    client_reference_id, or triggering mail to an address of their choosing
    without one. The fix is Stripe's constructEvent with the webhook secret;
    it is a deliberate behaviour change and belongs in its own commit.
    """
    event = await request.json()
    obj = (event or {}).get("data", {}).get("object", {}) or {}
    send_email = bool((obj.get("metadata") or {}).get("send_email"))
    child_id = obj.get("client_reference_id")

    child: Child | None = None
    user: User | None = None

    if child_id:
        child = (await db.execute(
            select(Child).where(Child.id == child_id))).scalar_one_or_none()
        user = (await db.execute(
            select(User).where(User.id == child.user_id))).scalar_one_or_none() if child else None

        existing = (await db.execute(
            select(Purchase).where(Purchase.child_id == child_id))).scalars().first()
        if existing is None:
            db.add(Purchase(user_id=user.id if user else None,
                            child_id=child.id if child else None,
                            journey_id=JOURNEY_ID, purchase_source="stripe",
                            purchase_reference=obj.get("id")))
        email = user.email if user else None
    else:
        # Paid before having an account. user_id and child_id stay null; signing
        # up later adopts the row by email (see services/accounts.py).
        email = (obj.get("customer_details") or {}).get("email")
        db.add(Purchase(email=email, purchase_reference=obj.get("id"),
                        purchase_source="stripe", journey_id=JOURNEY_ID))

    await db.commit()

    await klaviyo.subscribe(email)
    await notifications.send_purchase_email(
        obj.get("customer_details"), obj.get("id"),
        child.name if child else None)

    if send_email and child_id:
        insight = (await db.execute(
            select(Insight).where(Insight.child_id == child_id))).scalars().first()
        await notifications.send_insight(
            child.name if child else None,
            user.name if user else None,
            email, insight)

    return WebhookAck(success=True)
