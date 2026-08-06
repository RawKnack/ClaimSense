import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.db.database import get_db
from app.db.models import Claim, ClaimStatus, Decision, ExtractedFields
from app.schemas.claim import (
    ClaimCreateResponse,
    ClaimStatusEnum,
    ClaimStatusResponse,
    DecisionOutputSchema,
    RuleResultSchema,
)
from app.services.adjudication_pipeline import (
    adjudicate_claim,
    parse_structured_documents_json,
)
from app.services.storage import save_upload
from app.workers.tasks import process_claim

router = APIRouter(prefix="/claims", tags=["claims"])


def _generate_claim_number() -> str:
    return f"CLM_{uuid.uuid4().hex[:8].upper()}"


_SWAGGER_PLACEHOLDERS = frozenset({"string", "null", "none", "undefined", "n/a", "na"})


def _is_swagger_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    return str(value).strip().lower() in _SWAGGER_PLACEHOLDERS


def _clean_optional_str(value: str | None) -> str | None:
    if _is_swagger_placeholder(value):
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_optional_date(value: str | None) -> str | None:
    """Optional dates: ignore Swagger placeholders; drop invalid values."""
    if _is_swagger_placeholder(value):
        return None
    from datetime import datetime

    cleaned = str(value).strip()[:10]
    try:
        datetime.strptime(cleaned, "%Y-%m-%d")
    except ValueError:
        return None
    return cleaned


def _validate_required_date(field_name: str, value: str) -> str:
    if _is_swagger_placeholder(value):
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} is required (YYYY-MM-DD)",
        )
    from datetime import datetime

    cleaned = str(value).strip()[:10]
    try:
        datetime.strptime(cleaned, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be YYYY-MM-DD (got {value!r})",
        ) from exc
    return cleaned


def _sanitize_invalid_join_date(claim: Claim) -> None:
    claim.member_join_date = _clean_optional_date(claim.member_join_date)


def _claim_to_status_response(claim: Claim, db: Session) -> ClaimStatusResponse:
    decision_row = db.query(Decision).filter(Decision.claim_id == claim.id).first()
    extracted_row = (
        db.query(ExtractedFields).filter(ExtractedFields.claim_id == claim.id).first()
    )

    decision_schema = None
    if decision_row:
        payload = decision_row.decision_payload
        rule_results = [
            RuleResultSchema(**r) for r in payload.get("rule_results", [])
        ]
        decision_schema = DecisionOutputSchema(
            claim_id=payload.get("claim_id", str(claim.id)),
            claim_number=payload.get("claim_number"),
            decision=payload["decision"],
            approved_amount=payload.get("approved_amount", 0),
            rejection_reasons=payload.get("rejection_reasons", []),
            rejected_items=payload.get("rejected_items", []),
            deductions=payload.get("deductions", {}),
            flags=payload.get("flags", []),
            confidence_score=payload.get("confidence_score", 0),
            notes=payload.get("notes"),
            next_steps=payload.get("next_steps"),
            rule_results=rule_results,
            cashless_approved=payload.get("cashless_approved"),
            network_discount=payload.get("network_discount"),
            medical_necessity_established=payload.get("medical_necessity_established"),
            exclusions_detected=payload.get("exclusions_detected", []),
        )

    return ClaimStatusResponse(
        claim_id=claim.id,
        claim_number=claim.claim_number,
        status=ClaimStatusEnum(claim.status.value),
        member_id=claim.member_id,
        member_name=claim.member_name,
        treatment_date=claim.treatment_date,
        claim_amount=claim.claim_amount,
        created_at=claim.created_at,
        updated_at=claim.updated_at,
        error_message=claim.error_message,
        decision=decision_schema,
        extracted_fields=extracted_row.extracted_data if extracted_row else None,
    )


@router.post("", response_model=ClaimCreateResponse, status_code=202)
async def submit_claim(
    member_id: Annotated[str, Form()],
    member_name: Annotated[str, Form()],
    treatment_date: Annotated[str, Form(description="YYYY-MM-DD")],
    claim_amount: Annotated[float, Form()],
    member_join_date: Annotated[str | None, Form()] = None,
    hospital: Annotated[str | None, Form()] = None,
    cashless_request: Annotated[str | None, Form()] = None,
    previous_claims_same_day: Annotated[int | None, Form()] = None,
    structured_documents: Annotated[
        str | None,
        Form(
            description="JSON blob matching test_cases input_data.documents for MVP/testing"
        ),
    ] = None,
    prescription: Annotated[UploadFile | None, File()] = None,
    bill: Annotated[UploadFile | None, File()] = None,
    diagnostic_report: Annotated[UploadFile | None, File()] = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> ClaimCreateResponse:
    """
    Accept claim metadata + optional document uploads.
    Returns immediately with claim_id;
    """
    treatment_date = _validate_required_date("treatment_date", treatment_date)
    member_join_date = _clean_optional_date(member_join_date)
    hospital = _clean_optional_str(hospital)
    cashless_on = str(cashless_request or "").lower() in ("true", "1", "on", "yes")

    claim_number = _generate_claim_number()
    claim = Claim(
        claim_number=claim_number,
        status=ClaimStatus.PENDING,
        member_id=member_id.strip(),
        member_name=member_name.strip(),
        member_join_date=member_join_date,
        treatment_date=treatment_date,
        claim_amount=claim_amount,
        hospital=hospital,
        cashless_request=cashless_on,
        previous_claims_same_day=previous_claims_same_day or None,
        metadata_extra={},
        document_paths={},
    )
    db.add(claim)
    db.flush()

    try:
        if structured_documents:
            parsed = parse_structured_documents_json(structured_documents)
            claim.metadata_extra = {"structured_documents": parsed}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    doc_paths: dict[str, str] = {}
    file_hashes: dict[str, str] = {}
    uploads = [
        ("prescription", prescription),
        ("bill", bill),
        ("diagnostic_report", diagnostic_report),
    ]
    for doc_type, upload in uploads:
        if upload and upload.filename:
            path = await save_upload(claim.id, upload, settings, doc_type)
            doc_paths[doc_type] = path
            try:
                import hashlib
                with open(path, "rb") as f:
                    file_hashes[doc_type] = hashlib.md5(f.read()).hexdigest()
            except Exception:
                pass

    if doc_paths:
        claim.document_paths = doc_paths

    if file_hashes:
        metadata = dict(claim.metadata_extra or {})
        metadata["file_hashes"] = file_hashes
        claim.metadata_extra = metadata

    if not claim.metadata_extra and not doc_paths:
        raise HTTPException(
            status_code=400,
            detail="Provide structured_documents JSON and/or upload at least one document",
        )

    db.commit()
    db.refresh(claim)
    process_claim(str(claim.id))
    db.refresh(claim)
    response_status = ClaimStatusEnum(claim.status.value)

    return ClaimCreateResponse(
        claim_id=claim.id,
        claim_number=claim.claim_number,
        status=response_status,
        message=(
            "Claim submitted. Poll GET /claims/{claim_id} for status."
            if response_status == ClaimStatusEnum.PENDING
            else "Claim adjudicated. Use GET /claims/{claim_id} for full decision."
        ),
    )


@router.get("/{claim_id}", response_model=ClaimStatusResponse)
def get_claim_status(
    claim_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ClaimStatusResponse:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _claim_to_status_response(claim, db)


@router.get("/{claim_id}/decision", response_model=DecisionOutputSchema)
def get_claim_decision(
    claim_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DecisionOutputSchema:
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    if claim.status in (ClaimStatus.PENDING, ClaimStatus.PROCESSING):
        raise HTTPException(
            status_code=202,
            detail=f"Adjudication in progress. Current status: {claim.status.value}",
        )

    decision_row = db.query(Decision).filter(Decision.claim_id == claim_id).first()
    if not decision_row:
        raise HTTPException(status_code=404, detail="Decision not yet available")

    payload = decision_row.decision_payload
    return DecisionOutputSchema(
        claim_id=payload.get("claim_id", str(claim_id)),
        claim_number=payload.get("claim_number"),
        decision=payload["decision"],
        approved_amount=payload.get("approved_amount", 0),
        rejection_reasons=payload.get("rejection_reasons", []),
        rejected_items=payload.get("rejected_items", []),
        deductions=payload.get("deductions", {}),
        flags=payload.get("flags", []),
        confidence_score=payload.get("confidence_score", 0),
        notes=payload.get("notes"),
        next_steps=payload.get("next_steps"),
        rule_results=[RuleResultSchema(**r) for r in payload.get("rule_results", [])],
        cashless_approved=payload.get("cashless_approved"),
        network_discount=payload.get("network_discount"),
        medical_necessity_established=payload.get("medical_necessity_established"),
        exclusions_detected=payload.get("exclusions_detected", []),
    )


@router.post("/{claim_id}/adjudicate-sync", response_model=DecisionOutputSchema)
def adjudicate_sync(
    claim_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> DecisionOutputSchema:
    """Synchronous adjudication for local testing without Celery."""
    claim = db.query(Claim).filter(Claim.id == claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    _validate_required_date("treatment_date", claim.treatment_date)
    _sanitize_invalid_join_date(claim)

    structured = None
    if claim.metadata_extra:
        structured = claim.metadata_extra.get("structured_documents") or claim.metadata_extra

    try:
        payload = adjudicate_claim(db, claim, structured_documents=structured)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Adjudication failed: {exc}",
        ) from exc
    return DecisionOutputSchema(
        claim_id=payload["claim_id"],
        claim_number=payload.get("claim_number"),
        decision=payload["decision"],
        approved_amount=payload.get("approved_amount", 0),
        rejection_reasons=payload.get("rejection_reasons", []),
        rejected_items=payload.get("rejected_items", []),
        deductions=payload.get("deductions", {}),
        flags=payload.get("flags", []),
        confidence_score=payload.get("confidence_score", 0),
        notes=payload.get("notes"),
        next_steps=payload.get("next_steps"),
        rule_results=[RuleResultSchema(**r) for r in payload.get("rule_results", [])],
        cashless_approved=payload.get("cashless_approved"),
        network_discount=payload.get("network_discount"),
        medical_necessity_established=payload.get("medical_necessity_established"),
        exclusions_detected=payload.get("exclusions_detected", []),
    )
