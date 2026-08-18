"""Audit logging.

Every policy answer is recorded with the source record IDs that produced it, so
the question "what did the assistant tell this resident, and from which
records?" always has an answer. This matters more than usual here because the
assistant quotes fines.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.services.answer import GeneratedAnswer
from app.services.confidence import ConfidenceAssessment
from app.services.retrieval import RetrievalResult


def write_audit(
    db: Session,
    *,
    query: str,
    detected_language: str,
    intent: str,
    compound: str | None,
    phase: str | None,
    retrieval: RetrievalResult,
    confidence: ConfidenceAssessment,
    answer: GeneratedAnswer,
    user_id: str | None = None,
    session_id: str | None = None,
    escalated: bool = False,
    ticket_id: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        id=uuid.uuid4(),
        user_id=user_id,
        session_id=session_id,
        query=query,
        detected_language=detected_language,
        intent=intent,
        compound=compound,
        phase=phase,
        retrieved_record_ids=retrieval.record_ids,
        policy_version=retrieval.policy_version,
        confidence=confidence.score,
        confidence_band=confidence.band,
        answer=answer.text,
        llm_provider=answer.generator,
        llm_model=answer.model,
        integrity_guard_triggered=answer.integrity_guard_triggered,
        escalated=escalated,
        ticket_id=ticket_id,
    )
    db.add(entry)
    db.flush()
    return entry
