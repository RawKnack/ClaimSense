
from __future__ import annotations

import logging
from uuid import UUID

from app.db.database import SessionLocal
from app.db.models import Claim, ClaimStatus
from app.services.adjudication_pipeline import adjudicate_claim
from app.services.document_pipeline import prepare_claim_documents

logger = logging.getLogger(__name__)


def process_claim(claim_id: str) -> dict:
    db = SessionLocal()

    try:
        claim = db.query(Claim).filter(Claim.id == UUID(claim_id)).first()

        if not claim:
            raise ValueError(f"Claim {claim_id} not found")

        claim.status = ClaimStatus.PROCESSING
        db.commit()

        structured = None

        if claim.metadata_extra and "structured_documents" in claim.metadata_extra:
            structured = claim.metadata_extra["structured_documents"]
        elif claim.metadata_extra and "documents" in claim.metadata_extra:
            structured = claim.metadata_extra

        documents, ocr_payload, field_confidence = prepare_claim_documents(
            structured_documents=structured,
            document_paths=claim.document_paths,
        )

        if not documents and not structured:
            claim.status = ClaimStatus.FAILED
            claim.error_message = (
                "No documents to adjudicate. Provide structured_documents or upload files."
            )
            db.commit()
            raise ValueError(claim.error_message)

        decision = adjudicate_claim(
            db,
            claim,
            structured_documents={"documents": documents} if documents else structured,
            ocr_payload=ocr_payload,
            field_confidence=field_confidence,
        )

        logger.info(
            "Claim %s adjudicated: %s",
            claim.claim_number,
            decision["decision"],
        )

        return decision

    except Exception as exc:
        logger.exception("Failed processing claim %s", claim_id)

        claim = db.query(Claim).filter(Claim.id == UUID(claim_id)).first()

        if claim and claim.status == ClaimStatus.PROCESSING:
            claim.status = ClaimStatus.FAILED
            claim.error_message = str(exc)
            db.commit()

        raise exc

    finally:
        db.close()