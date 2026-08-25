"""Google Places passthrough endpoints — Xano `scripters` 49 and 50.

Google is never called for real: `app.services.google_places` is the single seam
and both tests replace it. That keeps the suite offline and deterministic, and
it means a change to the response shaping is caught rather than masked by a
network failure.
"""
import pytest

from app.services import google_places

AUTOCOMPLETE_OK = {
    "status": "OK",
    "predictions": [
        {"place_id": f"place-{i}", "description": f"Lahore {i}", "extra": "ignored"}
        for i in range(8)  # more than the limit of 5
    ],
}

DETAILS_OK = {
    "status": "OK",
    "result": {
        "formatted_address": "Lahore, Punjab, Pakistan",
        "geometry": {"location": {"lat": 31.5203696, "lng": 74.3587473}},
        "address_components": [
            {"short_name": "Lahore", "types": ["locality"]},
            {"short_name": "PK", "types": ["country", "political"]},
        ],
    },
}


@pytest.fixture
def google(monkeypatch):
    calls = {}

    async def fake_autocomplete(query):
        calls["autocomplete"] = query
        return calls.get("autocomplete_response", AUTOCOMPLETE_OK)

    async def fake_details(place_id):
        calls["details"] = place_id
        return calls.get("details_response", DETAILS_OK)

    monkeypatch.setattr(google_places, "autocomplete", fake_autocomplete)
    monkeypatch.setattr(google_places, "details", fake_details)
    return calls


async def test_autocomplete_returns_place_id_and_description_only(client, google):
    body = (await client.get("/places_autocomplete?q=lahore")).json()
    assert set(body["predictions"][0]) == {"place_id", "description"}
    assert body["predictions"][0]["description"] == "Lahore 0"


async def test_autocomplete_caps_at_five(client, google):
    """Xano slices to 5 even though Google returns more."""
    body = (await client.get("/places_autocomplete?q=lahore")).json()
    assert len(body["predictions"]) == 5


async def test_autocomplete_rejects_short_queries(client, google):
    r = await client.get("/places_autocomplete?q=la")
    assert r.status_code == 400
    # The input-filter envelope, measured against live Xano 2026-08-25:
    assert r.json() == {
        "code": "ERROR_CODE_INPUT_ERROR",
        "message": "Input does not meet minimum length requirement of 3 characters",
        "payload": {"param": "q"}}


async def test_autocomplete_trims_before_measuring(client, google):
    """`filters=trim|min:3` runs before the length check, so spaces don't count."""
    r = await client.get("/places_autocomplete?q=%20%20la%20%20")
    assert r.status_code == 400


async def test_autocomplete_surfaces_request_denied(client, google):
    google["autocomplete_response"] = {"status": "REQUEST_DENIED",
                                       "error_message": "The provided API key is invalid."}
    r = await client.get("/places_autocomplete?q=lahore")
    assert r.status_code == 500
    assert r.json()["message"] == "The provided API key is invalid."


async def test_details_extracts_coordinates_and_country(client, google):
    body = (await client.get("/places_details?place_id=abc123")).json()
    assert body == {
        "place_id": "abc123",
        "formatted_address": "Lahore, Punjab, Pakistan",
        "lat": pytest.approx(31.5203696),
        "lon": pytest.approx(74.3587473),
        "country_code": "PK",
    }


async def test_details_reports_a_google_failure(client, google):
    google["details_response"] = {"status": "ZERO_RESULTS", "error_message": None}
    r = await client.get("/places_details?place_id=abc123")
    assert r.status_code == 500
    assert "ZERO_RESULTS" in r.json()["message"]


async def test_details_handles_a_place_with_no_country_component(client, google):
    google["details_response"] = {
        "status": "OK",
        "result": {"formatted_address": "Somewhere",
                   "geometry": {"location": {"lat": 0, "lng": 0}},
                   "address_components": []},
    }
    body = (await client.get("/places_details?place_id=abc123")).json()
    assert body["country_code"] is None


async def test_both_endpoints_are_unauthenticated(client, google):
    """Matches Xano; the signup form calls these before anyone has logged in."""
    assert (await client.get("/places_autocomplete?q=lahore")).status_code == 200
    assert (await client.get("/places_details?place_id=abc123")).status_code == 200
