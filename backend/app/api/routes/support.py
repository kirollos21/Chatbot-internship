"""Support tickets and resident violation reports."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import authenticated
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import Complaint, Ticket, ViolationReport
from app.schemas.support import (
    ComplaintCategoryOut,
    ComplaintCreate,
    ComplaintOut,
    ComplaintStatusUpdate,
    TicketCreate,
    TicketOut,
    TicketStatusUpdate,
    ViolationReportCreate,
    ViolationReportOut,
)
from app.services import complaints as complaints_service
from app.services import escalation as escalation_service
from app.services import retrieval as retrieval_service
from app.services.confidence import MEDIUM, ConfidenceAssessment
from app.services.intent import POLICY_QUESTION, classify_intent
from app.services.language import detect_language

router = APIRouter(tags=["support"], dependencies=[Depends(authenticated)])

# Magic bytes for the image types we accept. Content-Type alone is caller-supplied.
_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",
}


# --------------------------------------------------------------------- tickets

@router.post("/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)) -> TicketOut:
    ticket = escalation_service.create_ticket(
        db,
        query=payload.query,
        detected_language=payload.detected_language,
        confidence=ConfidenceAssessment(0.0, MEDIUM, ["resident_request"]),
        retrieval=retrieval_service.RetrievalResult(),
        reason=payload.reason,
        compound=payload.compound,
        phase=payload.phase,
        user_id=payload.user_id,
    )
    db.commit()
    return TicketOut.model_validate(ticket, from_attributes=True)


@router.get("/tickets", response_model=list[TicketOut])
def list_tickets(
    db: Session = Depends(get_db),
    user_id: str | None = None,
    status_filter: str | None = None,
) -> list[TicketOut]:
    stmt = select(Ticket)
    if user_id:
        stmt = stmt.where(Ticket.user_id == user_id)
    if status_filter:
        stmt = stmt.where(Ticket.status == status_filter)
    rows = db.execute(stmt.order_by(Ticket.created_at.desc()).limit(200)).scalars()
    return [TicketOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str, db: Session = Depends(get_db)) -> TicketOut:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return TicketOut.model_validate(ticket, from_attributes=True)


@router.patch("/tickets/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: str, payload: TicketStatusUpdate, db: Session = Depends(get_db)
) -> TicketOut:
    if payload.status not in escalation_service.VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status must be one of {sorted(escalation_service.VALID_STATUSES)}",
        )
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found.")

    ticket.status = payload.status
    if payload.resolution is not None:
        ticket.resolution = payload.resolution
    if payload.assigned_team is not None:
        ticket.assigned_team = payload.assigned_team
    if payload.status in (escalation_service.RESOLVED, escalation_service.CLOSED):
        ticket.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return TicketOut.model_validate(ticket, from_attributes=True)


# ---------------------------------------------------------------- reports

def _new_report_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"RPT-{stamp}-{secrets.token_hex(3).upper()}"


@router.post("/reports", response_model=ViolationReportOut, status_code=status.HTTP_201_CREATED)
def create_report(payload: ViolationReportCreate, db: Session = Depends(get_db)) -> ViolationReportOut:
    """Record a resident-reported violation.

    The retrieval hit is stored as a *suggestion* for staff triage only. The
    report's status stays `reported` — a person has to verify it before it
    becomes an enforced violation. Nothing here accuses anyone.
    """
    detection = detect_language(payload.description)
    intent_result = classify_intent(payload.description)
    retrieval = retrieval_service.search(
        db,
        payload.description,
        intent=POLICY_QUESTION,
        category_hints=intent_result.category_hints,
        compound=payload.compound,
        phase=payload.phase,
    )
    top_violation = retrieval.violations[0] if retrieval.violations else None

    report = ViolationReport(
        report_id=_new_report_id(),
        user_id=payload.user_id,
        category_id=payload.category_id or (top_violation.category_id if top_violation else None),
        description=payload.description,
        location_text=payload.location_text,
        compound=payload.compound,
        phase=payload.phase,
        attachments=[],
        status="reported",
        suggested_violation_id=top_violation.record_id if top_violation else None,
        suggested_confidence=top_violation.score if top_violation else None,
        ai_classification={
            "detected_language": detection.language,
            "category_hints": intent_result.category_hints,
            "candidates": [
                {"record_id": r.record_id, "score": r.score} for r in retrieval.violations[:3]
            ],
            "note": "Suggestion only. Not an enforcement decision.",
        },
    )
    db.add(report)
    db.commit()
    return ViolationReportOut.model_validate(report, from_attributes=True)


@router.post("/reports/{report_id}/attachments", response_model=ViolationReportOut)
def attach_evidence(
    report_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
) -> ViolationReportOut:
    settings = get_settings()
    report = db.get(ViolationReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    if file.content_type not in settings.allowed_upload_type_set:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Allowed: {sorted(settings.allowed_upload_type_set)}",
        )

    content = file.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the maximum upload size.")
    if not content:
        raise HTTPException(status_code=422, detail="Empty file.")

    # Content-Type is caller-supplied; verify the bytes actually match.
    if not any(content.startswith(magic) for magic in _MAGIC):
        raise HTTPException(status_code=415, detail="File content does not match a supported image type.")

    digest = hashlib.sha256(content).hexdigest()
    attachments = list(report.attachments or [])
    attachments.append(
        {
            "filename": (file.filename or "upload").rsplit("/", 1)[-1].rsplit("\\", 1)[-1],
            "content_type": file.content_type,
            "size_bytes": len(content),
            "sha256": digest,
            # Binary storage is not wired up yet - see README "Open items".
            "storage": "not_persisted",
        }
    )
    report.attachments = attachments
    db.commit()
    return ViolationReportOut.model_validate(report, from_attributes=True)


@router.get("/reports", response_model=list[ViolationReportOut])
def list_reports(
    db: Session = Depends(get_db),
    user_id: str | None = None,
    status_filter: str | None = None,
) -> list[ViolationReportOut]:
    stmt = select(ViolationReport)
    if user_id:
        stmt = stmt.where(ViolationReport.user_id == user_id)
    if status_filter:
        stmt = stmt.where(ViolationReport.status == status_filter)
    rows = db.execute(stmt.order_by(ViolationReport.created_at.desc()).limit(200)).scalars()
    return [ViolationReportOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/reports/{report_id}", response_model=ViolationReportOut)
def get_report(report_id: str, db: Session = Depends(get_db)) -> ViolationReportOut:
    report = db.get(ViolationReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return ViolationReportOut.model_validate(report, from_attributes=True)


# ------------------------------------------------------------------ complaints

@router.get("/complaint-categories", response_model=list[ComplaintCategoryOut])
def list_complaint_categories() -> list[ComplaintCategoryOut]:
    """Categories the complaint form offers, with the team each routes to."""
    return [
        ComplaintCategoryOut(
            id=key,
            label_en=label_en,
            label_ar=label_ar,
            team=team,
            urgent=key in complaints_service.URGENT_CATEGORIES,
        )
        for key, (label_en, label_ar, team) in complaints_service.CATEGORIES.items()
    ]


@router.post("/complaints", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
def create_complaint(payload: ComplaintCreate, db: Session = Depends(get_db)) -> ComplaintOut:
    if payload.category not in complaints_service.CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown complaint category '{payload.category}'.",
        )
    complaint = complaints_service.create_complaint(
        db,
        category=payload.category,
        subject=payload.subject,
        description=payload.description,
        compound=payload.compound,
        phase=payload.phase,
        location_text=payload.location_text,
        contact_phone=payload.contact_phone,
        user_id=payload.user_id,
    )
    db.commit()
    return ComplaintOut.model_validate(complaint, from_attributes=True)


@router.get("/complaints", response_model=list[ComplaintOut])
def list_complaints(
    db: Session = Depends(get_db),
    user_id: str | None = None,
    status_filter: str | None = None,
) -> list[ComplaintOut]:
    rows = complaints_service.list_complaints(db, user_id=user_id, status=status_filter)
    return [ComplaintOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/complaints/{complaint_id}", response_model=ComplaintOut)
def get_complaint(complaint_id: str, db: Session = Depends(get_db)) -> ComplaintOut:
    row = db.get(Complaint, complaint_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    return ComplaintOut.model_validate(row, from_attributes=True)


@router.patch("/complaints/{complaint_id}", response_model=ComplaintOut)
def update_complaint(
    complaint_id: str,
    payload: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
) -> ComplaintOut:
    """Staff-side status transition. Residents only ever read their complaints."""
    if payload.status not in complaints_service.VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Status must be one of {sorted(complaints_service.VALID_STATUSES)}.",
        )
    row = db.get(Complaint, complaint_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Complaint not found.")
    complaints_service.set_status(
        db,
        row,
        status=payload.status,
        resolution=payload.resolution,
        assigned_team=payload.assigned_team,
    )
    db.commit()
    return ComplaintOut.model_validate(row, from_attributes=True)
