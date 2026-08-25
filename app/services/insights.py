"""Insight generation, ported from the Xano `submit_onboarding` stack.

The payload builder is a pure function on purpose. Everything interesting in
that 501-line stack is the swap it performs when the reader is the *child*
rather than the parent — person_1 and person_2 trade places, and so do the
names, pronouns, birthdays and coordinates. Keeping it pure means that logic is
testable without a database, a network, or a running app.
"""
from datetime import datetime
from typing import Any

import httpx

from app.config import settings

DEFAULT_PRONOUNS = "she/her"

# Xano: format_timestamp:"Y-m-d\TH:i". Note the time component is always 00:00,
# because only the date inputs are used — user_time_of_birth and
# child_time_of_birth are declared and never read. All 331 live payloads carry
# T00:00 for both people. See the triage note in the migration plan.
BIRTHDAY_FORMAT = "%Y-%m-%dT%H:%M"


def _format_birthday(value: datetime | None) -> str | None:
    return value.strftime(BIRTHDAY_FORMAT) if value else None


def _text(value: Any) -> str:
    """Coerce an absent optional text field to "" rather than None.

    Xano's `text foo?` inputs arrive as "" when the caller omits them, never as
    null, and the payload is passed straight through to the provider. Proven
    against 321 live `insights_api_payload` rows: `rawUserMessage` is a string
    295 times and "" 26 times, and every tone_inputs value is str or "" — no
    column is ever null.

    This is not cosmetic. The provider validates types and answers
    `{"error": "Field 'rawUserMessage' must be a string", "status": 400}` to a
    null, which the retry loop then burns all five attempts on before marking
    the insight `failed`. Sending None here means no reading is ever generated
    for anyone who skips the free-text question.
    """
    return value if isinstance(value, str) else ""


def build_payload(payload: dict[str, Any], *, is_child: bool,
                  parent_coords: dict[str, float], child_coords: dict[str, float]
                  ) -> dict[str, Any]:
    """Assemble the body sent to the insight provider.

    `is_child` means the person asking is the adult child and the reading is
    about their parent. Everywhere below, the "first person" is whoever the
    reading is *for*.
    """
    def pick(when_child: Any, when_parent: Any) -> Any:
        return when_child if is_child else when_parent

    username = payload.get("username")
    childname = payload.get("childname")
    parent_pronouns = payload.get("parentPronouns") or DEFAULT_PRONOUNS
    child_pronouns = payload.get("childPronouns") or DEFAULT_PRONOUNS

    first = pick(child_coords, parent_coords)
    second = pick(parent_coords, child_coords)
    first_birthday = _format_birthday(pick(payload.get("child_dob"), payload.get("user_dob")))
    second_birthday = _format_birthday(pick(payload.get("user_dob"), payload.get("child_dob")))

    return {
        "parentName": _text(pick(childname, username)),
        "childName": _text(pick(username, childname)),
        "childPronouns": pick(parent_pronouns, child_pronouns),
        "parentPronouns": pick(child_pronouns, parent_pronouns),
        "rawUserMessage": _text(payload.get("raw_user_message")),
        "p1Lat": first.get("lat"),
        "p1Lon": first.get("lon"),
        "p2Lat": second.get("lat"),
        "p2Lon": second.get("lon"),
        "p1Birthday": first_birthday,
        "p2Birthday": second_birthday,
        "relationship_focus": pick("parent", "child"),
        "reader_role": pick("adult_child", "parent"),
        "person_1": {"birthday": first_birthday, "lat": first.get("lat"), "lon": first.get("lon")},
        "person_2": {"birthday": second_birthday, "lat": second.get("lat"), "lon": second.get("lon")},
        "tone_inputs": {
            "q1_climate": _text(payload.get("climate")),
            "q2_activation": _text(payload.get("activation")),
            "q3_closeness": _text(payload.get("closeness")),
            "q4_posture": _text(payload.get("posture")),
        },
    }


async def generate(payload: dict[str, Any]) -> httpx.Response:
    """One call to the provider. Raises on transport failure; the caller retries."""
    async with httpx.AsyncClient(timeout=settings.insight_timeout_seconds) as client:
        return await client.post(settings.external_insight_api_url, json=payload,
                                 headers={"Content-Type": "application/json"})
