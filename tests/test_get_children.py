"""GET /get_children — ported from Xano `scripters` endpoint 44.

Checks behaviour and, just as importantly, wire format: the frontend was built
against Xano's exact serialisation, so a correct query with the wrong shape is
still a break. Format rules come from xano-export/formats.md.
"""
import pytest

from app.models import Child, User
from tests.conftest import auth_headers as auth


async def test_returns_children_insights_and_purchases(client, session, user):
    r = await client.get("/get_children", headers=auth(user))

    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"children", "insights", "purchases"}
    assert len(body["children"]) == 2
    assert len(body["insights"]) == 1
    assert len(body["purchases"]) == 1


async def test_wire_format_matches_xano(client, session, user):
    body = (await client.get("/get_children", headers=auth(user))).json()
    child = next(c for c in body["children"] if c["name"] == "Amina")

    # timestamps are epoch milliseconds, not ISO strings. The literal guards
    # against the classic seconds-vs-milliseconds slip: 2026-08-05 09:31 UTC.
    assert isinstance(child["created_at"], int)
    assert child["created_at"] == 1785922260000
    assert len(str(child["created_at"])) == 13

    # dates are plain YYYY-MM-DD — a different format in the same row
    assert child["date_of_birth"] == "2019-04-11"

    # uuids are strings
    assert isinstance(child["id"], str) and len(child["id"]) == 36

    # JSON columns come back as objects
    assert body["insights"][0]["insights_api_payload"]["p1Lat"] == 31.52


async def test_null_keys_are_present_not_omitted(client, user):
    """Xano returns every key on every row. Dropping nulls changes the shape.

    Which columns are null and which hold a zero value is not a matter of taste
    — it is what the live table does. Across 505 real children rows,
    user_01_id / date_of_birth / time_of_birth / pronoun are null, while name is
    "" and lat / lon are numbers. The column nullability reproduces that.
    """
    body = (await client.get("/get_children", headers=auth(user))).json()
    bare = next(c for c in body["children"] if c["name"] == "")

    for key in ("date_of_birth", "time_of_birth", "pronoun", "user_01_id"):
        assert key in bare, f"{key} was omitted; Xano always includes it"
        assert bare[key] is None, f"{key} is nullable in Xano and should be null"

    for key, zero in (("name", ""), ("lat", 0), ("lon", 0), ("default_child", False)):
        assert bare[key] == zero, f"{key} is NOT NULL in Xano with a {zero!r} default"


async def test_only_the_callers_own_rows_come_back(client, session, user):
    other = User(name="Someone Else", email="other@example.test",
                 relationship_focus="parent")
    session.add(other)
    await session.flush()
    session.add(Child(user_id=other.id, name="Not Yours", relationship_focus="child"))
    await session.commit()

    body = (await client.get("/get_children", headers=auth(user))).json()
    assert {c["name"] for c in body["children"]} == {"Amina", ""}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nonsense"}])
async def test_requires_authentication(client, headers):
    """Xano declares auth = "user" on this endpoint, so it must stay protected."""
    assert (await client.get("/get_children", headers=headers)).status_code == 401
