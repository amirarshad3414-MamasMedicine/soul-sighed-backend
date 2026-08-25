"""auth/login, auth/signup, register_passwordless — Xano `scripters` 53, 52, 73."""
from sqlmodel import select

from app.core.security import decode_access_token
from app.models import Child, Purchase, User
from tests.conftest import JOURNEY_ID


async def signup(client, **body):
    return await client.post("/auth/signup",
                             json={"name": "Amir", "email": "new@example.test",
                                   "password": "hunter2", **body})


# --- auth/signup -------------------------------------------------------------

async def test_signup_returns_a_usable_token(client, session):
    r = await signup(client)
    assert r.status_code == 200
    token = r.json()["authToken"]
    user = (await session.execute(
        select(User).where(User.email == "new@example.test"))).scalar_one()
    assert int(decode_access_token(token)["sub"]) == user.id


async def test_signup_creates_a_placeholder_child(client, session):
    """Xano adds a nameless child with default_child = true. This is where the
    empty-name rows in the live table come from."""
    await signup(client)
    user = (await session.execute(
        select(User).where(User.email == "new@example.test"))).scalar_one()
    child = (await session.execute(
        select(Child).where(Child.user_id == user.id))).scalar_one()
    assert child.default_child is True
    # name is NOT NULL in Xano with a "" default, which is exactly why the live
    # children table holds empty-string names rather than nulls.
    assert child.name == ""


async def test_signup_adopts_purchases_bought_before_the_account_existed(client, session):
    """Paying before signing up writes a Purchase keyed only by email."""
    # checkout's "paid before signing up" branch writes exactly this shape:
    # email set, user_id and child_id null, journey_id hardcoded.
    session.add(Purchase(email="new@example.test", purchase_source="stripe",
                         purchase_reference="cs_early", journey_id=JOURNEY_ID))
    await session.commit()

    await signup(client)
    purchase = (await session.execute(
        select(Purchase).where(Purchase.purchase_reference == "cs_early"))).scalar_one()
    user = (await session.execute(
        select(User).where(User.email == "new@example.test"))).scalar_one()
    assert purchase.user_id == user.id
    assert purchase.child_id is not None


async def test_signup_refuses_a_duplicate_email(client, session):
    await signup(client)
    r = await signup(client)
    assert r.status_code == 403
    assert r.json()["message"] == "This account is already in use."


async def test_signup_normalises_the_email(client, session):
    """Xano applies `filters=lower|trim` to the email input."""
    await signup(client, email="  MiXeD@Example.Test  ")
    assert (await session.execute(
        select(User).where(User.email == "mixed@example.test"))).scalar_one_or_none()


async def test_signup_stores_a_hash_not_the_password(client, session):
    await signup(client)
    user = (await session.execute(
        select(User).where(User.email == "new@example.test"))).scalar_one()
    assert user.password != "hunter2"
    assert user.password.startswith("$argon2")


# --- auth/login --------------------------------------------------------------

async def test_login_succeeds_with_the_right_password(client, session):
    await signup(client)
    r = await client.post("/auth/login",
                          json={"email": "new@example.test", "password": "hunter2"})
    assert r.status_code == 200
    assert "authToken" in r.json()


async def test_login_rejects_a_wrong_password(client, session):
    await signup(client)
    r = await client.post("/auth/login",
                          json={"email": "new@example.test", "password": "wrong"})
    assert r.status_code == 500  # Xano: bare precondition -> ERROR_FATAL (measured)
    # The whole envelope, measured against live Xano 2026-08-25:
    assert r.json() == {"code": "ERROR_FATAL",
                        "message": "Invalid Credentials.", "payload": ""}


async def test_unknown_account_is_indistinguishable_from_a_wrong_password(client, session):
    """Both preconditions in Xano use the same message, so account existence
    cannot be probed. Verified rather than assumed."""
    await signup(client)
    wrong_password = await client.post(
        "/auth/login", json={"email": "new@example.test", "password": "wrong"})
    no_account = await client.post(
        "/auth/login", json={"email": "nobody@example.test", "password": "hunter2"})
    assert wrong_password.status_code == no_account.status_code
    assert wrong_password.json()["message"] == no_account.json()["message"]


async def test_a_passwordless_account_cannot_log_in_with_a_password(client, session):
    await client.post("/register_passwordless",
                      json={"name": "No Password", "email": "np@example.test"})
    r = await client.post("/auth/login",
                          json={"email": "np@example.test", "password": "anything"})
    assert r.status_code == 500  # Xano: bare precondition -> ERROR_FATAL (measured)


async def test_login_with_no_body_fields_is_invalid_credentials_not_a_crash(client):
    """Both inputs are optional in Xano, so this must not be an input error."""
    r = await client.post("/auth/login", json={})
    assert r.status_code == 500  # Xano: bare precondition -> ERROR_FATAL (measured)
    assert r.json()["message"] == "Invalid Credentials."


# --- register_passwordless ---------------------------------------------------

async def test_passwordless_creates_a_user_with_no_password(client, session):
    r = await client.post("/register_passwordless",
                          json={"name": "No Password", "email": "np@example.test"})
    assert r.status_code == 200
    assert r.json()["message"] == "user created successfully"
    user = (await session.execute(
        select(User).where(User.email == "np@example.test"))).scalar_one()
    assert user.password is None


async def test_passwordless_does_not_create_a_child(client, session):
    """Unlike auth/signup. The signup flow adds the child itself, later."""
    await client.post("/register_passwordless",
                      json={"name": "No Password", "email": "np@example.test"})
    user = (await session.execute(
        select(User).where(User.email == "np@example.test"))).scalar_one()
    children = (await session.execute(
        select(Child).where(Child.user_id == user.id))).scalars().all()
    assert children == []


async def test_passwordless_refuses_a_duplicate_email(client, session):
    body = {"name": "No Password", "email": "np@example.test"}
    await client.post("/register_passwordless", json=body)
    r = await client.post("/register_passwordless", json=body)
    assert r.status_code == 403
    assert r.json()["message"] == "This account is already in use."


async def test_token_expires_in_24_hours_like_xano(client, session):
    r = await signup(client)
    claims = decode_access_token(r.json()["authToken"])
    assert claims["exp"] - claims["iat"] == 86400
