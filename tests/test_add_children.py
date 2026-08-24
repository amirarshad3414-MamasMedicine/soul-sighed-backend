"""POST /add_children — Xano `scripters` 45.

The duplicate rule is the interesting part. Xano's `==?` behaves like SQL `=`,
so a null date of birth never matches a null date of birth and the guard simply
does not fire. That is not a theory: the live table holds 52 duplicate rows in
16 groups, and every one of those groups has a null dob.
"""
import pytest
from sqlmodel import select

from app.models import Child
from app.services import google_places
from tests.conftest import auth_headers

LAHORE = {"result": {"geometry": {"location": {"lat": 31.5203696, "lng": 74.3587473}}}}


@pytest.fixture
def google(monkeypatch):
    state = {"response": LAHORE, "calls": []}

    async def fake(place_id):
        state["calls"].append(place_id)
        if isinstance(state["response"], Exception):
            raise state["response"]
        return state["response"]

    monkeypatch.setattr(google_places, "details_for_geocoding", fake)
    return state


async def add(client, user, **body):
    return await client.post("/add_children", headers=auth_headers(user),
                             json={"name": "Yusuf", "relationship_focus": "child", **body})


async def test_creates_a_child(client, session, user, google):
    r = await add(client, user, dob="2019-04-11", pronoun="he/him")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Yusuf"
    assert body["date_of_birth"] == "2019-04-11"
    assert body["relationship_focus"] == "child"


async def test_geocodes_when_a_place_id_is_given(client, session, user, google):
    body = (await add(client, user, place_of_birth_id="ChIJlahore")).json()
    assert google["calls"] == ["ChIJlahore"]
    assert body["lat"] == pytest.approx(31.5203696)
    assert body["lon"] == pytest.approx(74.3587473)


async def test_place_id_appears_in_the_response_only_when_supplied(client, session, user, google):
    """The response genuinely has two shapes — Xano grafts the key on."""
    with_place = (await add(client, user, place_of_birth_id="ChIJlahore")).json()
    without = (await add(client, user, name="Other")).json()

    assert with_place["place_id"] == "ChIJlahore"
    assert "place_id" not in without


async def test_a_google_failure_still_saves_the_child(client, session, user, google):
    """Xano swallows the error and leaves the coordinates unset. The columns are
    NOT NULL with a 0 default, so what lands is 0, not null."""
    google["response"] = RuntimeError("REQUEST_DENIED")

    r = await add(client, user, place_of_birth_id="ChIJbroken")
    assert r.status_code == 200
    assert r.json()["lat"] == 0
    assert r.json()["lon"] == 0


async def test_place_of_birth_is_accepted_and_ignored(client, session, user, google):
    """Xano declares the input and never reads it. Only the place id is used."""
    r = await add(client, user, place_of_birth="Lahore, Pakistan")
    assert r.status_code == 200
    assert google["calls"] == []


async def test_the_same_name_and_dob_twice_is_refused(client, session, user, google):
    await add(client, user, dob="2019-04-11")
    r = await add(client, user, dob="2019-04-11")

    assert r.status_code == 400
    assert r.json()["message"] == "Record already exists"


async def test_a_different_dob_is_allowed(client, session, user, google):
    await add(client, user, dob="2019-04-11")
    assert (await add(client, user, dob="2020-01-01")).status_code == 200


async def test_duplicates_slip_through_when_there_is_no_dob(client, session, user, google):
    """Documents the real bug rather than fixing it silently.

    With a null dob the guard cannot match, so Xano inserts again — which is how
    one child ended up recorded 22 times. Changing this would make the parity
    diff disagree, so it is a triage decision, not a port decision.
    """
    for _ in range(3):
        assert (await add(client, user)).status_code == 200

    rows = (await session.execute(
        select(Child).where(Child.name == "Yusuf"))).scalars().all()
    assert len(rows) == 3


async def test_another_users_child_with_the_same_name_is_not_a_duplicate(
        client, session, user, google):
    await add(client, user, dob="2019-04-11")

    from app.models import User
    other = User(name="Other", email="other@example.test", relationship_focus="parent")
    session.add(other)
    await session.flush()
    await session.commit()

    r = await add(client, other, dob="2019-04-11")
    assert r.status_code == 200


async def test_relationship_focus_is_required(client, session, user, google):
    """Declared without `?` in Xano. One frontend caller omits it — empirical
    test #3 in the plan — so this endpoint should reject that call today."""
    r = await client.post("/add_children", headers=auth_headers(user),
                          json={"name": "No Focus"})
    assert r.status_code == 400
    assert r.json()["code"] == "ERROR_CODE_INPUT_ERROR"


async def test_requires_authentication(client, google):
    r = await client.post("/add_children",
                          json={"name": "X", "relationship_focus": "child"})
    assert r.status_code == 401
