"""create_checkout_session and checkout — Xano `scripters` 61 and 62.

`checkout` is the live Stripe webhook: it is what actually writes the Purchases
table, and it is why the `session` table in the unused stripe_checkout template
group has zero rows.

Stripe, Klaviyo and the two notification URLs are all replaced here. Nothing in
this file reaches the network.
"""
import pytest
from sqlmodel import select

from app.models import Child, Insight, Purchase, User
from app.schemas.checkout import JOURNEY_ID
from app.services import klaviyo, notifications, stripe_api
from tests.conftest import auth_headers

STRIPE_SESSION = {"id": "cs_test_abc", "url": "https://checkout.stripe.com/c/pay/cs_test_abc",
                  "object": "checkout.session"}


@pytest.fixture
def stripe(monkeypatch):
    state = {"response": STRIPE_SESSION, "params": None}

    async def fake(params):
        state["params"] = params
        return state["response"]

    monkeypatch.setattr(stripe_api, "create_checkout_session", fake)
    return state


@pytest.fixture
def outbound(monkeypatch):
    """Records every outbound side effect instead of performing it."""
    seen = {"klaviyo": [], "purchase_email": [], "insight": []}

    async def fake_subscribe(email):
        seen["klaviyo"].append(email)

    async def fake_purchase_email(customer, purchase_id, child_name):
        seen["purchase_email"].append((purchase_id, child_name))

    async def fake_send_insight(child_name, parent_name, email, insight):
        seen["insight"].append((child_name, parent_name, email, insight))

    monkeypatch.setattr(klaviyo, "subscribe", fake_subscribe)
    monkeypatch.setattr(notifications, "send_purchase_email", fake_purchase_email)
    monkeypatch.setattr(notifications, "send_insight", fake_send_insight)
    return seen


def stripe_event(**obj):
    return {"type": "checkout.session.completed",
            "data": {"object": {"id": "cs_live_1", "metadata": {}, **obj}}}


# --- the Stripe form encoding ------------------------------------------------
# These test the wire encoding directly. The endpoint tests below replace
# stripe_api.create_checkout_session wholesale, so they never see what actually
# goes over the wire — which is how the bug these pin reached the browser.

def test_line_items_use_stripes_bracket_notation():
    """Stripe is form-encoded and wants line_items[0][price], not a repr.

    Handed a list of dicts, httpx writes Python's repr — Stripe replied
    {"error": {"message": "Invalid array"}} and every purchase failed. Found by
    clicking Purchase in the dashboard against the local backend, 2026-08-25.
    """
    encoded = stripe_api.encode_form(
        {"line_items": [{"price": "price_123", "quantity": 1}]})
    assert encoded == {"line_items[0][price]": "price_123",
                       "line_items[0][quantity]": "1"}
    assert not any("{" in k or "{" in v for k, v in encoded.items())


def test_booleans_are_lowercased_for_stripe():
    """str(False) is "False"; Stripe wants "false"."""
    assert stripe_api.encode_form({"metadata": {"send_email": False}}) == {
        "metadata[send_email]": "false"}
    assert stripe_api.encode_form({"metadata": {"send_email": True}}) == {
        "metadata[send_email]": "true"}


def test_none_is_dropped_not_sent_as_the_string_none():
    assert stripe_api.encode_form({"client_reference_id": None}) == {}


def test_multiple_line_items_are_indexed_separately():
    encoded = stripe_api.encode_form({"line_items": [
        {"price": "a", "quantity": 1}, {"price": "b", "quantity": 2}]})
    assert encoded["line_items[0][price]"] == "a"
    assert encoded["line_items[1][price]"] == "b"
    assert encoded["line_items[1][quantity]"] == "2"


def test_flat_values_pass_through_unchanged():
    encoded = stripe_api.encode_form({
        "success_url": "https://x/ok", "payment_method_types[0]": "card"})
    assert encoded == {"success_url": "https://x/ok",
                       "payment_method_types[0]": "card"}


# --- create_checkout_session -------------------------------------------------

async def test_returns_stripes_object_untouched(client, stripe):
    r = await client.post("/create_checkout_session", json={
        "success_url": "https://x/ok", "cancel_url": "https://x/no",
        "line_items": [{"price": "price_1", "quantity": 1}]})
    assert r.status_code == 200
    assert r.json() == STRIPE_SESSION


async def test_sends_the_fixed_parameters_xano_sends(client, stripe):
    await client.post("/create_checkout_session", json={"success_url": "https://x/ok"})
    params = stripe["params"]
    assert params["payment_method_types[0]"] == "card"
    assert params["mode"] == "payment"
    assert params["allow_promotion_codes"] == "true"
    assert params["metadata"] == {"send_email": False}


async def test_an_empty_customer_email_is_dropped_not_sent_blank(client, stripe):
    """Xano uses set_ifnotempty for this field only."""
    await client.post("/create_checkout_session", json={"customer_email": ""})
    assert "customer_email" not in stripe["params"]

    await client.post("/create_checkout_session", json={"customer_email": "her@example.test"})
    assert stripe["params"]["customer_email"] == "her@example.test"


async def test_a_stripe_error_is_surfaced(client, stripe):
    stripe["response"] = {"error": {"message": "No such price: 'price_bad'"}}
    r = await client.post("/create_checkout_session", json={})
    assert r.status_code == 500
    assert r.json()["message"] == "No such price: 'price_bad'"


# --- checkout (the webhook) --------------------------------------------------

async def test_records_a_purchase_against_a_known_child(client, session, user, outbound):
    child = (await session.execute(
        select(Child).where(Child.user_id == user.id))).scalars().first()

    r = await client.post("/checkout",
                          json=stripe_event(client_reference_id=str(child.id)))
    assert r.status_code == 200
    assert r.json() == {"success": True}

    purchase = (await session.execute(
        select(Purchase).where(Purchase.purchase_reference == "cs_live_1"))).scalar_one()
    assert purchase.user_id == user.id
    assert purchase.child_id == child.id
    assert str(purchase.journey_id) == JOURNEY_ID


async def test_a_second_webhook_for_the_same_child_does_not_duplicate(client, session, user, outbound):
    child = (await session.execute(
        select(Child).where(Child.user_id == user.id))).scalars().first()
    event = stripe_event(client_reference_id=str(child.id))

    await client.post("/checkout", json=event)
    await client.post("/checkout", json=event)

    rows = (await session.execute(
        select(Purchase).where(Purchase.child_id == child.id))).scalars().all()
    assert len(rows) == 1


async def test_a_payment_with_no_child_is_recorded_against_the_email(client, session, outbound):
    """Someone can pay before they have an account."""
    r = await client.post("/checkout", json=stripe_event(
        customer_details={"email": "early@example.test", "name": "Early Bird"}))
    assert r.status_code == 200

    purchase = (await session.execute(
        select(Purchase).where(Purchase.email == "early@example.test"))).scalar_one()
    assert purchase.user_id is None
    assert purchase.child_id is None
    assert str(purchase.journey_id) == JOURNEY_ID


async def test_the_buyer_is_added_to_the_marketing_list(client, session, user, outbound):
    child = (await session.execute(
        select(Child).where(Child.user_id == user.id))).scalars().first()
    await client.post("/checkout", json=stripe_event(client_reference_id=str(child.id)))
    assert outbound["klaviyo"] == [user.email]


async def test_the_purchase_email_always_fires(client, session, outbound):
    await client.post("/checkout", json=stripe_event(
        customer_details={"email": "early@example.test"}))
    assert outbound["purchase_email"] == [("cs_live_1", None)]


async def test_the_insight_email_only_fires_when_metadata_asks(client, session, user, outbound):
    child = (await session.execute(
        select(Child).where(Child.user_id == user.id))).scalars().first()

    await client.post("/checkout", json=stripe_event(client_reference_id=str(child.id)))
    assert outbound["insight"] == []

    session.add(Insight(real_user_id=user.id, child_id=child.id,
                        journey_id=JOURNEY_ID, request_id=child.id,
                        status="ready", teaser_text="t"))
    await session.commit()

    event = stripe_event(client_reference_id=str(child.id))
    event["data"]["object"]["metadata"] = {"send_email": True}
    await client.post("/checkout", json=event)
    assert len(outbound["insight"]) == 1


async def test_the_webhook_accepts_anything_with_no_signature_check(client, session, outbound):
    """Documents the current behaviour rather than hiding it.

    No auth, no stripe-signature verification — a forged body is accepted and
    writes a real Purchases row. Xano does exactly this today. If this test ever
    fails, someone has added verification, which is a deliberate change.
    """
    r = await client.post("/checkout", json=stripe_event(
        customer_details={"email": "attacker@example.test"}))

    assert r.status_code == 200
    assert (await session.execute(
        select(Purchase).where(Purchase.email == "attacker@example.test"))).scalar_one()
