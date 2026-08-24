"""GET /onboarding_visit_stats — ported from Xano `scripters` endpoint 75.

The counting rule is the point of these tests: one person produces up to 17 rows,
so counts come from the single stage everyone records exactly once per flow.
"""
from datetime import datetime, timezone

from app.models import OnboardingVisit

AT = datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc)

STAGES = ["relationship", "childname", "birthday", "birthplace"]


async def _seed_funnel(session):
    rows = []
    # two child-flow visitors: one reached stage 4, one stopped at stage 1
    for step_index, step in enumerate(STAGES):
        rows.append(OnboardingVisit(session_id="sess-a", flow="child", step=step,
                                    step_index=step_index, created_at=AT))
    rows.append(OnboardingVisit(session_id="sess-b", flow="child", step="relationship",
                                step_index=0, created_at=AT))
    # one parent-flow visitor
    rows.append(OnboardingVisit(session_id="sess-c", flow="parent", step="relationship",
                                step_index=0, created_at=AT))
    session.add_all(rows)
    await session.commit()


async def test_counts_people_not_rows(client, session):
    await _seed_funnel(session)
    body = (await client.get("/onboarding_visit_stats")).json()
    assert body["child_users"] == 2   # 5 child rows, but only 2 people
    assert body["parent_users"] == 1
    assert len(body["rows"]) == 6


async def test_rows_are_ordered_by_stage(client, session):
    await _seed_funnel(session)
    body = (await client.get("/onboarding_visit_stats")).json()
    indexes = [r["step_index"] for r in body["rows"]]
    assert indexes == sorted(indexes)


async def test_empty_table_returns_zeroes_not_an_error(client):
    body = (await client.get("/onboarding_visit_stats")).json()
    assert body == {"child_users": 0, "parent_users": 0, "rows": []}
