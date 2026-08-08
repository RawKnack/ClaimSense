import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import Settings


def ensure_upload_dir(settings: Settings) -> Path:
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def validate_upload(file: UploadFile, settings: Settings) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename")
    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_upload_extensions:
        raise HTTPException(
            status_code=400,
            detail=(
                f"File type '{ext}' not allowed. "
                f"Allowed: {', '.join(sorted(settings.allowed_upload_extensions))}"
            ),
        )
    return ext


async def save_upload(
    claim_id: uuid.UUID,
    file: UploadFile,
    settings: Settings,
    document_type: str,
) -> str:
    ext = validate_upload(file, settings)
    upload_dir = ensure_upload_dir(settings)
    claim_dir = upload_dir / str(claim_id)
    claim_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{document_type}{ext}"
    dest = claim_dir / safe_name
    content = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds {settings.max_upload_size_mb}MB limit",
        )
    dest.write_bytes(content)
    return str(dest)
