"""Account creation, shared by auth/signup and register_passwordless.

Both endpoints create a user, then diverge only in whether a password is set and
what the response says. The default-child creation and purchase back-linking in
auth/signup live here so the routers stay declarative.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.errors import XanoError
from app.models import Child, Purchase, User


async def refuse_if_email_taken(db: AsyncSession, email: str | None) -> None:
    """Xano: `precondition ($user == null)` with error_type accessdenied."""
    existing = (await db.execute(
        select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        raise XanoError("accessdenied", "This account is already in use.")


async def create_user(db: AsyncSession, *, name: str | None, email: str | None,
                      password_hash: str | None = None) -> User:
    user = User(name=name, email=email, password=password_hash)
    db.add(user)
    await db.flush()
    return user


async def create_default_child(db: AsyncSession, user: User) -> Child:
    """auth/signup adds a nameless placeholder child with default_child = true.

    This is where the empty-name rows in the live `children` table come from —
    the onboarding flow fills them in later.
    """
    child = Child(user_id=user.id, default_child=True)
    db.add(child)
    await db.flush()
    return child


async def claim_purchases_made_before_signup(
    db: AsyncSession, user: User, child: Child, email: str | None) -> int:
    """Attach purchases bought against this email to the new account.

    Someone can pay before they have an account — `checkout` writes a Purchase
    row keyed only by `customer_details.email` in that case. Signing up later
    adopts those rows.
    """
    purchases = (await db.execute(
        select(Purchase).where(Purchase.email == email))).scalars().all()
    for purchase in purchases:
        purchase.user_id = user.id
        purchase.child_id = child.id
        db.add(purchase)
    return len(purchases)
