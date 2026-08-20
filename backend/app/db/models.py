"""SQLAlchemy models.

Design notes:

* Dataset records keep their **stable source ID** (P001, V014, C002, F003) in
  `record_id`. The primary key is a surrogate UUID so the same stable ID can
  exist once per policy version — versioning without renumbering the dataset.
* Every policy/violation row carries `compound`, `phase`, `effective_from` and
  `effective_until`. NULL compound/phase means "applies everywhere"; that is
  what the current v1.0 dataset loads as, because Palm Hills has not yet
  supplied per-compound rules.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import get_settings

_settings = get_settings()
EMBEDDING_DIM = _settings.embedding_dim

# When pgvector is unavailable the column is not declared at all, so
# create_all() never emits DDL the server cannot execute. Retrieval falls
# back to trigram-only ranking. See Settings.vector_enabled.
VECTOR_ENABLED = _settings.vector_enabled


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    version: Mapped[str] = mapped_column(String(32), unique=True)
    source_document: Mapped[str] = mapped_column(String(512))
    #: Hash of the source PDF, carried in the dataset's own metadata.
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    #: Hash of the dataset *file* as it was when ingested. Lets the API tell
    #: whether it is still serving what the file now says - see
    #: `app.services.dataset_state`.
    dataset_sha256: Mapped[str | None] = mapped_column(String(64))
    issuer: Mapped[str] = mapped_column(String(256))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    counts: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PolicyCategory(Base):
    __tablename__ = "policy_categories"

    category_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    category_en: Mapped[str] = mapped_column(String(256))
    category_ar: Mapped[str] = mapped_column(String(256))


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (
        UniqueConstraint("record_id", "version_id", name="uq_policy_record_version"),
        Index("ix_policies_category", "category_id"),
        Index("ix_policies_scope", "compound", "phase"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    record_id: Mapped[str] = mapped_column(String(32))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policy_versions.id", ondelete="CASCADE"))
    category_id: Mapped[str] = mapped_column(ForeignKey("policy_categories.category_id"))

    rule_en: Mapped[str] = mapped_column(Text)
    rule_ar: Mapped[str] = mapped_column(Text)
    src_en: Mapped[str] = mapped_column(String(16))
    src_ar: Mapped[str] = mapped_column(String(16))
    page_en: Mapped[int | None] = mapped_column(Integer)
    page_ar: Mapped[int | None] = mapped_column(Integer)

    compound: Mapped[str | None] = mapped_column(String(128))
    phase: Mapped[str | None] = mapped_column(String(128))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)

    search_text: Mapped[str] = mapped_column(Text)
    if VECTOR_ENABLED:
        embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class Violation(Base):
    __tablename__ = "violations"
    __table_args__ = (
        UniqueConstraint("record_id", "version_id", name="uq_violation_record_version"),
        Index("ix_violations_category", "category_id"),
        Index("ix_violations_scope", "compound", "phase"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    record_id: Mapped[str] = mapped_column(String(32))
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policy_versions.id", ondelete="CASCADE"))
    category_id: Mapped[str] = mapped_column(ForeignKey("policy_categories.category_id"))

    violation_en: Mapped[str] = mapped_column(Text)
    violation_ar: Mapped[str] = mapped_column(Text)
    penalty_egp: Mapped[int] = mapped_column(Integer)
    action_en: Mapped[str] = mapped_column(Text)
    action_ar: Mapped[str] = mapped_column(Text)
    related_policy_ids: Mapped[list] = mapped_column(JSONB, default=list)
    page_en: Mapped[int | None] = mapped_column(Integer)
    page_ar: Mapped[int | None] = mapped_column(Integer)

    compound: Mapped[str | None] = mapped_column(String(128))
    phase: Mapped[str | None] = mapped_column(String(128))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)

    search_text: Mapped[str] = mapped_column(Text)
    if VECTOR_ENABLED:
        embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)


class Contact(Base):
    __tablename__ = "contacts"

    record_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(256))
    name_ar: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(64))
    phone: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(256))
    hours: Mapped[str | None] = mapped_column(String(128))
    compound: Mapped[str | None] = mapped_column(String(128))
    phase: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="unconfigured")
    pending_fields: Mapped[list] = mapped_column(JSONB, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Facility(Base):
    __tablename__ = "facilities"

    record_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_en: Mapped[str] = mapped_column(String(256))
    name_ar: Mapped[str] = mapped_column(String(256))
    facility_type: Mapped[str] = mapped_column(String(64))
    compound: Mapped[str | None] = mapped_column(String(128))
    phase: Mapped[str | None] = mapped_column(String(128))
    location_note: Mapped[str | None] = mapped_column(Text)
    hours: Mapped[str | None] = mapped_column(String(128))
    hours_source: Mapped[str | None] = mapped_column(String(64))
    restrictions_en: Mapped[list] = mapped_column(JSONB, default=list)
    restrictions_ar: Mapped[list] = mapped_column(JSONB, default=list)
    related_policy_ids: Mapped[list] = mapped_column(JSONB, default=list)
    contact_id: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="unconfigured")
    pending_fields: Mapped[list] = mapped_column(JSONB, default=list)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_created", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[str | None] = mapped_column(String(128))
    session_id: Mapped[str | None] = mapped_column(String(128))
    query: Mapped[str] = mapped_column(Text)
    detected_language: Mapped[str] = mapped_column(String(16))
    intent: Mapped[str] = mapped_column(String(32))
    compound: Mapped[str | None] = mapped_column(String(128))
    phase: Mapped[str | None] = mapped_column(String(128))
    retrieved_record_ids: Mapped[list] = mapped_column(JSONB, default=list)
    policy_version: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column()
    confidence_band: Mapped[str] = mapped_column(String(16))
    answer: Mapped[str] = mapped_column(Text)
    llm_provider: Mapped[str] = mapped_column(String(32))
    llm_model: Mapped[str | None] = mapped_column(String(64))
    integrity_guard_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    ticket_id: Mapped[str | None] = mapped_column(String(64))


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(128))
    query: Mapped[str] = mapped_column(Text)
    detected_language: Mapped[str] = mapped_column(String(16))
    compound: Mapped[str | None] = mapped_column(String(128))
    phase: Mapped[str | None] = mapped_column(String(128))
    retrieved_records: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column()
    reason: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="open")
    assigned_team: Mapped[str | None] = mapped_column(String(64))
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Complaint(Base):
    """A resident raising a problem with the community or its services.

    Deliberately its own table rather than a flavour of `ViolationReport` or
    `Ticket`. The three are different acts with different consequences:

    * a **violation report** accuses somebody, and stays `reported` until staff
      verify it - see the status comment on `ViolationReport`;
    * a **ticket** is opened by the assistant when it could not verify an
      answer, and carries retrieval internals staff need;
    * a **complaint** is the resident's own grievance about service. Nobody is
      accused and nothing is retrieved, so folding it into either of the others
      would either imply an accusation or bury it among assistant failures.
    """

    __tablename__ = "complaints"
    __table_args__ = (Index("ix_complaints_user", "user_id"),)

    complaint_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text)
    compound: Mapped[str | None] = mapped_column(String(128))
    phase: Mapped[str | None] = mapped_column(String(128))
    location_text: Mapped[str | None] = mapped_column(Text)
    # Optional: a resident may want a call back, or may not.
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="open")
    assigned_team: Mapped[str | None] = mapped_column(String(64))
    resolution: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ViolationReport(Base):
    __tablename__ = "violation_reports"

    report_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(String(128))
    category_id: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    location_text: Mapped[str | None] = mapped_column(Text)
    compound: Mapped[str | None] = mapped_column(String(128))
    phase: Mapped[str | None] = mapped_column(String(128))
    attachments: Mapped[list] = mapped_column(JSONB, default=list)
    # 'reported' until a human confirms it. AI classification is a hint for
    # staff only and never promotes a report to 'verified'.
    status: Mapped[str] = mapped_column(String(32), default="reported")
    suggested_violation_id: Mapped[str | None] = mapped_column(String(32))
    suggested_confidence: Mapped[float | None] = mapped_column()
    ai_classification: Mapped[dict] = mapped_column(JSONB, default=dict)
    verified_violation_id: Mapped[str | None] = mapped_column(String(32))
    verified_by: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


__all__ = [
    "Base",
    "PolicyVersion",
    "PolicyCategory",
    "Policy",
    "Violation",
    "Contact",
    "Facility",
    "AuditLog",
    "Ticket",
    "ViolationReport",
]
