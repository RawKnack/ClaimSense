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
    """Dynamically resolves OpenAI-compatible client and model based on API keys."""
    keys = {}
    if settings.gemini_api_key and settings.gemini_api_key.strip():
        keys["gemini"] = settings.gemini_api_key.strip()
    if settings.google_vision_api_key and settings.google_vision_api_key.strip():
        keys["vision"] = settings.google_vision_api_key.strip()
    if settings.openai_api_key and settings.openai_api_key.strip():
        keys["openai"] = settings.openai_api_key.strip()

    if not keys:
        return None, None

    chosen_key = None
    key_type = None

    # 1. Prioritize OpenRouter key (starts with sk-or-v1-)
    for name, key in keys.items():
        if key.startswith("sk-or-v1-"):
            chosen_key = key
            key_type = "openrouter"
            break

    # 2. Then OpenAI key (starts with sk-)
    if not chosen_key:
        for name, key in keys.items():
            if key.startswith("sk-") and not key.startswith("sk-or-v1-"):
                chosen_key = key
                key_type = "openai"
                break

    # 3. Then standard Google Gemini key (starts with AIzaSy)
    if not chosen_key:
        for name, key in keys.items():
            if key.startswith("AIzaSy"):
                chosen_key = key
                key_type = "gemini"
                break

    # Fallback to the original priority order if no prefix matches
    if not chosen_key:
        fallback_order = ["gemini", "vision", "openai"]
        for name in fallback_order:
            if name in keys:
                chosen_key = keys[name]
                if chosen_key.startswith("sk-or-v1-"):
                    key_type = "openrouter"
                elif chosen_key.startswith("sk-"):
                    key_type = "openai"
                elif chosen_key.startswith("AIzaSy"):
                    key_type = "gemini"
                else:
                    key_type = "gemini"  # assume gemini/google
                break

    if not chosen_key:
        return None, None

    from openai import OpenAI

    if key_type == "openrouter":
        client = OpenAI(
            api_key=chosen_key,
            base_url="https://openrouter.ai/api/v1"
        )
        model = "google/gemini-flash-1.5"
    elif key_type == "openai":
        client = OpenAI(
            api_key=chosen_key,
        )
        model = "gpt-4o-mini"
    else:
        client = OpenAI(
            api_key=chosen_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        model = "gemini-2.5-flash"

    return client, model

