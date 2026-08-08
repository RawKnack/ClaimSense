from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.db.database import get_db
from app.schemas.claim import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> HealthResponse:
    db_status = "ok"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    overall = "ok" if db_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        service=settings.app_name,
        database=db_status,
    )


@router.get("/health/check-keys")
def check_keys(
    settings: Settings = Depends(get_app_settings),
):
    return {
        "openai_api_key": settings.openai_api_key,
        "gemini_api_key": settings.gemini_api_key,
        "google_vision_api_key": settings.google_vision_api_key,
    }