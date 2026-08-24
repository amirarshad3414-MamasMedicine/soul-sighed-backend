"""Request and response shapes for submit_onboarding."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.schemas.base import XanoSchema


class OnboardingPayload(BaseModel):
    """The object Xano declares a schema for.

    `user_time_of_birth` and `child_time_of_birth` are declared here because the
    frontend sends them, and are then never used — exactly as in Xano. Every one
    of the 331 live payloads carries T00:00 as a result.
    """

    username: str | None = None
    childname: str | None = None
    user_dob: datetime | None = None
    user_time_of_birth: datetime | None = None
    user_birth_place_id: str | None = None
    child_dob: datetime | None = None
    child_time_of_birth: datetime | None = None
    child_birth_place_id: str | None = None
    raw_user_message: str | None = None
    climate: str | None = None
    activation: str | None = None
    closeness: str | None = None
    posture: str | None = None
    summary: str | None = None
    emotionTags: str | None = None      # noqa: N815 — the frontend sends these keys
    keyThemes: str | None = None        # noqa: N815
    parentPronouns: str | None = None   # noqa: N815
    childPronouns: str | None = None    # noqa: N815


class SubmitOnboardingIn(BaseModel):
    child_id: UUID
    journey_id: UUID
    onboarding_payload: OnboardingPayload
    user_relation: str = "parent"

    @field_validator("user_relation", mode="before")
    @classmethod
    def _trim(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SubmitOnboardingResponse(XanoSchema):
    message: str
    insight_id: UUID
    status: str
    external_api_payload: dict[str, Any]
    teaser: str


class PlaceNotResolved(XanoSchema):
    """Returned with HTTP 200, not an error status.

    Xano uses `return` inside the catch, which short-circuits the stack and
    sends this body with a normal 200. The frontend therefore has to inspect the
    body rather than the status code.
    """

    error: str = "PLACE_NOT_RESOLVED"
    message: str
