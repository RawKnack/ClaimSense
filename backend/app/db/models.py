import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from pgvector.sqlalchemy import Vector


class ClaimStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, native_enum=False),
        default=ClaimStatus.PENDING,
        index=True,
    )
    member_id: Mapped[str] = mapped_column(String(64), index=True)
    member_name: Mapped[str] = mapped_column(String(255))
    member_join_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    treatment_date: Mapped[str] = mapped_column(String(32))
    claim_amount: Mapped[float] = mapped_column(Float)
    hospital: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cashless_request: Mapped[bool] = mapped_column(default=False)
    previous_claims_same_day: Mapped[int | None] = mapped_column(nullable=True)
    metadata_extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    document_paths: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ExtractedFields(Base):
    __tablename__ = "extracted_fields"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), index=True, unique=True
    )
    ocr_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extracted_data: Mapped[dict] = mapped_column(JSON)
    field_confidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), index=True, unique=True
    )
    decision_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PolicyEmbedding(Base):
    __tablename__ = "policy_embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chunk_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(128))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
