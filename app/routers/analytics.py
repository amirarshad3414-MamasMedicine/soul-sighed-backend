"""Onboarding funnel endpoints, ported from the Xano `scripters` API group."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.errors import XanoError
from app.database import get_session
from app.models import OnboardingVisit
from app.schemas.analytics import (
    OnboardingVisitStats,
    TrackVisitIn,
    TrackVisitResponse,
)

router = APIRouter(tags=["analytics"])


async def _count_flow(db: AsyncSession, flow: str) -> int:
    """Visitors in one flow, counted from the single stage everyone records once."""
    return await db.scalar(
        select(func.count())
        .select_from(OnboardingVisit)
        .where(OnboardingVisit.flow == flow)
        .where(OnboardingVisit.step == "relationship")
    ) or 0


@router.get("/onboarding_visit_stats", response_model=OnboardingVisitStats)
async def onboarding_visit_stats(
    db: AsyncSession = Depends(get_session),
) -> OnboardingVisitStats:
    """Funnel totals plus every row for per-stage breakdowns.

    Ported from .../75_onboarding_visit_stats.xs. Returns the whole table with no
    date filter, exactly as Xano does — the migration plan flags that as a
    scaling problem to fix after cutover, not during the port.
    """
    rows = (await db.execute(
        select(OnboardingVisit).order_by(OnboardingVisit.step_index.asc()))).scalars().all()
    return OnboardingVisitStats(
        child_users=await _count_flow(db, "child"),
        parent_users=await _count_flow(db, "parent"),
        rows=rows,
    )


@router.post("/track_onboarding_visit", response_model=TrackVisitResponse)
async def track_onboarding_visit(
    body: TrackVisitIn,
    db: AsyncSession = Depends(get_session),
) -> TrackVisitResponse:
    """Record that a visitor reached one stage of /signup-flow.

    Ported from .../74_track_onboarding_visit.xs. Stages are recorded on
    *arrival*, so the stage someone abandoned is the last one stored.

    One deliberate improvement inside identical behaviour: Xano checks for an
    existing row and then inserts, which can double-write under a race. Here the
    insert is attempted and a unique-violation is caught instead. The unique
    index on (session_id, flow, step) was always the real guarantee; this just
    stops relying on the check winning.
    """
    flow = body.flow.strip()
    if not flow:
        # A session can hold both flows if the visitor went back and switched,
        # so the most recent row is the best available answer.
        last = (await db.execute(
            select(OnboardingVisit)
            .where(OnboardingVisit.session_id == body.session_id)
            .order_by(OnboardingVisit.created_at.desc())
            .limit(1))).scalar_one_or_none()
        if last is not None:
            flow = last.flow

    if not flow:
        raise XanoError("standard",
                        "Unable to determine the onboarding flow for this session")

    visit = OnboardingVisit(session_id=body.session_id.strip(), flow=flow,
                            step=body.step.strip(), step_index=body.step_index,
                            created_at=datetime.now(UTC))
    try:
        db.add(visit)
        await db.commit()
        counted = True
    except IntegrityError:
        await db.rollback()
        counted = False

    return TrackVisitResponse(counted=counted, flow=flow)
