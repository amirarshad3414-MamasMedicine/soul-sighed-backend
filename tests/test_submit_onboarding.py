"""POST /submit_onboarding — Xano `scripters` 47, the largest endpoint.

Most of the value is in build_payload: the swap it performs when the reader is
the adult child rather than the parent. That is a pure function, so it is tested
directly, without a database or a network.
"""
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlmodel import select

from app.models import Child, Insight, Purchase
from app.schemas.checkout import JOURNEY_ID
from app.services import google_places, insights, notifications
from tests.conftest import auth_headers

PARENT_PLACE, CHILD_PLACE = "ChIJparent", "ChIJchild"
PARENT_COORDS = {"lat": 31.5, "lon": 74.3}
CHILD_COORDS = {"lat": 24.8, "lon": 67.0}

PAYLOAD = {
    "username": "Ayesha", "childname": "Yusuf",
    "user_dob": "1990-06-15T00:00:00", "child_dob": "2019-04-11T00:00:00",
    "user_birth_place_id": PARENT_PLACE, "child_birth_place_id": CHILD_PLACE,
    "raw_user_message": "he keeps testing me", "climate": "warm",
    "activation": "quick", "closeness": "close", "posture": "open",
    "parentPronouns": "she/her", "childPronouns": "he/him",
    "user_time_of_birth": "1990-06-15T14:30:00",
    "child_time_of_birth": "2019-04-11T08:05:00",
}


def google_payload(coords):
    return {"result": {"geometry": {"location": {"lat": coords["lat"], "lng": coords["lon"]}}}}


@pytest.fixture
def externals(monkeypatch):
    state = {"geo": {PARENT_PLACE: google_payload(PARENT_COORDS),
                     CHILD_PLACE: google_payload(CHILD_COORDS)},
             "provider": {"status": 200, "body": {"deep": "the long text",
                                                  "summary": "the summary",
                                                  "teaser": "the teaser"}},
             "attempts": 0, "insight_emails": []}

    async def fake_geo(place_id):
        result = state["geo"].get(place_id)
        if result is None:
            raise RuntimeError("ZERO_RESULTS")
        return result

    class FakeResponse:
        def __init__(self, status, body):
            self.status_code, self._body = status, body

        def json(self):
            return self._body

    async def fake_generate(payload):
        state["attempts"] += 1
        spec = state["provider"]
        if isinstance(spec, Exception):
            raise spec
        return FakeResponse(spec["status"], spec["body"])

    async def fake_send_insight(child_name, parent_name, email, insight):
        state["insight_emails"].append((child_name, parent_name, email))

    monkeypatch.setattr(google_places, "details_for_geocoding", fake_geo)
    monkeypatch.setattr(insights, "generate", fake_generate)
    monkeypatch.setattr(notifications, "send_insight", fake_send_insight)
    return state


async def submit(client, session, user, **body):
    # Ordered deliberately: an unordered LIMIT 1 is not stable here, because
    # updating a row rewrites it at the end of the heap and the next call picks
    # a different child.
    child = (await session.execute(
        select(Child).where(Child.user_id == user.id)
        .order_by(Child.created_at, Child.id))).scalars().first()
    return child, await client.post("/submit_onboarding", headers=auth_headers(user), json={
        "child_id": str(child.id), "journey_id": JOURNEY_ID,
        "onboarding_payload": PAYLOAD, **body})


# --- the payload builder, tested directly ------------------------------------

def test_parent_reading_puts_the_parent_first():
    built = insights.build_payload(
        {"username": "Ayesha", "childname": "Yusuf",
         "user_dob": datetime(1990, 6, 15), "child_dob": datetime(2019, 4, 11),
         "parentPronouns": "she/her", "childPronouns": "he/him"},
        is_child=False, parent_coords=PARENT_COORDS, child_coords=CHILD_COORDS)

    assert built["parentName"] == "Ayesha"
    assert built["childName"] == "Yusuf"
    assert built["p1Lat"] == PARENT_COORDS["lat"]
    assert built["p2Lat"] == CHILD_COORDS["lat"]
    assert built["relationship_focus"] == "child"
    assert built["reader_role"] == "parent"


def test_child_reading_swaps_everyone_over():
    """When the reader is the adult child, person_1 becomes the child and every
    name, pronoun, birthday and coordinate trades places."""
    built = insights.build_payload(
        {"username": "Ayesha", "childname": "Yusuf",
         "user_dob": datetime(1990, 6, 15), "child_dob": datetime(2019, 4, 11),
         "parentPronouns": "she/her", "childPronouns": "he/him"},
        is_child=True, parent_coords=PARENT_COORDS, child_coords=CHILD_COORDS)

    assert built["parentName"] == "Yusuf"
    assert built["childName"] == "Ayesha"
    assert built["childPronouns"] == "she/her"
    assert built["parentPronouns"] == "he/him"
    assert built["p1Lat"] == CHILD_COORDS["lat"]
    assert built["p2Lat"] == PARENT_COORDS["lat"]
    assert built["relationship_focus"] == "parent"
    assert built["reader_role"] == "adult_child"


def test_pronouns_fall_back_to_she_her():
    built = insights.build_payload({}, is_child=False,
                                   parent_coords=PARENT_COORDS, child_coords=CHILD_COORDS)
    assert built["childPronouns"] == "she/her"
    assert built["parentPronouns"] == "she/her"


def test_birth_times_are_dropped():
    """Documents a real defect rather than fixing it silently.

    The endpoint accepts a birth time for both people and never uses it — every
    one of the 331 live payloads carries T00:00. For an astrology product that
    is significant, since birth time fixes the ascendant. Triage decision.
    """
    built = insights.build_payload(
        {"user_dob": datetime(1990, 6, 15), "child_dob": datetime(2019, 4, 11),
         "user_time_of_birth": datetime(1990, 6, 15, 14, 30),
         "child_time_of_birth": datetime(2019, 4, 11, 8, 5)},
        is_child=False, parent_coords=PARENT_COORDS, child_coords=CHILD_COORDS)

    assert built["p1Birthday"] == "1990-06-15T00:00"
    assert built["p2Birthday"] == "2019-04-11T00:00"
    assert built["person_1"]["birthday"].endswith("T00:00")


def test_omitted_text_fields_are_sent_as_empty_strings_never_null():
    """The provider type-checks, and null is not a string.

    Caught by running a real onboarding end to end on 2026-08-25: the provider
    answered `{"error": "Field 'rawUserMessage' must be a string", "status":
    400}`, the retry loop burned all five attempts, and the insight was marked
    `failed`. Anyone skipping the optional free-text question would have got no
    reading at all.

    Xano sends "" here, not null. Proven against 321 live insights_api_payload
    rows: rawUserMessage is a string 295 times and "" 26 times, and every
    tone_inputs value is a string or "" — neither is ever null.
    """
    built = insights.build_payload({}, is_child=False,
                                   parent_coords=PARENT_COORDS,
                                   child_coords=CHILD_COORDS)

    assert built["rawUserMessage"] == ""
    assert built["parentName"] == ""
    assert built["childName"] == ""
    assert built["tone_inputs"] == {"q1_climate": "", "q2_activation": "",
                                    "q3_closeness": "", "q4_posture": ""}
    for key, value in built["tone_inputs"].items():
        assert isinstance(value, str), key


def test_supplied_text_fields_are_passed_through_unchanged():
    built = insights.build_payload(
        {"username": "Ama", "childname": "Kofi", "raw_user_message": "hello",
         "climate": "warm", "activation": "sometimes",
         "closeness": "close", "posture": "open"},
        is_child=False, parent_coords=PARENT_COORDS, child_coords=CHILD_COORDS)

    assert built["rawUserMessage"] == "hello"
    assert built["parentName"] == "Ama"
    assert built["childName"] == "Kofi"
    assert built["tone_inputs"]["q1_climate"] == "warm"
    assert built["tone_inputs"]["q4_posture"] == "open"


# --- the endpoint ------------------------------------------------------------

async def test_a_successful_generation(client, session, user, externals):
    _, r = await submit(client, session, user)
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "Insight created successfully."
    assert body["status"] == "ready"
    assert body["teaser"] == "the teaser"
    assert externals["attempts"] == 1


async def test_the_insight_row_is_filled_in(client, session, user, externals):
    child, r = await submit(client, session, user)
    insight = (await session.execute(
        select(Insight).where(Insight.child_id == child.id))).scalars().first()
    await session.refresh(insight)
    assert insight.status == "ready"
    assert insight.deep_text == "the long text"
    assert insight.summary_text == "the summary"


async def test_the_child_record_is_updated_with_name_and_coordinates(
        client, session, user, externals):
    child, _ = await submit(client, session, user)
    await session.refresh(child)
    assert child.name == "Yusuf"
    assert child.lat == CHILD_COORDS["lat"]
    assert child.default_child is False


async def test_the_provider_is_retried_five_times_then_marked_failed(
        client, session, user, externals):
    externals["provider"] = {"status": 500, "body": {}}

    child, r = await submit(client, session, user)
    assert externals["attempts"] == 5
    assert r.json()["status"] == "failed"

    insight = (await session.execute(
        select(Insight).where(Insight.child_id == child.id))).scalars().first()
    await session.refresh(insight)
    assert insight.status == "failed"
    assert insight.last_error == "Attempt 5 failed: External API returned status 500"


async def test_an_unresolvable_birthplace_returns_200_with_an_error_body(
        client, session, user, externals):
    """Xano uses `return` inside the catch, so this is a 200 — the frontend has
    to read the body, not the status."""
    externals["geo"] = {}
    before = len((await session.execute(select(Insight))).scalars().all())

    _, r = await submit(client, session, user)
    assert r.status_code == 200
    assert r.json()["error"] == "PLACE_NOT_RESOLVED"

    after = len((await session.execute(select(Insight))).scalars().all())
    assert after == before, "no insight row should be created when a place fails"


async def test_the_follow_up_email_only_fires_when_a_purchase_exists(
        client, session, user, externals):
    child, _ = await submit(client, session, user)
    assert externals["insight_emails"] == []

    session.add(Purchase(user_id=user.id, child_id=child.id,
                         journey_id=UUID(JOURNEY_ID), purchase_source="stripe"))
    await session.commit()

    await submit(client, session, user)
    assert externals["insight_emails"] == [("Yusuf", "Ayesha", user.email)]


async def test_a_reading_is_generated_without_any_purchase(client, session, user, externals):
    """The purchase precondition is commented out in Xano, so nothing stops an
    unpaid generation. Reproduced, and recorded in triage."""
    _, r = await submit(client, session, user)
    assert r.json()["status"] == "ready"


async def test_requires_authentication(client, externals):
    r = await client.post("/submit_onboarding", json={
        "child_id": "00000000-0000-0000-0000-000000000000",
        "journey_id": JOURNEY_ID, "onboarding_payload": PAYLOAD})
    assert r.status_code == 401
