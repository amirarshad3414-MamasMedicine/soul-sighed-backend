"""Google Places calls, extracted from the Xano stacks that made them.

Kept in one place so the routers stay thin and the tests have a single seam to
replace. Two different API keys are used on purpose — see app/config.py.
"""
from typing import Any

import httpx

from app.config import settings

AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

TIMEOUT = 10.0


async def autocomplete(query: str) -> dict[str, Any]:
    """Raw Google autocomplete payload for `query`."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(AUTOCOMPLETE_URL, params={
            "input": query,
            "key": settings.google_geocoding_api_key,
        })
        return response.json()


async def details(place_id: str) -> dict[str, Any]:
    """Raw Google place-details payload, restricted to the fields Xano asked for."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(DETAILS_URL, params={
            "place_id": place_id,
            "key": settings.google_places_autocomplete_api_key,
            "fields": "formatted_address,geometry,address_components",
        })
        return response.json()


async def coordinates_for(place_id: str) -> tuple[float | None, float | None]:
    """Latitude and longitude for a place, or (None, None) if anything fails.

    add_children swallows every failure: a REQUEST_DENIED or a missing result
    leaves both null and the child is still saved. Reproduced deliberately —
    changing it belongs in its own commit, after cutover.
    """
    try:
        payload = await details_for_geocoding(place_id)
        location = payload["result"]["geometry"]["location"]
        return location["lat"], location["lng"]
    except Exception:
        return None, None


async def details_for_geocoding(place_id: str) -> dict[str, Any]:
    """The lookup add_children makes — note it uses the *geocoding* key, while
    places_details uses a different one. Preserved rather than unified."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(DETAILS_URL, params={
            "place_id": place_id,
            "key": settings.google_geocoding_api_key,
        })
        return response.json()
