"""Children endpoints, ported from the Xano `scripters` API group."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.deps import current_user
from app.core.errors import XanoError
from app.database import get_session
from app.models import Child, Insight, Purchase, User
from app.schemas.child import AddChildIn, ChildOut, GetChildrenResponse
from app.services import google_places

router = APIRouter(tags=["children"])


@router.get("/get_children", response_model=GetChildrenResponse)
async def get_children(
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> GetChildrenResponse:
    """Everything the dashboard needs for the signed-in user.

    Ported from xano-export/.../44_get_children.xs. Note the name is misleading
    on both sides: it returns children, insights and purchases together.

    Two deliberate notes on parity:

    * Xano re-fetches the user row and reads `$user.id` from it, which is just
      `$auth.id` again. Skipped here — same result, one less query.
    * If the token is valid but the user row is gone, Xano returns 200 with three
      empty lists, because `db.get` yields null and every filter matches nothing.
      `current_user` raises 401 instead. Rare enough to accept; recorded in
      triage rather than reproduced.
    """
    children = (await db.execute(
        select(Child).where(Child.user_id == user.id))).scalars().all()
    insights = (await db.execute(
        select(Insight).where(Insight.real_user_id == user.id))).scalars().all()
    purchases = (await db.execute(
        select(Purchase).where(Purchase.user_id == user.id))).scalars().all()

    return GetChildrenResponse(
        children=children, insights=insights, purchases=purchases)


@router.get("/get_child_by_id", response_model=ChildOut)
async def get_child_by_id(
    child_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> Child:
    """One child, if it belongs to the caller.

    Ported from .../70_get_child_by_id.xs. Parity detail worth keeping: Xano
    fetches the row first and then asserts `$child_record.user_id == $auth.id`.
    When the id does not exist the row is null, `null.user_id` is null, the
    comparison fails, and the caller gets the *unauthorized* error — not a 404.
    Reproduced exactly, so an unknown id and someone else's id are
    indistinguishable to the caller.
    """
    child = (await db.execute(
        select(Child).where(Child.id == child_id))).scalar_one_or_none()

    if child is None or child.user_id != user.id:
        raise XanoError("unauthorized",
                        "You do not have permission to view this record.")
    return child


@router.post("/add_children")
async def add_children(
    body: AddChildIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Add a child or parent figure to the caller's account.

    Ported from .../45_add_children.xs. Three details are reproduced on purpose:

    * The duplicate check uses Xano's `==?`, which behaves like SQL `=` — NULL
      never equals NULL. So when no date of birth is given the check can never
      match and the insert always proceeds. That is why 52 duplicate rows exist
      today, every group of them with a null dob. Using IS NOT DISTINCT FROM
      here would reject inserts Xano accepts.
    * A failed Google lookup leaves lat and lon unset. The columns are NOT NULL
      with a 0 default, so Xano's null becomes 0 — omitting them here does the
      same thing rather than raising.
    * `place_id` is grafted onto the response only when one was supplied, so the
      response genuinely has two shapes. No OpenAPI spec can express that, which
      is why the response model is a plain dict.
    """
    latitude = longitude = None
    if body.place_of_birth_id is not None:
        latitude, longitude = await google_places.coordinates_for(body.place_of_birth_id)

    if body.dob is not None:
        duplicate = (await db.execute(
            select(Child.id)
            .where(Child.user_id == user.id)
            .where(Child.name == body.name)
            .where(Child.date_of_birth == body.dob)
            .limit(1))).first()
        if duplicate is not None:
            raise XanoError("inputerror", "Record already exists")

    child = Child(user_id=user.id, name=body.name, date_of_birth=body.dob,
                  pronoun=body.pronoun, relationship_focus=body.relationship_focus)
    if latitude is not None:
        child.lat = latitude
    if longitude is not None:
        child.lon = longitude

    db.add(child)
    await db.commit()
    await db.refresh(child)

    response = ChildOut.model_validate(child).model_dump(mode="json")
    if body.place_of_birth_id is not None:
        response["place_id"] = body.place_of_birth_id
    return response
