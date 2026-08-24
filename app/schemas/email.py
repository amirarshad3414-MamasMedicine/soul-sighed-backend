"""Response shape for the `Email` queue."""
from datetime import datetime

from pydantic import BaseModel

from app.schemas.base import EpochMillis, XanoSchema


class EmailOut(XanoSchema):
    id: int
    created_at: EpochMillis
    email: str | None
    subject: str | None
    html_content: str | None
    timestamp: EpochMillis
    delivered: bool | None


class DeliverEmailIn(BaseModel):
    email_id: int


class ScheduleEmailIn(BaseModel):
    email: str
    subject: str
    body: str
    scheduled_time: datetime
