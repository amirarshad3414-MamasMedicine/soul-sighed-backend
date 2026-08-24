"""otp/store, verify_otp, update_password — Xano `scripters` 63, 64, 65.

All three are unauthenticated in Xano and stay that way under the auth-parity
rule. test_update_password_needs_no_proof_of_anything documents that as a fact
rather than an accident — see the triage note in the migration plan.
"""
from datetime import UTC, datetime, timedelta

from sqlmodel import select

from app.core.security import verify_password
from app.models import User

EMAIL = "reset@example.test"


async def _account(client, session) -> User:
    await client.post("/auth/signup",
                      json={"name": "Reset Me", "email": EMAIL, "password": "old-password"})
    return (await session.execute(
        select(User).where(User.email == EMAIL))).scalar_one()


async def _fresh(session, user) -> User:
    await session.refresh(user)
    return user


# --- otp/store ---------------------------------------------------------------

async def test_store_otp_records_code_and_expiry(client, session):
    user = await _account(client, session)
    before = datetime.now(UTC)

    r = await client.post("/otp/store",
                          json={"email": EMAIL, "otp": "123456", "expiresIn": 600})
    assert r.status_code == 200
    assert r.json() == {"success": True, "message": "OTP stored successfully"}

    user = await _fresh(session, user)
    assert user.otp == "123456"
    assert before + timedelta(seconds=595) < user.otp_expiry < before + timedelta(seconds=605)


async def test_store_otp_for_an_unknown_email_is_an_input_error(client, session):
    r = await client.post("/otp/store",
                          json={"email": "nobody@example.test", "otp": "1", "expiresIn": 60})
    assert r.status_code == 400
    assert r.json()["message"] == "User not found"


# --- verify_otp --------------------------------------------------------------

async def test_verify_accepts_the_right_code(client, session):
    await _account(client, session)
    await client.post("/otp/store", json={"email": EMAIL, "otp": "123456", "expiresIn": 600})

    r = await client.post("/verify_otp", json={"email": EMAIL, "otp": "123456"})
    assert r.status_code == 200
    assert r.json() == {"message": "OTP verified successfully"}


async def test_verify_burns_the_code(client, session):
    user = await _account(client, session)
    await client.post("/otp/store", json={"email": EMAIL, "otp": "123456", "expiresIn": 600})
    await client.post("/verify_otp", json={"email": EMAIL, "otp": "123456"})

    r = await client.post("/verify_otp", json={"email": EMAIL, "otp": "123456"})
    assert r.status_code == 400
    user = await _fresh(session, user)
    assert user.otp == ""          # NOT NULL, so Xano's null becomes ""


async def test_a_burnt_code_cannot_be_replayed_as_an_empty_string(client, session):
    """After verification `otp` is "", so an empty submission matches it. The
    expiry check is what actually stops the replay — verified, not assumed."""
    await _account(client, session)
    await client.post("/otp/store", json={"email": EMAIL, "otp": "123456", "expiresIn": 600})
    await client.post("/verify_otp", json={"email": EMAIL, "otp": "123456"})

    r = await client.post("/verify_otp", json={"email": EMAIL, "otp": ""})
    assert r.status_code == 400
    assert r.json()["message"] == "OTP has expired. Please request a new one."


async def test_verify_rejects_a_wrong_code(client, session):
    await _account(client, session)
    await client.post("/otp/store", json={"email": EMAIL, "otp": "123456", "expiresIn": 600})

    r = await client.post("/verify_otp", json={"email": EMAIL, "otp": "999999"})
    assert r.status_code == 400
    assert r.json()["message"] == "Invalid OTP code. Please try again."


async def test_verify_rejects_an_expired_code(client, session):
    user = await _account(client, session)
    await client.post("/otp/store", json={"email": EMAIL, "otp": "123456", "expiresIn": 600})
    user = await _fresh(session, user)
    user.otp_expiry = datetime.now(UTC) - timedelta(seconds=1)
    session.add(user)
    await session.commit()

    r = await client.post("/verify_otp", json={"email": EMAIL, "otp": "123456"})
    assert r.status_code == 400
    assert r.json()["message"] == "OTP has expired. Please request a new one."


async def test_verify_for_an_unknown_email(client, session):
    r = await client.post("/verify_otp", json={"email": "nobody@example.test", "otp": "1"})
    assert r.status_code == 400
    assert r.json()["message"] == "User not found."


# --- update_password ---------------------------------------------------------

async def test_update_password_changes_the_hash(client, session):
    user = await _account(client, session)
    r = await client.post("/update_password",
                          json={"email": EMAIL, "newPassword": "brand-new"})
    assert r.status_code == 200
    assert r.json() == {"message": "Password updated successfully"}

    user = await _fresh(session, user)
    assert verify_password("brand-new", user.password)
    assert not verify_password("old-password", user.password)


async def test_update_password_then_login_with_the_new_one(client, session):
    await _account(client, session)
    await client.post("/update_password", json={"email": EMAIL, "newPassword": "brand-new"})

    r = await client.post("/auth/login", json={"email": EMAIL, "password": "brand-new"})
    assert r.status_code == 200


async def test_update_password_for_an_unknown_email(client, session):
    r = await client.post("/update_password",
                          json={"email": "nobody@example.test", "newPassword": "x"})
    assert r.status_code == 403
    assert r.json()["message"] == "404 Not Found"


async def test_update_password_needs_no_proof_of_anything(client, session):
    """Documents current behaviour, which is a real account-takeover path.

    No auth header, no OTP, no token — an email address is the only thing
    required to replace someone's password. Xano does exactly this today, so the
    port reproduces it and the test records it. If this ever starts failing,
    someone has fixed it, and that is a deliberate change to acknowledge rather
    than a regression.
    """
    await _account(client, session)

    r = await client.post("/update_password",
                          json={"email": EMAIL, "newPassword": "attacker-chosen"})

    assert r.status_code == 200
    login = await client.post("/auth/login",
                              json={"email": EMAIL, "password": "attacker-chosen"})
    assert login.status_code == 200
