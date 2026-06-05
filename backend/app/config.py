import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    MODAL_TOKEN_ID: str = os.getenv("MODAL_TOKEN_ID", "")
    MODAL_TOKEN_SECRET: str = os.getenv("MODAL_TOKEN_SECRET", "")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./esapiens.db")
    API_V1_STR: str = "/api/v1"
    FREE_TIER_MARKUP: float = 0.35
    PREMIUM_TIER_MARKUP: float = 0.05
    DEFAULT_LLM_MODEL: str = "nvidia/nemotron-3-super-120b-a12b"
    HEAVY_LLM_MODEL: str = "nvidia/nemotron-3-ultra-550b-a55b"


settings = Settings()