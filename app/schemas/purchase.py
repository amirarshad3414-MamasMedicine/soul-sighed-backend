"""Response shape for the `Purchases` table."""
from uuid import UUID

from app.schemas.base import EpochMillis, XanoSchema


class PurchaseOut(XanoSchema):
    id: UUID
    created_at: EpochMillis
    user_id: int | None
    child_id: UUID | None
    journey_id: UUID | None
    purchase_source: str | None
    purchase_reference: str | None
    email: str | None
