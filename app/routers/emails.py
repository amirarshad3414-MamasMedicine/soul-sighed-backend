"""Email queue endpoints, ported from the Xano `scripters` API group."""
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.errors import XanoError
from app.database import get_session
from app.models import EmailMessage
from app.schemas.email import DeliverEmailIn, EmailOut, ScheduleEmailIn

router = APIRouter(tags=["email"])


@router.get("/get_pending_emails", response_model=list[EmailOut])
async def get_pending_emails(
    current_time: int = Query(..., description="Epoch milliseconds, as the cron sends it"),
    db: AsyncSession = Depends(get_session),
) -> list[EmailMessage]:
    """Undelivered mail due on or before `current_time`, oldest first.

    Ported from .../68_get_pending_emails.xs. Unauthenticated in Xano and left
    unauthenticated here under the auth-parity rule — the Vercel cron in the
    frontend repo calls it every five minutes with no credentials.
    """
    due = datetime.fromtimestamp(current_time / 1000, tz=UTC)
    rows = await db.execute(
        select(EmailMessage)
        .where(EmailMessage.delivered == False)  # noqa: E712 — SQL, not Python
        .where(EmailMessage.timestamp <= due)
        .order_by(EmailMessage.timestamp.asc())
    )
    return rows.scalars().all()


@router.post("/deliver_email", response_model=EmailOut)
async def deliver_email(
    body: DeliverEmailIn,
    db: AsyncSession = Depends(get_session),
) -> EmailMessage:
    """Mark one queued email as sent.

    Ported from .../67_deliver_email.xs. Note it overwrites `timestamp` with the
    delivery time, replacing the time the mail was scheduled for. Odd, but that
    is what the queue does today, and get_pending_emails filters on the same
    column — so a delivered row can never come back.
    """
    email = (await db.execute(
        select(EmailMessage).where(EmailMessage.id == body.email_id))).scalar_one_or_none()
    if email is None:
        raise XanoError("inputerror", "Email record not found.")

    email.delivered = True
    email.timestamp = datetime.now(UTC)
    db.add(email)
    await db.commit()
    await db.refresh(email)
    return email


@router.post("/scheduled_email", response_model=EmailOut)
async def scheduled_email(
    body: ScheduleEmailIn,
    db: AsyncSession = Depends(get_session),
) -> EmailMessage:
    """Queue an email for later delivery.

    Ported from .../66_scheduled_email.xs. Unauthenticated in Xano, so anyone
    who knows the URL can add to the send queue — kept as-is under the
    auth-parity rule and recorded in triage.
    """
    email = EmailMessage(email=body.email, subject=body.subject.strip(),
                         html_content=body.body.strip(),
                         timestamp=body.scheduled_time, delivered=False)
    db.add(email)
    await db.commit()
    await db.refresh(email)
    return email
