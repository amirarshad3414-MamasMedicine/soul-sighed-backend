"""Google Places endpoints, ported from the Xano `scripters` API group."""
from fastapi import APIRouter, Query

from app.core.errors import XanoError
from app.schemas.places import AutocompleteResponse, PlaceDetails, Prediction
from app.services import google_places

router = APIRouter(tags=["places"])

MAX_PREDICTIONS = 5


@router.get("/places_autocomplete", response_model=AutocompleteResponse)
async def places_autocomplete(q: str = Query(...)) -> AutocompleteResponse:
    """Address suggestions for a partial query.

    Ported from .../49_places_autocomplete.xs. Xano applies `trim|min:3` to the
    input. Measured against live Xano 2026-08-25 (parity-question #6): the input
    FILTER rejects a short query before the stack runs — so the stack's own
    length assertion is never reached, and the envelope is exactly this, not the
    stack's wording. `payload` here is an object, not the "" a precondition gives.
    """
    query = q.strip()
    if len(query) < 3:
        raise XanoError(
            "inputerror",
            "Input does not meet minimum length requirement of 3 characters",
            payload={"param": "q"})

    payload = await google_places.autocomplete(query)

    if payload.get("status") == "REQUEST_DENIED":
        raise XanoError("standard", payload.get("error_message") or "REQUEST_DENIED")

    predictions = [
        Prediction(place_id=p.get("place_id"), description=p.get("description"))
        for p in (payload.get("predictions") or [])
    ][:MAX_PREDICTIONS]
    return AutocompleteResponse(predictions=predictions)


@router.get("/places_details", response_model=PlaceDetails)
async def places_details(place_id: str = Query(...)) -> PlaceDetails:
    """Coordinates and country for one place id.

    Ported from .../50_places_details.xs, including the coordinate-range checks,
    which cannot realistically fail on a Google response but are part of the
    contract.
    """
    payload = await google_places.details(place_id)

    if payload.get("status") != "OK":
        raise XanoError(
            "standard",
            f"Failed to fetch place details: {payload.get('status')} - "
            f"{payload.get('error_message')}")

    result = payload.get("result") or {}
    location = (result.get("geometry") or {}).get("location") or {}
    lat, lon = float(location.get("lat", 0)), float(location.get("lng", 0))

    if not -90 <= lat <= 90:
        raise XanoError("inputerror", "Latitude must be between -90 and 90.")
    if not -180 <= lon <= 180:
        raise XanoError("inputerror", "Longitude must be between -180 and 180.")

    country = next((c for c in (result.get("address_components") or [])
                    if "country" in (c.get("types") or [])), None)

    return PlaceDetails(
        place_id=place_id,
        formatted_address=result.get("formatted_address"),
        lat=lat,
        lon=lon,
        country_code=country.get("short_name") if country else None,
    )
