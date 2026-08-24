"""POST /scheduled_email and /deliver_email — Xano `scripters` 66 and 67.

Together with get_pending_emails these three are the whole mail queue: something
schedules, the Vercel cron drains, and delivery marks the row done.
"""
from datetime import UTC, datetime, timedelta

from sqlmodel import select

from app.models import EmailMessage

WHEN = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


async def schedule(client, **body):
    return await client.post("/scheduled_email", json={
        "email": "her@example.test", "subject": "  Your reading  ",
        "body": "  <p>hello</p>  ", "scheduled_time": WHEN.isoformat(), **body})


async def test_scheduling_queues_an_undelivered_row(client, session):
    r = await schedule(client)
    assert r.status_code == 200
    body = r.json()
    assert body["delivered"] is False
    assert body["email"] == "her@example.test"


async def test_subject_and_body_are_trimmed(client, session):
    """Xano applies filters=trim to both."""
    body = (await schedule(client)).json()
    assert body["subject"] == "Your reading"
    assert body["html_content"] == "<p>hello</p>"


async def test_a_scheduled_email_is_not_yet_due(client, session):
    await schedule(client)
    earlier = int((WHEN - timedelta(hours=1)).timestamp() * 1000)
    assert (await client.get(f"/get_pending_emails?current_time={earlier}")).json() == []


async def test_delivering_marks_it_done_and_removes_it_from_the_queue(client, session):
    email_id = (await schedule(client)).json()["id"]
    due = int((WHEN + timedelta(hours=1)).timestamp() * 1000)
    assert len((await client.get(f"/get_pending_emails?current_time={due}")).json()) == 1

    r = await client.post("/deliver_email", json={"email_id": email_id})
    assert r.status_code == 200
    assert r.json()["delivered"] is True

    assert (await client.get(f"/get_pending_emails?current_time={due}")).json() == []


async def test_delivery_overwrites_the_scheduled_time(client, session):
    """Deliberate parity quirk: `timestamp` becomes the delivery time, losing
    the time the mail was scheduled for."""
    email_id = (await schedule(client)).json()["id"]
    before = datetime.now(UTC)

    await client.post("/deliver_email", json={"email_id": email_id})
    row = (await session.execute(
        select(EmailMessage).where(EmailMessage.id == email_id))).scalar_one()
    await session.refresh(row)
    assert row.timestamp >= before


async def test_delivering_an_unknown_id_is_an_input_error(client, session):
    r = await client.post("/deliver_email", json={"email_id": 999999})
    assert r.status_code == 400
    assert r.json()["message"] == "Email record not found."


async def test_profile_is_an_empty_stub(client):
    """Xano's Profile endpoint has no inputs, no stack and returns null."""
    r = await client.post("/Profile")
    assert r.status_code == 200
    assert r.json() is None
