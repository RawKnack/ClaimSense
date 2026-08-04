"""LLM field extraction from OCR text — extraction only, no adjudication."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import Settings, get_settings, get_llm_client_and_model

logger = logging.getLogger(__name__)

EXTRACTION_SCHEMA = """
Return JSON with this shape only:
{
  "prescription": {
    "doctor_name": str|null,
    "doctor_reg": str|null,
    "diagnosis": str|null,
    "medicines_prescribed": [str]|null,
    "procedures": [str]|null,
    "tests_prescribed": [str]|null,
    "treatment": str|null
  }|null,
  "bill": { "<line_item_key>": number, ... }|null,
  "field_confidence": { "<field_path>": 0.0-1.0 }
}
"""

DOCTOR_REG_RE = re.compile(
    r"\b([A-Z]{2,5}/\d+/\d{4}|AYUR/[A-Z]{2}/\d+/\d{4})\b",
    re.IGNORECASE,
)


def _heuristic_extract(doc_type: str, text: str) -> dict[str, Any]:
    """Fallback when no LLM API key — basic pattern matching."""
    text_clean = " ".join(text.split())
    result: dict[str, Any] = {}
    confidence: dict[str, float] = {}

    if doc_type == "prescription":
        reg_match = DOCTOR_REG_RE.search(text_clean.replace(" ", ""))
        doctor_reg = reg_match.group(1).upper() if reg_match else None
        diagnosis = None
        for line in text.splitlines():
            lower = line.lower()
            if "diagnosis" in lower or "dx" in lower:
                diagnosis = line.split(":", 1)[-1].strip() or line.strip()
                break
        prescription = {
            "doctor_name": None,
            "doctor_reg": doctor_reg,
            "diagnosis": diagnosis,
            "medicines_prescribed": None,
            "procedures": None,
            "tests_prescribed": None,
            "treatment": None,
        }
        result["prescription"] = prescription
        if doctor_reg:
            confidence["prescription.doctor_reg"] = 0.7
        if diagnosis:
            confidence["prescription.diagnosis"] = 0.6
    elif doc_type == "bill":
        bill: dict[str, float] = {}
        for line in text.splitlines():
            amounts = re.findall(r"[\d,]+\.?\d*", line.replace(",", ""))
            if not amounts:
                continue
            label = re.sub(r"[^a-zA-Z ]", "", line).strip().lower().replace(" ", "_")
            if not label:
                label = f"item_{len(bill) + 1}"
            try:
                bill[label[:40] or f"line_{len(bill)}"] = float(amounts[-1])
            except ValueError:
                continue
        result["bill"] = bill or None
        if bill:
            confidence["bill"] = 0.55

    result["field_confidence"] = confidence
    return result


def _openai_extract(doc_type: str, text: str, settings: Settings) -> dict[str, Any]:
    client, model = get_llm_client_and_model(settings)
    if not client or not model:
        raise ValueError("No valid LLM client or model resolved.")

    prompt = (
        f"Document type: {doc_type}\n"
        f"OCR text:\n{text[:12000]}\n\n"
        f"{EXTRACTION_SCHEMA}"
    )
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract structured medical claim fields from OCR text. "
                    "Output valid JSON only. Do not approve or reject claims. "
                    "CRITICAL: Output valid JSON only. Do not include any unescaped double-quotes "
                    "inside string values (use single-quotes or escape them as \\\")."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0,
        max_tokens=2048,
    )
    content = response.choices[0].message.content or "{}"
    content_clean = content.strip()
    if content_clean.startswith("```"):
        if content_clean.startswith("```json"):
            content_clean = content_clean[7:]
        else:
            content_clean = content_clean[3:]
        if content_clean.endswith("```"):
            content_clean = content_clean[:-3]
        content_clean = content_clean.strip()
    return json.loads(content_clean)


def extract_from_ocr(
    ocr_by_type: dict[str, Any],
    settings: Settings | None = None,
) -> tuple[dict[str, Any], dict[str, float]]:
    """Merge per-document extractions into documents dict for rule engine."""
    settings = settings or get_settings()
    client, model = get_llm_client_and_model(settings)
    has_api_key = client is not None
    documents: dict[str, Any] = {}
    all_confidence: dict[str, float] = {}

    for doc_type, ocr_payload in ocr_by_type.items():
        if ocr_payload.get("error"):
            continue
        text = ocr_payload.get("full_text") or ""
        if not text.strip():
            continue
        try:
            if has_api_key:
                parsed = _openai_extract(doc_type, text, settings)
            else:
                parsed = _heuristic_extract(doc_type, text)
        except Exception as exc:
            logger.warning("Extraction failed for %s: %s", doc_type, exc)
            parsed = _heuristic_extract(doc_type, text)

        field_conf = parsed.pop("field_confidence", {}) or {}
        for key, val in field_conf.items():
            all_confidence[f"{doc_type}.{key}" if not key.startswith(doc_type) else key] = val

        if doc_type == "prescription" and parsed.get("prescription"):
            documents["prescription"] = parsed["prescription"]
        elif doc_type == "bill" and parsed.get("bill"):
            documents["bill"] = parsed["bill"]
        elif doc_type in parsed:
            documents[doc_type] = parsed[doc_type]
        else:
            documents[doc_type] = {
                k: v for k, v in parsed.items() if k not in ("field_confidence",)
            }

    return documents, all_confidence
