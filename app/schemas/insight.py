"""Response shape for the `Insights` table."""
from uuid import UUID

from app.schemas.base import EpochMillis, XanoSchema


class InsightOut(XanoSchema):
    """One generated reading.

    `status` is a plain string, not an enum: the live table holds "ready",
    "processing", "failed" and one empty string.
    """

    id: UUID
    created_at: EpochMillis
    real_user_id: int | None
    child_id: UUID | None
    journey_id: UUID | None
    status: str | None
    deep_text: str | None
    summary_text: str | None
    teaser_text: str | None
    request_id: UUID | None
    last_error: str | None
    insights_api_payload: dict | None
