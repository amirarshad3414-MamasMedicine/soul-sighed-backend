"""Request shapes for the Stripe endpoints."""
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.base import XanoSchema

JOURNEY_ID = "fff90478-924f-4ec7-95a1-68b5549a0ec9"


class CreateCheckoutSessionIn(BaseModel):
    """Every field is optional in Xano; Stripe does the real validation."""

    success_url: str | None = None
    cancel_url: str | None = None
    line_items: list[dict[str, Any]] | None = None
    client_reference_id: str | None = None
    customer_email: str | None = None
    send_email: bool | None = None


class WebhookAck(XanoSchema):
    success: bool = Field(default=True)
