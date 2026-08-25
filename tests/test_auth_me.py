"""GET /auth/me — ported from Xano `scripters` endpoint 54."""
from tests.conftest import auth_headers

# Xano projects the user row to exactly these columns.
EXPECTED_KEYS = {"id", "created_at", "name", "email", "account_id",
                 "relationship_focus", "role", "password_reset"}


async def test_returns_the_signed_in_user(client, user):
    r = await client.get("/auth/me", headers=auth_headers(user))
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == user.id
    assert body["email"] == "parent@example.test"


async def test_returns_exactly_xanos_column_projection(client, user):
    """Extra keys would leak columns Xano never returned — password above all."""
    body = (await client.get("/auth/me", headers=auth_headers(user))).json()
    assert set(body) == EXPECTED_KEYS
    assert "password" not in body


async def test_password_reset_is_the_three_key_object_never_null(client, user):
    """Xano's live auth/me returns password_reset as
    {token:"", expiration:null, used:false} — never null, never {} (measured
    2026-08-25). A frontend reading password_reset.used must not hit null.used.
    """
    body = (await client.get("/auth/me", headers=auth_headers(user))).json()
    assert body["password_reset"] == {"token": "", "expiration": None,
                                      "used": False}


async def test_created_at_is_epoch_millis(client, user):
    body = (await client.get("/auth/me", headers=auth_headers(user))).json()
    assert isinstance(body["created_at"], int)
    assert len(str(body["created_at"])) == 13


async def test_requires_authentication(client):
    assert (await client.get("/auth/me")).status_code == 401
