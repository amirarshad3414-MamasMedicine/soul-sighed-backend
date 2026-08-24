"""GET /get_pending_emails — ported from Xano `scripters` endpoint 68.

Unauthenticated in Xano; the Vercel cron in the frontend repo calls it every five
minutes with no credentials. Kept open under the auth-parity rule.
"""
from datetime import datetime, timezone

from app.models import EmailMessage

BASE = datetime(2026, 8, 5, 9, 0, tzinfo=timezone.utc)


def ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


async def _seed_queue(session):
    from datetime import timedelta
    session.add_all([
        EmailMessage(email="due@example.test", subject="due", html_content="<p>1</p>",
                     delivered=False, timestamp=BASE - timedelta(minutes=10)),
        EmailMessage(email="older@example.test", subject="older", html_content="<p>2</p>",
                     delivered=False, timestamp=BASE - timedelta(hours=2)),
        EmailMessage(email="future@example.test", subject="future", html_content="<p>3</p>",
                     delivered=False, timestamp=BASE + timedelta(hours=1)),
        EmailMessage(email="sent@example.test", subject="sent", html_content="<p>4</p>",
                     delivered=True, timestamp=BASE - timedelta(hours=3)),
    ])
    await session.commit()


async def test_returns_only_undelivered_mail_that_is_due(client, session):
    await _seed_queue(session)
    body = (await client.get(f"/get_pending_emails?current_time={ms(BASE)}")).json()
    assert {e["subject"] for e in body} == {"due", "older"}


async def test_oldest_first(client, session):
    await _seed_queue(session)
    body = (await client.get(f"/get_pending_emails?current_time={ms(BASE)}")).json()
    assert [e["subject"] for e in body] == ["older", "due"]


async def test_timestamps_are_epoch_millis(client, session):
    await _seed_queue(session)
    body = (await client.get(f"/get_pending_emails?current_time={ms(BASE)}")).json()
    assert all(isinstance(e["timestamp"], int) for e in body)
    assert all(isinstance(e["created_at"], int) for e in body)


async def test_no_credentials_required(client, session):
    """Deliberate: matches Xano, and the cron sends no auth header."""
    assert (await client.get(f"/get_pending_emails?current_time={ms(BASE)}")).status_code == 200
