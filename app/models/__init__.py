"""Every model must be imported here — Alembic discovers tables through
SQLModel.metadata, and a model that is never imported is never created."""

from app.models.analytics import OnboardingVisit
from app.models.child import Child
from app.models.email import EmailMessage
from app.models.insight import Insight, Journey
from app.models.purchase import Purchase
from app.models.user import LegacyUser, User

__all__ = [
    "Child",
    "EmailMessage",
    "Insight",
    "Journey",
    "LegacyUser",
    "OnboardingVisit",
    "Purchase",
    "User",
]
