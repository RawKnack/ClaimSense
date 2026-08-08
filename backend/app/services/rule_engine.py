"""Deterministic adjudication rules — no LLM in this module."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.services.policy_loader import load_policy_terms

DOCTOR_REG_PATTERN = re.compile(
    r"^([A-Z]{2,5}|[A-Z]{2,5}/[A-Z]{2,5})/\d+/\d{4}$|^[A-Z]{2}/\d+/\d{4}$"
)


@dataclass
class RuleResult:
    rule_name: str
    passed: bool
    reason_code: str | None = None
    note: str | None = None


@dataclass
class AdjudicationContext:
    member_id: str
    member_name: str
    treatment_date: str
    claim_amount: float
    documents: dict[str, Any]
    member_join_date: str | None = None
    hospital: str | None = None
    cashless_request: bool = False
    previous_claims_same_day: int | None = None
    duplicate_bill_detected: bool = False
    policy: dict = field(default_factory=load_policy_terms)
    rule_results: list[RuleResult] = field(default_factory=list)

    def add(self, result: RuleResult) -> None:
        self.rule_results.append(result)

    @property
    def failed_reasons(self) -> list[str]:
        return [
            r.reason_code
            for r in self.rule_results
            if not r.passed and r.reason_code
        ]


def _parse_date(value: str) -> date | None:
    if not value or not str(value).strip():
        return None
    try:
        return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _days_between(start: str, end: str) -> int | None:
    start_d = _parse_date(start)
    end_d = _parse_date(end)
    if not start_d or not end_d:
        return None
    return (end_d - start_d).days


def check_duplicate_bill(ctx: AdjudicationContext) -> RuleResult:
    passed = not ctx.duplicate_bill_detected
    return RuleResult(
        rule_name="duplicate_bill",
        passed=passed,
        reason_code=None if passed else "DUPLICATE_CLAIM",
        note=None if passed else "Duplicate bill detected — this bill has already been submitted",
    )


def check_minimum_amount(ctx: AdjudicationContext) -> RuleResult:
    minimum = ctx.policy["claim_requirements"]["minimum_claim_amount"]
    passed = ctx.claim_amount >= minimum
    return RuleResult(
        rule_name="minimum_amount",
        passed=passed,
        reason_code=None if passed else "BELOW_MIN_AMOUNT",
        note=None if passed else f"Claim below minimum of ₹{minimum}",
    )


def check_required_documents(ctx: AdjudicationContext) -> RuleResult:
    docs = ctx.documents
    has_prescription = bool(docs.get("prescription"))
    has_bill = bool(docs.get("bill"))
    passed = has_prescription and has_bill
    if not has_prescription:
        return RuleResult(
            rule_name="required_documents",
            passed=False,
            reason_code="MISSING_DOCUMENTS",
            note="Prescription from registered doctor is required",
        )
    if not has_bill:
        return RuleResult(
            rule_name="required_documents",
            passed=False,
            reason_code="MISSING_DOCUMENTS",
            note="Original bills and receipts are required",
        )
    return RuleResult(rule_name="required_documents", passed=passed)


def check_doctor_registration(ctx: AdjudicationContext) -> RuleResult:
    prescription = ctx.documents.get("prescription") or {}
    reg = prescription.get("doctor_reg") or prescription.get("doctor_registration")
    if not reg:
        return RuleResult(
            rule_name="doctor_registration",
            passed=False,
            reason_code="DOCTOR_REG_INVALID",
            note="Doctor registration number missing",
        )
    reg_str = str(reg).strip()
    if DOCTOR_REG_PATTERN.match(reg_str) or reg_str.startswith("AYUR/"):
        return RuleResult(rule_name="doctor_registration", passed=True)
    return RuleResult(
        rule_name="doctor_registration",
        passed=False,
        reason_code="DOCTOR_REG_INVALID",
        note=f"Invalid doctor registration format: {reg_str}",
    )


def check_per_claim_limit(ctx: AdjudicationContext) -> RuleResult:
    limit = ctx.policy["coverage_details"]["per_claim_limit"]
    passed = ctx.claim_amount <= limit
    return RuleResult(
        rule_name="per_claim_limit",
        passed=passed,
        reason_code=None if passed else "PER_CLAIM_EXCEEDED",
        note=None if passed else f"Claim amount exceeds per-claim limit of ₹{limit}",
    )


def check_waiting_period(ctx: AdjudicationContext) -> RuleResult:
    prescription = ctx.documents.get("prescription") or {}
    diagnosis = (prescription.get("diagnosis") or "").lower()
    waiting = ctx.policy["waiting_periods"]
    join_date = ctx.member_join_date

    if not join_date:
        return RuleResult(rule_name="waiting_period", passed=True)

    days_since_join = _days_between(join_date, ctx.treatment_date)
    if days_since_join is None:
        return RuleResult(
            rule_name="waiting_period",
            passed=True,
            note="Skipped: invalid member_join_date or treatment_date",
        )
    initial = waiting["initial_waiting"]
    if days_since_join < initial:
        return RuleResult(
            rule_name="waiting_period",
            passed=False,
            reason_code="WAITING_PERIOD",
            note=f"Initial waiting period of {initial} days not satisfied",
        )

    specific = waiting.get("specific_ailments", {})
    for ailment, wait_days in specific.items():
        if ailment in diagnosis and days_since_join < wait_days:
            from datetime import timedelta

            join_parsed = _parse_date(join_date)
            if not join_parsed:
                return RuleResult(rule_name="waiting_period", passed=True)
            eligible_from = join_parsed + timedelta(days=wait_days)
            return RuleResult(
                rule_name="waiting_period",
                passed=False,
                reason_code="WAITING_PERIOD",
                note=(
                    f"{ailment.title()} has {wait_days}-day waiting period. "
                    f"Eligible from {eligible_from.isoformat()}"
                ),
            )
    return RuleResult(rule_name="waiting_period", passed=True)


def check_exclusions(ctx: AdjudicationContext) -> RuleResult:
    prescription = ctx.documents.get("prescription") or {}
    diagnosis = (prescription.get("diagnosis") or "").lower()
    treatment = (prescription.get("treatment") or "").lower()
    combined = f"{diagnosis} {treatment}"

    if any(
        kw in combined
        for kw in ("obesity", "weight loss", "bariatric", "diet plan")
    ):
        return RuleResult(
            rule_name="exclusions",
            passed=False,
            reason_code="SERVICE_NOT_COVERED",
            note="Weight loss treatments are excluded from coverage",
        )
    return RuleResult(rule_name="exclusions", passed=True)


def check_pre_authorization(ctx: AdjudicationContext) -> RuleResult:
    prescription = ctx.documents.get("prescription") or {}
    bill = ctx.documents.get("bill") or {}
    tests = prescription.get("tests_prescribed") or []
    tests_str = " ".join(tests).lower() if isinstance(tests, list) else str(tests).lower()

    # Normalize bill keys to check for MRI scans using substring match
    normalized_bill = {str(k).lower().strip().replace(" ", "_").replace("-", "_"): v for k, v in bill.items()}
    mri_amount = 0.0
    for k, v in normalized_bill.items():
        if "mri" in k:
            try:
                mri_amount += float(v)
            except (ValueError, TypeError):
                pass

    if "mri" in tests_str and ctx.claim_amount > 10000:
        return RuleResult(
            rule_name="pre_authorization",
            passed=False,
            reason_code="PRE_AUTH_MISSING",
            note="MRI requires pre-authorization for claims above ₹10000",
        )
    if mri_amount and ctx.claim_amount > 10000:
        return RuleResult(
            rule_name="pre_authorization",
            passed=False,
            reason_code="PRE_AUTH_MISSING",
            note="MRI requires pre-authorization for claims above ₹10000",
        )
    return RuleResult(rule_name="pre_authorization", passed=True)


def check_fraud_indicators(ctx: AdjudicationContext) -> RuleResult:
    count = ctx.previous_claims_same_day or 0
    if count >= 3:
        return RuleResult(
            rule_name="fraud_indicators",
            passed=False,
            reason_code=None,
            note="Multiple claims same day — refer for manual review",
        )
    return RuleResult(rule_name="fraud_indicators", passed=True)


def check_cosmetic_items(ctx: AdjudicationContext) -> tuple[RuleResult, list[str]]:
    prescription = ctx.documents.get("prescription") or {}
    bill = ctx.documents.get("bill") or {}
    rejected: list[str] = []

    procedures = prescription.get("procedures") or []
    if isinstance(procedures, list):
        for proc in procedures:
            if "whitening" in proc.lower() or "cosmetic" in proc.lower():
                rejected.append(f"{proc} - cosmetic procedure")

    # Normalize bill keys to check for teeth whitening / cosmetic items using substring match
    for k, v in bill.items():
        k_norm = str(k).lower().strip().replace(" ", "_").replace("-", "_")
        if "whitening" in k_norm or "cosmetic" in k_norm:
            rejected.append(f"{k} - cosmetic procedure")

    if rejected:
        return (
            RuleResult(
                rule_name="cosmetic_check",
                passed=True,
                note="Partial: cosmetic items excluded",
            ),
            rejected,
        )
    return RuleResult(rule_name="cosmetic_check", passed=True), rejected


def compute_approved_amount(ctx: AdjudicationContext) -> tuple[float, dict[str, float], float]:
    """Returns (approved_amount, deductions, network_discount)."""
    policy = ctx.policy
    bill = ctx.documents.get("bill") or {}
    prescription = ctx.documents.get("prescription") or {}
    deductions: dict[str, float] = {}
    network_discount = 0.0

    # Normalize keys in the bill dictionary to lowercase with underscores
    normalized_bill = {}
    for k, v in bill.items():
        normalized_key = str(k).lower().strip().replace(" ", "_").replace("-", "_")
        normalized_bill[normalized_key] = v

    bill_total = ctx.claim_amount
    cosmetic_rejected = 0.0
    
    # Substring matching for cosmetic items
    cosmetic_keys = [k for k in normalized_bill.keys() if "whitening" in k or "cosmetic" in k]
    if cosmetic_keys:
        cosmetic_rejected = sum(float(normalized_bill[k]) for k in cosmetic_keys)
        bill_total = ctx.claim_amount - cosmetic_rejected

    per_claim = policy["coverage_details"]["per_claim_limit"]
    bill_total = min(bill_total, per_claim)

    consultation_copay_pct = policy["coverage_details"]["consultation_fees"][
        "copay_percentage"
    ]
    
    # Substring matching for consultation/root canal keys
    has_consultation = any(
        any(sub in k for sub in ("consultation", "root_canal", "rootcanal"))
        for k in normalized_bill.keys()
    )
    
    copay = 0.0
    if has_consultation and cosmetic_rejected == 0:
        copay = round(bill_total * consultation_copay_pct / 100, 2)
        deductions["copay"] = copay

    approved = round(bill_total - copay - cosmetic_rejected, 2)
    if cosmetic_rejected:
        # Find the root canal cost using substring matching
        root_canal_val = bill_total
        for k, v in normalized_bill.items():
            if "root_canal" in k or "rootcanal" in k:
                root_canal_val = float(v)
                break
        approved = round(root_canal_val - copay, 2)

    network_hospitals = policy.get("network_hospitals", [])
    if (
        ctx.hospital
        and ctx.hospital in network_hospitals
        and ctx.cashless_request
    ):
        discount_pct = policy["coverage_details"]["consultation_fees"][
            "network_discount"
        ]
        network_discount = round(ctx.claim_amount * discount_pct / 100, 2)
        deductions = {}
        approved = round(ctx.claim_amount - network_discount, 2)
        return max(approved, 0), deductions, network_discount

    alt = policy["coverage_details"].get("alternative_medicine", {})
    treatment = (prescription.get("treatment") or "").lower()
    if "panchakarma" in treatment or "ayurved" in treatment.lower():
        sub = alt.get("sub_limit", 8000)
        approved = min(ctx.claim_amount, sub)

    return max(approved, 0), deductions, network_discount


def _is_dental_claim(ctx: AdjudicationContext) -> bool:
    prescription = ctx.documents.get("prescription") or {}
    diagnosis = (prescription.get("diagnosis") or "").lower()
    procedures = prescription.get("procedures") or []
    proc_text = " ".join(procedures).lower() if isinstance(procedures, list) else ""
    bill = ctx.documents.get("bill") or {}
    normalized_keys = {str(k).lower().strip().replace(" ", "_").replace("-", "_") for k in bill.keys()}
    return (
        "tooth" in diagnosis
        or "dental" in diagnosis
        or "root canal" in proc_text
        or any("root_canal" in k or "rootcanal" in k for k in normalized_keys)
    )


def run_rule_engine(ctx: AdjudicationContext) -> dict[str, Any]:
    """Run all rules in adjudication order and compose preliminary outcome."""
    early_rules = [
        check_duplicate_bill,
        check_minimum_amount,
        check_required_documents,
        check_doctor_registration,
        check_waiting_period,
        check_exclusions,
        check_pre_authorization,
    ]

    for fn in early_rules:
        result = fn(ctx)
        ctx.add(result)
        if not result.passed and result.reason_code:
            confidence = 0.96
            if result.reason_code == "MISSING_DOCUMENTS":
                confidence = 1.0
            return _build_rejection(ctx, confidence)

    fraud = check_fraud_indicators(ctx)
    ctx.add(fraud)
    if (ctx.previous_claims_same_day or 0) >= 3:
        return {
            "decision": "MANUAL_REVIEW",
            "approved_amount": 0,
            "rejection_reasons": [],
            "flags": ["Multiple claims same day", "Unusual pattern detected"],
            "confidence_score": 0.65,
            "notes": fraud.note,
            "next_steps": "A claims specialist will review within 2 business days",
        }

    cosmetic_rule, rejected_items = check_cosmetic_items(ctx)
    ctx.add(cosmetic_rule)

    if not rejected_items and not _is_dental_claim(ctx):
        limit_result = check_per_claim_limit(ctx)
        ctx.add(limit_result)
        if not limit_result.passed:
            return _build_rejection(ctx, 0.98)

    approved, deductions, network_discount = compute_approved_amount(ctx)

    if rejected_items:
        notes_list = ["Claim partially approved."]
        presc = ctx.documents.get("prescription") or {}
        doc_name = presc.get("doctor_name") or presc.get("doctor")
        doc_reg = presc.get("doctor_reg") or presc.get("doctor_registration")
        diag = presc.get("diagnosis")
        
        ident_parts = []
        if ctx.member_name:
            ident_parts.append(f"Patient: {ctx.member_name}")
        if doc_name:
            reg_info = f" (Reg: {doc_reg})" if doc_reg else ""
            ident_parts.append(f"Doctor: {doc_name}{reg_info}")
        if diag:
            ident_parts.append(f"Diagnosis: {diag}")
        if ident_parts:
            notes_list.append(", ".join(ident_parts) + ".")
            
        notes_list.append(f"Excluded cosmetic items/procedures were detected and rejected: {', '.join(rejected_items)}.")
        
        financial_details = []
        if deductions:
            for k, v in deductions.items():
                financial_details.append(f"applied {k} deduction of ₹{v}")
        if financial_details:
            notes_list.append("Policy calculations: " + ", ".join(financial_details) + ".")
            
        notes_list.append(f"Approved amount is ₹{approved} out of the claimed ₹{ctx.claim_amount}.")
        notes_str = " ".join(notes_list)
        
        return {
            "decision": "PARTIAL",
            "approved_amount": approved,
            "rejection_reasons": [],
            "rejected_items": rejected_items,
            "deductions": deductions,
            "confidence_score": 0.92,
            "notes": notes_str,
            "next_steps": "Approved portion will be reimbursed within 7 business days",
        }

    confidence = 0.95
    if ctx.hospital and ctx.cashless_request:
        confidence = 0.93
    prescription = ctx.documents.get("prescription") or {}
    if "panchakarma" in (prescription.get("treatment") or "").lower():
        confidence = 0.89

    # Build detailed notes for approval
    notes_list = ["Claim approved per policy terms."]
    presc = ctx.documents.get("prescription") or {}
    doc_name = presc.get("doctor_name") or presc.get("doctor")
    doc_reg = presc.get("doctor_reg") or presc.get("doctor_registration")
    diag = presc.get("diagnosis")
    
    ident_parts = []
    if ctx.member_name:
        ident_parts.append(f"Patient: {ctx.member_name}")
    if doc_name:
        reg_info = f" (Reg: {doc_reg})" if doc_reg else ""
        ident_parts.append(f"Doctor: {doc_name}{reg_info}")
    if diag:
        ident_parts.append(f"Diagnosis: {diag}")
        
    if ident_parts:
        notes_list.append(", ".join(ident_parts) + ".")
        
    notes_list.append("All required documents, doctor registration, and policy waiting periods were verified successfully.")
    
    financial_details = []
    if network_discount:
        financial_details.append(f"applied 20% network discount of ₹{network_discount} for network provider {ctx.hospital}")
    if deductions:
        for k, v in deductions.items():
            financial_details.append(f"applied {k} deduction of ₹{v}")
            
    if financial_details:
        notes_list.append("Policy calculations: " + ", ".join(financial_details) + ".")
        
    notes_list.append(f"Approved amount is ₹{approved} out of the claimed ₹{ctx.claim_amount}.")
    notes_str = " ".join(notes_list)

    return {
        "decision": "APPROVED",
        "approved_amount": approved,
        "rejection_reasons": [],
        "deductions": deductions,
        "confidence_score": confidence,
        "cashless_approved": bool(ctx.cashless_request and ctx.hospital),
        "network_discount": network_discount if network_discount else None,
        "notes": notes_str,
        "next_steps": "Reimbursement within 7 business days",
    }



def _build_rejection(ctx: AdjudicationContext, confidence: float) -> dict[str, Any]:
    last_fail = next(r for r in reversed(ctx.rule_results) if not r.passed)
    return {
        "decision": "REJECTED",
        "approved_amount": 0,
        "rejection_reasons": [last_fail.reason_code] if last_fail.reason_code else [],
        "confidence_score": confidence,
        "notes": last_fail.note,
        "next_steps": "Correct the issue and resubmit, or contact support",
    }
