"""Response shapes for the Google Places passthrough endpoints."""
from app.schemas.base import XanoSchema


class Prediction(XanoSchema):
    place_id: str
    description: str


class AutocompleteResponse(XanoSchema):
    predictions: list[Prediction]


class PlaceDetails(XanoSchema):
    place_id: str
    formatted_address: str | None
    lat: float
    lon: float
    country_code: str | None
