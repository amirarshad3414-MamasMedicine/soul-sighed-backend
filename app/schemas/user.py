"""Response shapes for the user endpoints."""
from app.schemas.base import EpochMillis, XanoSchema


class UserMe(XanoSchema):
    """`GET /auth/me`.

    Xano projects the row to exactly these eight columns — `password` is
    access=internal and never leaves the backend. Keep the list identical:
    adding a field here leaks something Xano did not return.
    """

    id: int
    created_at: EpochMillis
    name: str | None
    email: str | None
    account_id: int | None
    relationship_focus: str | None
    role: str | None
    password_reset: dict | None
