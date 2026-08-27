"""Xano-compatible error responses.

FastAPI's default error body is `{"detail": "..."}`. The frontend reads
`data?.message` (devlinkModified/env.js), so a default body turns every error in
the UI into "Request failed". Everything here exists to keep that from happening.

Xano's `precondition` takes an error_type from a fixed set — standard, notfound,
accessdenied, toomanyrequests, unauthorized, badrequest, inputerror — which map
to the statuses below.

TODO(parity): the `code` strings follow Xano's documented convention but have not
been confirmed against a live error response. Confirming that needs a real call
to Xano, which is gated on approval (see the migration plan, Phase 8). `message`
is certain — the frontend depends on it.
"""
import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings

ERROR_TYPES: dict[str, tuple[int, str]] = {
    "standard":        (status.HTTP_500_INTERNAL_SERVER_ERROR, "ERROR_CODE_STANDARD"),
    "notfound":        (status.HTTP_404_NOT_FOUND,             "ERROR_CODE_NOT_FOUND"),
    "accessdenied":    (status.HTTP_403_FORBIDDEN,             "ERROR_CODE_ACCESS_DENIED"),
    "toomanyrequests": (status.HTTP_429_TOO_MANY_REQUESTS,     "ERROR_CODE_TOO_MANY_REQUESTS"),
    "unauthorized":    (status.HTTP_401_UNAUTHORIZED,          "ERROR_CODE_UNAUTHORIZED"),
    "badrequest":      (status.HTTP_400_BAD_REQUEST,           "ERROR_CODE_BAD_REQUEST"),
    "inputerror":      (status.HTTP_400_BAD_REQUEST,           "ERROR_CODE_INPUT_ERROR"),
    # A precondition with NO error_type. Xano throws a fatal error, and the
    # captured response is HTTP 500 with this code — measured against live Xano
    # for auth/login's "Invalid Credentials.", 2026-08-25 (parity-question #1).
    "fatal":           (status.HTTP_500_INTERNAL_SERVER_ERROR, "ERROR_FATAL"),
    # NOT from Xano — a deliberate cutover signal. A migrated account still holds
    # its peppered Xano hash, which the port cannot verify, so login redirects the
    # user to password reset instead of failing. See auth.py auth_login.
    "passwordreset":   (status.HTTP_409_CONFLICT,               "PASSWORD_RESET_REQUIRED"),
}


class XanoError(HTTPException):
    """The equivalent of a XanoScript `precondition` failing.

    `payload` defaults to "" — not None — because Xano's error envelope carries
    an empty string there, confirmed across every captured error body (auth/login,
    signup-duplicate, verify_otp) on 2026-08-25. A precondition that sets a
    payload passes it through.
    """

    def __init__(self, error_type: str, message: str, payload: object = ""):
        if error_type not in ERROR_TYPES:
            raise ValueError(f"unknown Xano error_type: {error_type!r}")
        code_status, code = ERROR_TYPES[error_type]
        super().__init__(status_code=code_status, detail=message)
        self.code = code
        self.message = message
        self.payload = payload

    def body(self) -> dict:
        return {"code": self.code, "message": self.message, "payload": self.payload}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(XanoError)
    async def _xano(_: Request, exc: XanoError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.body())

    @app.exception_handler(HTTPException)
    async def _http(_: Request, exc: HTTPException) -> JSONResponse:
        """Anything raised as a plain HTTPException still gets a `message` key."""
        code = next((c for s, c in ERROR_TYPES.values() if s == exc.status_code),
                    "ERROR_CODE_STANDARD")
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message": str(exc.detail), "payload": ""},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Xano rejects bad input with an input error, not FastAPI's 422."""
        if settings.debug:
            # The frontend surfaces only `message`, so the failing field is
            # invisible in the browser. Log it while debugging locally.
            logging.getLogger("uvicorn.error").warning(
                "VALIDATION FAILED %s %s -> %s",
                request.method, request.url.path, exc.errors())
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"code": "ERROR_CODE_INPUT_ERROR",
                     "message": "Input validation failed",
                     "payload": exc.errors()},
        )
