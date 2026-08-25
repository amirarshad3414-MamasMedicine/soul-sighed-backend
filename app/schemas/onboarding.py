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

    @field_validator("user_dob", "child_dob", mode="before")
    @classmethod
    def _empty_string_is_no_date(cls, value: object) -> object:
        """Treat "" as absent, the way Xano's optional timestamps do.

        The frontend builds every field with `|| ""` (see
        app/onboardingMain/page.jsx mapToOnboardingPayload), so a value left
        blank arrives as an empty string rather than null. Pydantic rejects ""
        for a datetime and the whole request 400s with "Input validation
        failed" — but Xano accepts it. A real date must still parse, so this
        only maps blank to None.
        """
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("user_time_of_birth", "child_time_of_birth", mode="before")
    @classmethod
    def _birth_time_is_never_a_timestamp(cls, value: object) -> object:
        """Accept whatever the birth-time inputs send, including "14:30".

        These two fields come from `<input type="time">`, so a filled-in time
        arrives as a bare "HH:MM" — which is not a datetime, and Pydantic
        rejected the entire request with "Input validation failed". Xano
        declares them `timestamp ...?` and accepts the value, then never reads
        it: all 331 live payloads carry T00:00 for both people, because only
        the date fields reach the calculation.

        So the parity-correct behaviour is to accept and discard. Dropping an
        unparseable value here changes no output — it only stops a field the
        product ignores from failing the whole reading. Whether birth times
        SHOULD reach the calculation is an open triage question; fixing that is
        a deliberate behaviour change, not this. Found by running the real
        onboarding flow with a birth time filled in, 2026-08-25.
        """
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value) if value.strip() else None
            except ValueError:
                return None      # e.g. "14:30" — collected, never used
        return value


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
