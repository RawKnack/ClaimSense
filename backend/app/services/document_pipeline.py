"""OCR + LLM extraction → documents dict for rule engine."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import Settings, get_settings
from app.services.llm.extraction import extract_from_ocr
from app.services.ocr.service import ocr_claim_documents
from app.services.adjudication_pipeline import build_documents_from_structured

logger = logging.getLogger(__name__)


def prepare_claim_documents(
    structured_documents: dict[str, Any] | None,
    document_paths: dict[str, str] | None,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, float]]:
    """
    Returns (documents, ocr_payload, field_confidence).
    Uses structured JSON when provided; otherwise OCR + extraction from files.
    """
    settings = settings or get_settings()

    if structured_documents:
        docs = build_documents_from_structured(structured_documents)
        if docs:
            return docs, None, {"source": 1.0}

    if document_paths:
        ocr_payload = ocr_claim_documents(document_paths, settings)
        documents, field_confidence = extract_from_ocr(ocr_payload, settings)
        if documents:
            return documents, ocr_payload, field_confidence
        logger.warning("OCR produced no extractable documents")
        return {}, ocr_payload, field_confidence

    return {}, None, {}
