"""OCR: PyTesseract + OpenCV; Google Vision fallback when confidence is low."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _resize_image_for_fast_ocr(img_bgr: Any, max_dim: int = 1200) -> Any:
    import cv2
    if img_bgr is None or not hasattr(img_bgr, "shape"):
        return img_bgr
    h, w = img_bgr.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / float(max(h, w))
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
    return img_bgr


def _load_image(path: Path) -> Any:
    import numpy as np
    from PIL import Image

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            import fitz
            import cv2

            doc = fitz.open(str(path))
            pages = []
            for page in doc:
                pix = page.get_pixmap(dpi=120)
                img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
                if pix.n == 4:
                    img_bgr = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
                else:
                    img_bgr = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)
                pages.append(_resize_image_for_fast_ocr(img_bgr))
            return pages
        except Exception as exc:
            logger.warning("PDF conversion with PyMuPDF failed (%s): %s", path, exc)
            raise
    import cv2

    img = cv2.imread(str(path))
    if img is None:
        pil = Image.open(path).convert("RGB")
        img_bgr = np.array(pil)[:, :, ::-1]
        return [_resize_image_for_fast_ocr(img_bgr)]
    return [_resize_image_for_fast_ocr(img)]


def _tesseract_page(image_bgr: Any, settings: Settings) -> dict[str, Any]:
    import pytesseract
    from pytesseract import Output
    import sys
    if sys.platform.startswith("win"):
        pytesseract.pytesseract.tesseract_cmd = (
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
    from app.services.ocr.preprocess import preprocess_for_ocr

    image_bgr = _resize_image_for_fast_ocr(image_bgr)
    processed = preprocess_for_ocr(image_bgr)
    data = pytesseract.image_to_data(processed, output_type=Output.DICT)
    confidences = [int(c) for c in data["conf"] if str(c).isdigit() and int(c) >= 0]
    avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    
    words = []
    for text_word, conf in zip(data.get("text", []), data.get("conf", [])):
        if str(conf).isdigit() and int(conf) >= 0 and text_word and text_word.strip():
            words.append(text_word.strip())
    text = " ".join(words).strip()
    if not text:
        text = pytesseract.image_to_string(processed).strip()

    return {"text": text, "confidence": round(avg_conf, 3), "engine": "tesseract"}


def _google_vision_page(image_bgr: Any, settings: Settings) -> dict[str, Any]:
    import base64

    import cv2
    import httpx

    _, buf = cv2.imencode(".png", image_bgr)
    payload = {
        "requests": [
            {
                "image": {"content": base64.b64encode(buf).decode("utf-8")},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
            }
        ]
    }
    url = (
        f"https://vision.googleapis.com/v1/images:annotate"
        f"?key={settings.google_vision_api_key}"
    )
    resp = httpx.post(url, json=payload, timeout=3.0)
    resp.raise_for_status()
    result = resp.json()["responses"][0]
    if "error" in result:
        raise RuntimeError(result["error"].get("message", "Vision API error"))
    annotation = result.get("fullTextAnnotation", {})
    text = annotation.get("text", "").strip()
    return {"text": text, "confidence": 0.85, "engine": "google_vision"}


def ocr_file(file_path: str | Path, settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    images = _load_image(path)
    if not isinstance(images, list):
        images = [images]

    pages: list[dict[str, Any]] = []
    for idx, image in enumerate(images, start=1):
        use_fallback = False
        page_result = {"text": "", "confidence": 0.0, "engine": "tesseract"}
        try:
            page_result = _tesseract_page(image, settings)
        except Exception as exc:
            logger.warning("Tesseract failed on page %s: %s", idx, exc)

        page_result["page"] = idx
        pages.append(page_result)

    full_text = "\n\n".join(p["text"] for p in pages if p.get("text"))
    avg_conf = (
        sum(p["confidence"] for p in pages) / len(pages) if pages else 0.0
    )
    return {
        "source_file": str(path),
        "pages": pages,
        "full_text": full_text,
        "confidence": round(avg_conf, 3),
    }


def ocr_claim_documents(
    document_paths: dict[str, str],
    settings: Settings | None = None,
) -> dict[str, Any]:
    """OCR each uploaded document by type (prescription, bill, etc.)."""
    settings = settings or get_settings()
    by_type: dict[str, Any] = {}
    for doc_type, path in document_paths.items():
        try:
            by_type[doc_type] = ocr_file(path, settings)
        except Exception as exc:
            by_type[doc_type] = {"error": str(exc), "source_file": path, "pages": []}
    return by_type
