"""Test fixtures: a real Postgres, wiped between tests.

Tests run against the same Docker Postgres as development. Every table is
truncated before each test, so a test never sees another test's rows.
"""
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.database import get_session
from app.main import app
from app.models import *  # noqa: F401,F403 — registers tables on the metadata

TABLES = ["children", "insights", "journey", "purchases", "email",
          "onboarding_visit", "user_01", "users"]


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(settings.database_url, poolclass=None)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s


@pytest_asyncio.fixture
async def client(session):
    app.dependency_overrides[get_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


# --- shared seed helpers -----------------------------------------------------

SEED_AT = datetime(2026, 8, 5, 9, 31, tzinfo=timezone.utc)

# The single journey the product currently sells; hardcoded in checkout.xs and
# in the frontend at app/onboardingMain/page.jsx:267.
JOURNEY_ID = UUID("fff90478-924f-4ec7-95a1-68b5549a0ec9")


def auth_headers(user) -> dict[str, str]:
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest_asyncio.fixture
async def user(session):
    """A parent with one full child, one bare child, an insight and a purchase."""
    from app.models import Child, Insight, Purchase, User

    parent = User(name="Test Parent", email="parent@example.test",
                  relationship_focus="parent", created_at=SEED_AT)
    session.add(parent)
    await session.flush()

    session.add(Child(
        user_id=parent.id, name="Amina", relationship_focus="child",
        date_of_birth=date(2019, 4, 11), lat=31.5204, lon=74.3587,
        pronoun="she/her", default_child=False, created_at=SEED_AT))
    session.add(Child(user_id=parent.id, name="", relationship_focus="",
                      created_at=SEED_AT))
    # Insights.child_id, journey_id and request_id are NOT NULL in Xano, and
    # Purchases.journey_id likewise — 200 sampled purchase rows carry one.
    session.add(Insight(
        real_user_id=parent.id, child_id=uuid4(), journey_id=JOURNEY_ID,
        request_id=uuid4(), status="ready", teaser_text="hello",
        insights_api_payload={"p1Lat": 31.52}, created_at=SEED_AT))
    session.add(Purchase(
        user_id=parent.id, journey_id=JOURNEY_ID, purchase_source="stripe",
        purchase_reference="cs_test_123", created_at=SEED_AT))
    await session.commit()
    return parent
