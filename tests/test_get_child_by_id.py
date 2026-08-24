"""GET /get_child_by_id — ported from Xano `scripters` endpoint 70."""
from uuid import uuid4

from sqlmodel import select

from app.models import Child, User
from tests.conftest import auth_headers

DENIED = "You do not have permission to view this record."


async def _a_child(session, user) -> Child:
    rows = await session.execute(select(Child).where(Child.user_id == user.id))
    return next(c for c in rows.scalars().all() if c.name == "Amina")


async def test_returns_the_childs_row(client, session, user):
    child = await _a_child(session, user)
    r = await client.get(f"/get_child_by_id?child_id={child.id}",
                         headers=auth_headers(user))
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Amina"
    assert body["date_of_birth"] == "2019-04-11"
    assert isinstance(body["created_at"], int)


async def test_another_users_child_is_refused(client, session, user):
    stranger = User(name="Stranger", email="stranger@example.test",
                    relationship_focus="parent")
    session.add(stranger)
    await session.flush()
    theirs = Child(user_id=stranger.id, name="Not Yours", relationship_focus="child")
    session.add(theirs)
    await session.commit()

    r = await client.get(f"/get_child_by_id?child_id={theirs.id}",
                         headers=auth_headers(user))
    assert r.status_code == 401
    assert r.json()["message"] == DENIED


async def test_unknown_id_is_indistinguishable_from_someone_elses(client, user):
    """Xano checks ownership on a null row, so a missing id yields the same
    unauthorized error rather than a 404. Reproduced deliberately."""
    r = await client.get(f"/get_child_by_id?child_id={uuid4()}",
                         headers=auth_headers(user))
    assert r.status_code == 401
    assert r.json()["message"] == DENIED


async def test_missing_child_id_is_an_input_error(client, user):
    """Xano rejects a missing required input with 400, not FastAPI's 422."""
    r = await client.get("/get_child_by_id", headers=auth_headers(user))
    assert r.status_code == 400
    assert r.json()["code"] == "ERROR_CODE_INPUT_ERROR"


async def test_requires_authentication(client):
    assert (await client.get(f"/get_child_by_id?child_id={uuid4()}")).status_code == 401
