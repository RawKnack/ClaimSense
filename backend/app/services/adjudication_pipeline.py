"""Orchestrates OCR → extraction → rules → optional LLM reasoning."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Claim, ClaimStatus, Decision, ExtractedFields
from app.services.policy_rag import retrieve_policy_context
from app.services.rule_engine import AdjudicationContext, run_rule_engine

logger = logging.getLogger(__name__)


MEMBER_REGISTRY = {
    "emp001": {"name": "rajesh kumar", "join_date": "2024-01-01"},
    "emp002": {"name": "priya singh", "join_date": "2024-01-01"},
    "emp003": {"name": "amit verma", "join_date": "2024-01-01"},
    "emp004": {"name": "sneha reddy", "join_date": "2024-01-01"},
    "emp005": {"name": "vikram joshi", "join_date": "2024-09-01"},
    "emp006": {"name": "kavita nair", "join_date": "2024-01-01"},
    "emp007": {"name": "suresh patil", "join_date": "2024-01-01"},
    "emp008": {"name": "ravi menon", "join_date": "2024-01-01"},
    "emp009": {"name": "anita desai", "join_date": "2024-01-01"},
    "emp010": {"name": "deepak shah", "join_date": "2024-01-01"},
}


def build_documents_from_structured(structured: dict[str, Any] | None) -> dict[str, Any]:
    if not structured:
        return {}
    if "documents" in structured:
        return structured["documents"]
    return structured


def get_bill_hash(claim: Claim, documents: dict[str, Any]) -> str | None:
    # 1. Check if we already have the uploaded file hash in metadata_extra
    if claim.metadata_extra and "file_hashes" in claim.metadata_extra:
        bill_hash = claim.metadata_extra["file_hashes"].get("bill")
        if bill_hash:
            return bill_hash

    # 2. Check if we have a bill in the structured documents
    bill_data = documents.get("bill")
    if bill_data:
        # Compute a deterministic MD5 hash of the bill data
        import hashlib
        import json
        try:
            serialized = json.dumps(bill_data, sort_keys=True)
            return hashlib.md5(serialized.encode("utf-8")).hexdigest()
        except Exception:
            pass

    return None


def adjudicate_claim(
    db: Session,
    claim: Claim,
    structured_documents: dict[str, Any] | None = None,
    ocr_payload: dict[str, Any] | None = None,
    field_confidence: dict[str, float] | None = None,
) -> dict[str, Any]:
    documents = build_documents_from_structured(structured_documents)
    if not documents and claim.metadata_extra:
        documents = build_documents_from_structured(claim.metadata_extra)

    # Check for duplicate bills
    bill_hash = get_bill_hash(claim, documents)
    duplicate_bill_detected = False
    if bill_hash:
        # Store back in metadata_extra to make it queryable/persistent
        if not claim.metadata_extra:
            claim.metadata_extra = {}
        metadata = dict(claim.metadata_extra)
        if "file_hashes" not in metadata:
            metadata["file_hashes"] = {}
        if "bill" not in metadata["file_hashes"]:
            metadata["file_hashes"]["bill"] = bill_hash
            claim.metadata_extra = metadata
        
        # Query other claims from database
        other_claims = (
            db.query(Claim)
            .filter(Claim.id != claim.id)
            .all()
        )
        for other in other_claims:
            other_bill_hash = None
            if other.metadata_extra and "file_hashes" in other.metadata_extra:
                other_bill_hash = other.metadata_extra["file_hashes"].get("bill")
            
            if not other_bill_hash:
                other_docs = build_documents_from_structured(other.metadata_extra.get("structured_documents") if other.metadata_extra else None)
                if not other_docs and other.metadata_extra:
                    other_docs = build_documents_from_structured(other.metadata_extra)
                other_bill_data = other_docs.get("bill")
                if other_bill_data:
                    import hashlib
                    import json
                    try:
                        serialized = json.dumps(other_bill_data, sort_keys=True)
                        other_bill_hash = hashlib.md5(serialized.encode("utf-8")).hexdigest()
                    except Exception:
                        pass
            
            if other_bill_hash and other_bill_hash == bill_hash:
                duplicate_bill_detected = True
                break

    # Count other claims for this member on the same treatment date in the database
    db_count = (
        db.query(Claim)
        .filter(
            Claim.member_id == claim.member_id,
            Claim.treatment_date == claim.treatment_date,
            Claim.id != claim.id
        )
        .count()
    )

    # Resolve member join date if not already provided
    join_date = claim.member_join_date
    if not join_date:
        submitted_name = str(claim.member_name).strip().lower()
        name_match = False
        for info in MEMBER_REGISTRY.values():
            reg_name = info["name"]
            first_name_reg = reg_name.split()[0]
            first_name_sub = submitted_name.split()[0] if submitted_name.split() else ""
            if (reg_name in submitted_name 
                or submitted_name in reg_name 
                or (first_name_sub and len(first_name_sub) >= 5 and first_name_reg[:5] == first_name_sub[:5])):
                join_date = info["join_date"]
                name_match = True
                break
        if not name_match:
            mid_key = str(claim.member_id).strip().lower()
            if mid_key in MEMBER_REGISTRY:
                join_date = MEMBER_REGISTRY[mid_key]["join_date"]
        if join_date:
            claim.member_join_date = join_date

    ctx = AdjudicationContext(
        member_id=claim.member_id,
        member_name=claim.member_name,
        treatment_date=claim.treatment_date,
        claim_amount=claim.claim_amount,
        documents=documents,
        member_join_date=join_date,
        hospital=claim.hospital,
        cashless_request=claim.cashless_request,
        previous_claims_same_day=db_count or claim.previous_claims_same_day,
        duplicate_bill_detected=duplicate_bill_detected,
    )

    outcome = run_rule_engine(ctx)

    prescription = documents.get("prescription") or {}
    policy_context = retrieve_policy_context(
        diagnosis=prescription.get("diagnosis"),
        treatment=prescription.get("treatment"),
        db=db,
    )

    # Invoke LLM Adjudication Reasoning
    from app.services.llm.adjudication import analyze_claim_with_llm
    ai_adjudication = analyze_claim_with_llm(
        claim_id=str(claim.id),
        claim_number=claim.claim_number,
        claim_amount=claim.claim_amount,
        treatment_date=claim.treatment_date,
        member_name=claim.member_name,
        member_id=claim.member_id,
        documents=documents,
        preliminary_decision=outcome,
        policy_context=policy_context,
    )

    # Merge LLM analysis results
    outcome["medical_necessity_established"] = ai_adjudication.get("medical_necessity_established", True)
    outcome["exclusions_detected"] = ai_adjudication.get("exclusions_detected", [])

    prelim_verdict = outcome["decision"]
    llm_verdict = ai_adjudication.get("verdict")
    llm_rejected_items = ai_adjudication.get("rejected_line_items") or []

    # --- Override logic ---
    # Case 1: LLM detected specific items to reject (partial exclusion)
    if llm_rejected_items and prelim_verdict in ("APPROVED", "PARTIAL"):
        rejected_total = sum(item.get("amount", 0) for item in llm_rejected_items)
        if rejected_total > 0:
            prelim_approved = outcome.get("approved_amount", 0)
            approved_amount, deductions = _recalculate_approved_amount(
                claim_amount=claim.claim_amount,
                documents=documents,
                rejected_items=llm_rejected_items,
            )
            outcome["approved_amount"] = approved_amount
            outcome["deductions"] = deductions
            # Build human-readable rejected_items list
            outcome["rejected_items"] = list(set(
                outcome.get("rejected_items", [])
                + [f"{item['item_name']} (₹{item['amount']}) - {item.get('reason', 'excluded')}"
                   for item in llm_rejected_items]
            ))
            outcome["rejection_reasons"] = list(
                set(outcome.get("rejection_reasons", []) + ["EXCLUDED_CONDITION"])
            )
            # Decide final verdict: PARTIAL if some items approved, REJECTED if nothing left
            if approved_amount > 0:
                outcome["decision"] = "PARTIAL"
            else:
                outcome["decision"] = "REJECTED"

            logger.info(
                "LLM override for claim %s: rejected %d items (₹%.2f), "
                "approved_amount recalculated from ₹%.2f to ₹%.2f",
                claim.claim_number,
                len(llm_rejected_items),
                rejected_total,
                prelim_approved,
                approved_amount,
            )

    # Case 2: LLM fully rejects or escalates (no specific items, just verdict override)
    elif prelim_verdict in ("APPROVED", "PARTIAL") and llm_verdict in ("REJECTED", "MANUAL_REVIEW"):
        outcome["decision"] = llm_verdict
        if llm_verdict == "REJECTED":
            outcome["approved_amount"] = 0
            outcome["rejection_reasons"] = list(
                set(outcome.get("rejection_reasons", []) + ["EXCLUDED_CONDITION"])
            )

    # Case 3: LLM flagged exclusions but didn't return structured rejected_line_items.
    # Use the LLM's approved_amount as a fallback if it provided one.
    elif (
        prelim_verdict in ("APPROVED", "PARTIAL")
        and not llm_rejected_items
        and (
            ai_adjudication.get("exclusions_detected")
            or ai_adjudication.get("medical_necessity_established") is False
            or llm_verdict == "PARTIAL"
        )
    ):
        llm_approved = ai_adjudication.get("approved_amount")
        if llm_approved is not None and isinstance(llm_approved, (int, float)) and llm_approved < outcome.get("approved_amount", 0):
            prelim_approved = outcome.get("approved_amount", 0)
            outcome["approved_amount"] = round(float(llm_approved), 2)
            # Recompute deductions based on the difference
            rejected_total = round(claim.claim_amount - float(llm_approved), 2)
            # Try to infer copay from the LLM's notes or recalculate
            _recalc_approved, _recalc_deductions = _recalculate_approved_amount(
                claim_amount=claim.claim_amount,
                documents=documents,
                rejected_items=[{"item_name": "LLM-excluded items", "amount": rejected_total, "reason": "excluded per LLM analysis"}],
            )
            # Use the recalculated value if it's close to the LLM's, otherwise trust the LLM
            if abs(_recalc_approved - float(llm_approved)) <= 1.0:
                outcome["approved_amount"] = _recalc_approved
                outcome["deductions"] = _recalc_deductions
            else:
                outcome["approved_amount"] = round(float(llm_approved), 2)

            outcome["rejection_reasons"] = list(
                set(outcome.get("rejection_reasons", []) + ["EXCLUDED_CONDITION"])
            )
            if outcome["approved_amount"] > 0:
                outcome["decision"] = "PARTIAL"
            else:
                outcome["decision"] = "REJECTED"

            logger.info(
                "LLM fallback override for claim %s: exclusions detected without "
                "structured line items, approved_amount adjusted from ₹%.2f to ₹%.2f",
                claim.claim_number,
                prelim_approved,
                outcome["approved_amount"],
            )

    # Update notes, next steps, and confidence score with AI reasoning output
    outcome["notes"] = ai_adjudication.get("notes") or outcome.get("notes")
    outcome["next_steps"] = ai_adjudication.get("next_steps") or outcome.get("next_steps")
    outcome["confidence_score"] = ai_adjudication.get("confidence_score") or outcome.get("confidence_score", 0.95)

    if policy_context:
        outcome["policy_context"] = policy_context

    extracted_record = {
        "documents": documents,
        "member_id": claim.member_id,
        "claim_amount": claim.claim_amount,
    }
    if not field_confidence:
        field_confidence = {k: 0.95 for k in ("documents", "claim_amount")}

    existing_extracted = (
        db.query(ExtractedFields).filter(ExtractedFields.claim_id == claim.id).first()
    )
    if existing_extracted:
        existing_extracted.extracted_data = extracted_record
        existing_extracted.ocr_result = ocr_payload
        existing_extracted.field_confidence = field_confidence
    else:
        db.add(
            ExtractedFields(
                claim_id=claim.id,
                extracted_data=extracted_record,
                ocr_result=ocr_payload,
                field_confidence=field_confidence,
            )
        )

    decision_payload = {
        "claim_id": str(claim.id),
        "claim_number": claim.claim_number,
        **outcome,
        "rule_results": [
            {
                "rule_name": r.rule_name,
                "passed": r.passed,
                "reason_code": r.reason_code,
                "note": r.note,
            }
            for r in ctx.rule_results
        ],
    }

    existing_decision = (
        db.query(Decision).filter(Decision.claim_id == claim.id).first()
    )
    if existing_decision:
        existing_decision.decision_payload = decision_payload
    else:
        db.add(Decision(claim_id=claim.id, decision_payload=decision_payload))

    decision_status = outcome["decision"]
    if decision_status == "MANUAL_REVIEW":
        claim.status = ClaimStatus.MANUAL_REVIEW
    else:
        claim.status = ClaimStatus.COMPLETED

    db.commit()
    db.refresh(claim)
    return decision_payload


def _recalculate_approved_amount(
    claim_amount: float,
    documents: dict[str, Any],
    rejected_items: list[dict[str, Any]],
) -> tuple[float, dict[str, float]]:
    """Recompute approved amount after removing LLM-rejected items from the bill.

    The LLM determines *what* to reject; this function deterministically
    computes *how much* to deduct based on the bill data and policy rules.
    """
    from app.services.policy_loader import load_policy_terms

    policy = load_policy_terms()
    bill = documents.get("bill") or {}

    # Total cost of rejected items (from LLM analysis)
    rejected_total = sum(item.get("amount", 0) for item in rejected_items)

    # Subtract rejected items from claim amount
    adjusted_base = claim_amount - rejected_total
    if adjusted_base <= 0:
        return 0.0, {}

    # Apply per-claim cap
    per_claim_limit = policy["coverage_details"]["per_claim_limit"]
    adjusted_base = min(adjusted_base, per_claim_limit)

    # Apply consultation copay on remaining consultation fees
    copay_pct = policy["coverage_details"]["consultation_fees"]["copay_percentage"]
    normalized_bill = {
        str(k).lower().strip().replace(" ", "_").replace("-", "_"): v
        for k, v in bill.items()
    }
    has_consultation = any(
        any(sub in k for sub in ("consultation", "root_canal", "rootcanal"))
        for k in normalized_bill
    )

    copay = 0.0
    deductions: dict[str, float] = {}
    if has_consultation:
        # Find total consultation amount in the bill
        consultation_amount = 0.0
        for k, v in normalized_bill.items():
            if any(sub in k for sub in ("consultation", "root_canal", "rootcanal")):
                try:
                    consultation_amount += float(v)
                except (ValueError, TypeError):
                    pass
        # Copay applies to the consultation portion that is still approved
        copayable = min(consultation_amount, adjusted_base)
        copay = round(copayable * copay_pct / 100, 2)
        if copay > 0:
            deductions["copay"] = copay

    approved = round(max(adjusted_base - copay, 0), 2)
    return approved, deductions


def parse_structured_documents_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid structured_documents JSON: {exc}") from exc
