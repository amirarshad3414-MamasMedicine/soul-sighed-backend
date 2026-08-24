"""Endpoints that exist in Xano but do nothing."""
from fastapi import APIRouter

router = APIRouter(tags=["misc"])


@router.post("/Profile")
async def profile() -> None:
    """An empty stub.

    Ported from .../69_Profile.xs, which is genuinely empty — no inputs, no
    stack, `response = null`. Reproduced so the route still exists and answers
    the same way; a triage candidate for deletion once something confirms
    nothing calls it.
    """
    return None
