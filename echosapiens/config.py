"""
config.py — Global Environment, Settings, and Secrets Configuration.

Manages LLM endpoints, GCS storage, sandbox compute limits, and workflow
orchestration parameters via pydantic-settings.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ErrorHandlingPreference = Literal[
    "agentic_self_correction",
    "fail_fast_expose",
    "human_in_the_loop",
]


class Settings(BaseSettings):
    """Global settings for the EchoSapiens execution engine."""

    # ── LLM Settings (OpenAI-compatible: Tencent HY3 / DeepSeek / OpenRouter) ──
    llm_api_key: str = Field(..., validation_alias="LLM_API_KEY")
    llm_base_url: str = Field(
        "https://api.lkeap.cloud.tencent.com/v1",
        validation_alias="LLM_BASE_URL",
    )
    llm_model: str = Field("deepseek-v4-flash", validation_alias="LLM_MODEL")
    llm_temperature: float = 0.1
    llm_max_tokens: int = 16384

    # ── GCS Storage Configuration ──
    gcs_bucket_name: str = Field(..., validation_alias="GCS_BUCKET_NAME")
    gcp_project_id: str = Field(..., validation_alias="GCP_PROJECT_ID")
    gcs_signed_url_ttl: int = Field(3600, validation_alias="GCS_SIGNED_URL_TTL")

    # ── Sandbox Compute Configuration ──
    sandbox_default_cpu: float = Field(2.0, validation_alias="SANDBOX_DEFAULT_CPU")
    sandbox_default_memory_mb: int = Field(4096, validation_alias="SANDBOX_DEFAULT_MEMORY_MB")
    sandbox_timeout_seconds: int = Field(1800, validation_alias="SANDBOX_TIMEOUT_SECONDS")

    # ── Workflow Orchestration ──
    error_handling_preference: ErrorHandlingPreference = Field(
        "agentic_self_correction",
        validation_alias="ERROR_HANDLING_PREFERENCE",
    )
    max_agentic_retries: int = Field(3, validation_alias="MAX_AGENTIC_RETRIES")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_settings() -> Settings:
    """Load, validate, and return system settings.

    Instantiates Settings, which triggers pydantic validation against
    environment variables and the .env file.
    """
    return Settings()
