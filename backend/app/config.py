"""Application configuration using pydantic-settings.

All settings are read from environment variables with sensible defaults.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the E.sapiens platform."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://esapiens:esapiens@localhost:5432/esapiens"
    )

    # ── Redis ─────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Auth / JWT ────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ── Modal (compute sandbox) ──────────────────────────────────────
    MODAL_APP_NAME: str = "esapiens-pipelines"
    MODAL_TIMEOUT: int = 600

    # ── CORS ─────────────────────────────────────────────────────────
    # Kept as plain str so pydantic-settings never calls json.loads().
    # Use the .cors_origins_list property for the parsed list.
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS_ORIGINS into a list for CORSMiddleware."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # ── ORCID OAuth ─────────────────────────────────────────────────
    ORCID_CLIENT_ID: str = ""
    ORCID_CLIENT_SECRET: str = ""
    ORCID_REDIRECT_URI: str = "http://localhost:8000/auth/orcid/callback"

    # ── Outbox relay ────────────────────────────────────────────────
    OUTBOX_RELAY_INTERVAL_SECONDS: int = 2
    OUTBOX_REDIS_CHANNEL: str = "esapiens:events"


settings = Settings()