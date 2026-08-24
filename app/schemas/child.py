"""Response shapes for the children endpoints."""
from datetime import date
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.schemas.base import EpochMillis, XanoSchema
from app.schemas.insight import InsightOut
from app.schemas.purchase import PurchaseOut


class ChildOut(XanoSchema):
    """One row of the `children` table, exactly as Xano returns it."""

    id: UUID
    created_at: EpochMillis
    user_01_id: UUID | None
    user_id: int | None
    name: str | None
    date_of_birth: date | None
    time_of_birth: EpochMillis
    lat: float | None
    lon: float | None
    pronoun: str | None
    default_child: bool | None
    relationship_focus: str


class GetChildrenResponse(XanoSchema):
    """`GET /get_children` returns three lists side by side, not just children."""

    children: list[ChildOut]
    insights: list[InsightOut]
    purchases: list[PurchaseOut]


def _trim(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class AddChildIn(BaseModel):
    """Inputs of `POST /add_children`.

    `name` and `relationship_focus` are required in Xano (no `?` on either);
    `dob` is both optional and nullable. `place_of_birth` is accepted and then
    never used — only `place_of_birth_id` reaches the stack. Kept so existing
    callers do not start failing validation.
    """

    name: str
    relationship_focus: str
    dob: date | None = None
    place_of_birth: str | None = None
    place_of_birth_id: str | None = None
    pronoun: str | None = None

    _trim_strings = field_validator(
        "name", "relationship_focus", "place_of_birth", "place_of_birth_id",
        "pronoun", mode="before")(_trim)
