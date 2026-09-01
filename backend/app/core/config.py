from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] = project root
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ClaimSense API"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # Set DATABASE_URL in .env for Postgres + pgvector
    database_url: str = "postgresql+psycopg2://claimsense:claimsense@localhost:5433/claimsense_db"
    upload_dir: Path = Path("uploads")
    max_upload_size_mb: int = 10
    allowed_upload_extensions: set[str] = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".tiff",
    }

    policy_terms_path: Path = PROJECT_ROOT / "policy_terms.json"
    adjudication_rules_path: Path = PROJECT_ROOT / "adjudication_rules.md"

    openai_api_key: str | None = None
    google_vision_api_key: str | None = None
    gemini_api_key: str | None = None
    ocr_confidence_fallback_threshold: float = 0.60
    llm_reasoning_confidence_threshold: float = 0.70





@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_llm_client_and_model(settings: Settings):
    """Resolves official Google Gemini client and model using GEMINI_API_KEY."""
    api_key = (settings.gemini_api_key or settings.google_vision_api_key or settings.openai_api_key or "").strip()
    if not api_key:
        return None, None

    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    model = "gemini-2.5-flash"

    return client, model

