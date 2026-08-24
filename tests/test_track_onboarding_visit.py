"""POST /track_onboarding_visit — Xano `scripters` 74.

The dedupe rule is the whole point: one row per browser per flow per stage, so a
stage's row count is already a count of people. A duplicate row would silently
inflate the funnel.
"""
from sqlmodel import select

from app.models import OnboardingVisit


async def track(client, **body):
    return await client.post("/track_onboarding_visit",
                             json={"session_id": "sess-1", "step": "names",
                                   "step_index": 3, **body})


async def test_records_a_new_stage(client, session):
    r = await track(client, flow="child")
    assert r.status_code == 200
    assert r.json() == {"counted": True, "flow": "child"}

    rows = (await session.execute(select(OnboardingVisit))).scalars().all()
    assert len(rows) == 1
    assert rows[0].step == "names"


async def test_the_same_stage_twice_is_counted_once(client, session):
    await track(client, flow="child")
    r = await track(client, flow="child")

    assert r.json() == {"counted": False, "flow": "child"}
    rows = (await session.execute(select(OnboardingVisit))).scalars().all()
    assert len(rows) == 1


async def test_the_same_stage_in_the_other_flow_is_a_separate_row(client, session):
    """A visitor who goes back and switches is in both funnels."""
    await track(client, flow="child")
    r = await track(client, flow="parent")

    assert r.json()["counted"] is True
    rows = (await session.execute(select(OnboardingVisit))).scalars().all()
    assert len(rows) == 2


async def test_a_missing_flow_is_inferred_from_the_session(client, session):
    """After the Stripe round-trip the browser has forgotten which funnel it was
    in, so the flow comes from this session's most recent row."""
    await track(client, flow="parent", step="relationship", step_index=0)

    r = await track(client, step="afterPurchase", step_index=16)
    assert r.json() == {"counted": True, "flow": "parent"}


async def test_a_missing_flow_with_no_history_is_refused(client, session):
    r = await track(client, step="afterPurchase", step_index=16)
    assert r.status_code == 500
    assert r.json()["message"] == "Unable to determine the onboarding flow for this session"
    assert (await session.execute(select(OnboardingVisit))).scalars().all() == []


async def test_stats_count_people_not_rows_after_a_full_walk(client, session):
    """End to end against the endpoint that reads this table."""
    for i, step in enumerate(["relationship", "names", "birthday"]):
        await track(client, flow="child", step=step, step_index=i)
    await client.post("/track_onboarding_visit",
                      json={"session_id": "sess-2", "flow": "child",
                            "step": "relationship", "step_index": 0})

    stats = (await client.get("/onboarding_visit_stats")).json()
    assert stats["child_users"] == 2      # 4 rows, 2 people
    assert len(stats["rows"]) == 4
