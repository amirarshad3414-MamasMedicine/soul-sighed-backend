"""FastAPI application factory."""
from fastapi import FastAPI

from app.config import settings
from app.core.errors import register_error_handlers
from app.routers import (
    analytics,
    auth,
    checkout,
    children,
    emails,
    misc,
    onboarding,
    places,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Soul Sighted API",
        description="FastAPI port of the Xano `scripters` API group.",
        version="0.1.0",
        debug=settings.debug,
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    register_error_handlers(app)

    # registered as endpoints are ported; xano-export/inventory.csv tracks the 25
    app.include_router(auth.router)
    app.include_router(children.router)
    app.include_router(emails.router)
    app.include_router(analytics.router)
    app.include_router(places.router)
    app.include_router(checkout.router)
    app.include_router(onboarding.router)
    app.include_router(misc.router)

    return app


app = create_app()
