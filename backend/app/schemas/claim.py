from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ClaimStatusEnum(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class DecisionType(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PARTIAL = "PARTIAL"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ClaimCreateResponse(BaseModel):
    claim_id: UUID
    claim_number: str
    status: ClaimStatusEnum
    message: str = "Claim submitted. Poll GET /claims/{claim_id} for status."


class RuleResultSchema(BaseModel):
    rule_name: str | None = None
    passed: bool
    reason_code: str | None = None
    note: str | None = None


class DecisionOutputSchema(BaseModel):
    claim_id: str
    claim_number: str | None = None
    decision: DecisionType | str
    approved_amount: float = 0
    rejection_reasons: list[str] = Field(default_factory=list)
    rejected_items: list[str] = Field(default_factory=list)
    deductions: dict[str, float] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    confidence_score: float
    notes: str | None = None
    next_steps: str | None = None
    rule_results: list[RuleResultSchema] = Field(default_factory=list)
    cashless_approved: bool | None = None
    network_discount: float | None = None
    medical_necessity_established: bool | None = None
    exclusions_detected: list[str] = Field(default_factory=list)


class ClaimStatusResponse(BaseModel):
    claim_id: UUID
    claim_number: str
    status: ClaimStatusEnum
    member_id: str
    member_name: str
    treatment_date: str
    claim_amount: float
    created_at: datetime
    updated_at: datetime | None = None
    error_message: str | None = None
    decision: DecisionOutputSchema | None = None
    extracted_fields: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str