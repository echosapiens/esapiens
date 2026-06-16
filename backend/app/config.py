"""Application configuration using pydantic-settings.

All settings are read from environment variables with sensible defaults.
"""
from __future__ import annotations

from typing import List

from pydantic import field_validator
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
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # ── ORCID OAuth ─────────────────────────────────────────────────
    ORCID_CLIENT_ID: str = ""
    ORCID_CLIENT_SECRET: str = ""
    ORCID_REDIRECT_URI: str = "http://localhost:8000/auth/orcid/callback"

    # ── Outbox relay ────────────────────────────────────────────────
    OUTBOX_RELAY_INTERVAL_SECONDS: int = 2
    OUTBOX_REDIS_CHANNEL: str = "esapiens:events"


settings = Settings()