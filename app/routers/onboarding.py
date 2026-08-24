"""Onboarding submission, ported from the Xano `scripters` API group."""
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import settings
from app.core.deps import current_user
from app.database import get_session
from app.models import Child, Insight, Purchase, User
from app.schemas.onboarding import (
    PlaceNotResolved,
    SubmitOnboardingIn,
    SubmitOnboardingResponse,
)
from app.services import google_places, insights, notifications

router = APIRouter(tags=["onboarding"])

PLACE_NOT_RESOLVED_MESSAGE = (
    "We couldn’t validate this birthplace. "
    "Please select a suggested location from the dropdown."
)


async def _coordinates(place_id: str | None) -> dict[str, float] | None:
    """Google lookup for one birthplace, or None if it cannot be resolved."""
    try:
        payload = await google_places.details_for_geocoding(place_id)
        location = payload["result"]["geometry"]["location"]
        return {"lat": location["lat"], "lon": location["lng"]}
    except Exception:
        return None


@router.post("/submit_onboarding")
async def submit_onboarding(
    body: SubmitOnboardingIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    """Generate a reading, retrying the provider up to five times.

    Ported from .../47_submit_onboarding.xs, the largest endpoint in the group.

    Kept identical, including the parts that are questionable:

    * The purchase check and the "insight already exists" early return are both
      commented out in Xano, so a reading is generated whether or not anything
      was paid for, and duplicates are not prevented. `has_purchase` is still
      computed, because it gates the follow-up email.
    * Generation is synchronous, inside the request, with a 300-second provider
      timeout and five attempts. The Insights row is written as "processing"
      *before* the loop, so if the request dies mid-flight the row is stranded
      there forever with no error — that is the origin of the 7 stuck rows in
      production. This should become a background job with a dead-letter, but
      the response carries the finished `teaser`, so making it asynchronous is a
      contract change and belongs in triage, not in the port.
    * An unresolvable birthplace returns HTTP **200** with an error object,
      because Xano uses `return` inside the catch.
    """
    is_child = body.user_relation == "child"
    payload = body.onboarding_payload

    has_purchase = (await db.execute(
        select(Purchase.id)
        .where(Purchase.user_id == user.id)
        .where(Purchase.child_id == body.child_id)
        .where(Purchase.journey_id == body.journey_id)
        .limit(1))).first() is not None

    parent_coords = await _coordinates(payload.user_birth_place_id)
    child_coords = await _coordinates(payload.child_birth_place_id)
    if parent_coords is None or child_coords is None:
        return JSONResponse(status_code=200, content=PlaceNotResolved(
            message=PLACE_NOT_RESOLVED_MESSAGE).model_dump())

    child = (await db.execute(
        select(Child).where(Child.id == body.child_id))).scalar_one_or_none()
    if child is not None:
        child.default_child = False
        child.name = payload.childname
        child.lat = child_coords["lat"]
        child.lon = child_coords["lon"]
        db.add(child)

    api_payload = insights.build_payload(
        payload.model_dump(), is_child=is_child,
        parent_coords=parent_coords, child_coords=child_coords)

    insight = Insight(real_user_id=user.id, child_id=body.child_id,
                      journey_id=body.journey_id, status="processing",
                      insights_api_payload=api_payload, request_id=uuid4(),
                      created_at=datetime.now(UTC))
    db.add(insight)
    await db.commit()
    await db.refresh(insight)

    teaser = ""
    for attempt in range(settings.insight_max_retries):
        try:
            response = await insights.generate(api_payload)
            if response.status_code != 200:
                raise RuntimeError(
                    f"External API returned status {response.status_code}")
            result = response.json()
            insight.status = "ready"
            insight.deep_text = result.get("deep")
            insight.summary_text = result.get("summary")
            insight.teaser_text = result.get("teaser")
            teaser = result.get("teaser") or ""
            db.add(insight)
            await db.commit()
            break
        except Exception as error:  # noqa: BLE001 — Xano catches everything here
            insight.last_error = f"Attempt {attempt + 1} failed: {error}"
            if attempt == settings.insight_max_retries - 1:
                insight.status = "failed"
            db.add(insight)
            await db.commit()

    await db.refresh(insight)

    if has_purchase:
        await notifications.send_insight(
            payload.childname, payload.username, user.email, insight)

    return SubmitOnboardingResponse(
        message="Insight created successfully.",
        insight_id=insight.id,
        status=insight.status,
        external_api_payload=api_payload,
        teaser=teaser,
    )
