"""Response shapes for the onboarding funnel."""
from app.schemas.base import EpochMillis, XanoSchema


class OnboardingVisitOut(XanoSchema):
    id: int
    created_at: EpochMillis
    session_id: str
    flow: str
    step: str
    step_index: int


class OnboardingVisitStats(XanoSchema):
    """Counts are of *people*, not rows.

    Every visitor records the "relationship" stage exactly once per flow, so
    counting that stage counts people. Counting all rows would multiply each
    person by the number of stages they reached.
    """

    child_users: int
    parent_users: int
    rows: list[OnboardingVisitOut]


class TrackVisitIn(XanoSchema):
    """`flow` may legitimately be absent.

    After the Stripe round-trip the page reloads and the browser no longer knows
    which funnel it was in, so the endpoint infers it from this session's earlier
    rows. An omitted optional text input arrives as "" in Xano, so "" is the
    default here rather than None.
    """

    session_id: str
    step: str
    step_index: int
    flow: str = ""


class TrackVisitResponse(XanoSchema):
    counted: bool
    flow: str
