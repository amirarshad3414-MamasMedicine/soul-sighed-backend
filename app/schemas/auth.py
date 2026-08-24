"""Request and response shapes for the auth endpoints."""
from pydantic import BaseModel, field_validator

from app.schemas.base import XanoSchema


def _lower_trim(value: str | None) -> str | None:
    return value.strip().lower() if isinstance(value, str) else value


class LoginIn(BaseModel):
    """Both fields are optional in Xano (`email email?`, `text password?`).

    Reproduced rather than tightened: a request missing them must fail with
    "Invalid Credentials.", not with an input error.
    """

    email: str | None = None
    password: str | None = None

    _normalise_email = field_validator("email", mode="before")(_lower_trim)


class SignupIn(BaseModel):
    name: str | None = None
    email: str | None = None
    password: str | None = None

    _normalise_email = field_validator("email", mode="before")(_lower_trim)


class PasswordlessIn(BaseModel):
    name: str | None = None
    email: str | None = None

    _normalise_email = field_validator("email", mode="before")(_lower_trim)


class TokenResponse(XanoSchema):
    authToken: str  # noqa: N815 — the frontend reads this exact key


class PasswordlessResponse(TokenResponse):
    message: str
