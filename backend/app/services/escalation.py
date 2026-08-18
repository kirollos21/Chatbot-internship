"""Human escalation.

When the assistant cannot verify an answer it does not guess — it opens a
ticket for Community Management and tells the resident. Residents see the
ticket ID and status only; retrieval internals stay on the staff side.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Ticket
from app.services.confidence import ConfidenceAssessment
from app.services.retrieval import RetrievalResult

OPEN = "open"
IN_REVIEW = "in_review"
AWAITING_USER = "awaiting_user"
RESOLVED = "resolved"
CLOSED = "closed"

VALID_STATUSES = {OPEN, IN_REVIEW, AWAITING_USER, RESOLVED, CLOSED}

_TEAM_BY_REASON = {
    "low_confidence": "community_management",
    "compound_unknown": "community_management",
    "resident_request": "community_management",
}


def new_ticket_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"TKT-{stamp}-{secrets.token_hex(3).upper()}"


def create_ticket(
    db: Session,
    *,
    query: str,
    detected_language: str,
    confidence: ConfidenceAssessment,
    retrieval: RetrievalResult,
    reason: str = "low_confidence",
    compound: str | None = None,
    phase: str | None = None,
    user_id: str | None = None,
) -> Ticket:
    ticket = Ticket(
        ticket_id=new_ticket_id(),
        user_id=user_id,
        query=query,
        detected_language=detected_language,
        compound=compound,
        phase=phase,
        retrieved_records=[
            {"record_id": r.record_id, "kind": r.kind, "score": r.score}
            for r in retrieval.records
        ],
        confidence=confidence.score,
        reason=reason,
        status=OPEN,
        assigned_team=_TEAM_BY_REASON.get(reason, "community_management"),
    )
    db.add(ticket)
    db.flush()
    return ticket
