"""Request and response shapes for the OTP and password-reset endpoints."""
from pydantic import BaseModel, field_validator

from app.schemas.base import XanoSchema


class StoreOtpIn(BaseModel):
    email: str
    otp: str
    expiresIn: int  # noqa: N815 — the frontend sends this exact key


class VerifyOtpIn(BaseModel):
    email: str
    otp: str


class UpdatePasswordIn(BaseModel):
    email: str
    newPassword: str  # noqa: N815 — the frontend sends this exact key

    @field_validator("email", mode="before")
    @classmethod
    def _lower_trim(cls, value: str | None) -> str | None:
        return value.strip().lower() if isinstance(value, str) else value


class MessageResponse(XanoSchema):
    message: str


class StoreOtpResponse(MessageResponse):
    success: bool
