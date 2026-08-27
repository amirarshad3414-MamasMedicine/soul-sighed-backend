"""Application settings, loaded from the environment (.env in development)."""
import re
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://app:app_password@localhost:5433/app_db"

    # When NEONDB is present in the environment it wins: the app runs on Neon.
    # Remove/rename it to fall back to the local docker Postgres above.
    neondb: str = ""

    @model_validator(mode="after")
    def _prefer_neon(self):
        """Convert a Neon connection string into the asyncpg form the engine needs:
        swap the driver to +asyncpg, use the *direct* endpoint (strip `-pooler`, so
        asyncpg's prepared statements are not broken by PgBouncer), and drop the
        libpq-only `?sslmode=`/`?channel_binding=` params (TLS is applied via
        db_connect_args instead). The credential never leaves the environment."""
        if self.neondb:
            m = re.match(r"postgresql(?:\+\w+)?://([^:]+):([^@]+)@([^/?]+)/([^?]+)", self.neondb)
            if m:
                user, pw, host, db = m.groups()
                host = host.replace("-pooler", "")
                object.__setattr__(self, "database_url",
                                   f"postgresql+asyncpg://{user}:{pw}@{host}/{db}")
        return self

    @property
    def db_connect_args(self) -> dict:
        """asyncpg connect args. Neon (and any managed Postgres) needs TLS, which
        asyncpg takes as an `ssl` kwarg — the libpq `?sslmode=`/`?channel_binding=`
        query params in a Neon URL are not understood by asyncpg and must be
        dropped from the URL. `statement_cache_size=0` keeps it safe behind Neon's
        PgBouncer `-pooler` endpoint; harmless on a direct connection."""
        if "neon.tech" in self.database_url:
            return {"ssl": True, "statement_cache_size": 0}
        return {}

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    # Xano issues tokens with expiration = 86400 (24h) in auth/login,
    # auth/signup and register_passwordless. Matched deliberately.
    jwt_expire_minutes: int = 60 * 24

    # external services the Xano stacks called; see xano-export/inventory.csv
    # Two different Google keys, deliberately. places_autocomplete and
    # add_children use the geocoding key; places_details uses this other one.
    # Confusing, but reproduced from the XanoScript rather than unified.
    google_geocoding_api_key: str = ""
    google_places_autocomplete_api_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    insights_api_key: str = ""
    external_insight_api_url: str = ""
    insight_max_retries: int = 5      # Xano: var $max_retries { value = 5 }
    insight_timeout_seconds: float = 300.0

    # Hardcoded inside the Xano `checkout` stack rather than held in an env var.
    # Read from the environment here — same value, not committed to source.
    klaviyo_api_key: str = ""
    klaviyo_list_id: str = "XPSdCW"

    # Both are hardcoded in checkout.xs. The second is a specific Vercel
    # deployment URL, so a rename would silently stop insight emails.
    purchase_email_url: str = "https://parenting-insights.soul-sighted.com/api/send-purchase-email"
    send_insight_url: str = "https://mamas-medicine-frontend-rosy.vercel.app/api/send-insight"

    email_provider_api_key: str = ""
    email_from: str = ""

    # Browser origins allowed to call this API. Xano sends CORS headers, so the
    # frontend already makes these calls cross-origin; the port must too or the
    # browser blocks them. Comma-separated in the env. Dev defaults cover the
    # Next dev server (3000) and the analytics dashboard (3001).
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001"

    debug: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
