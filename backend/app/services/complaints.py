"""Resident complaints.

A complaint is the resident's own grievance about the community or its services
— a lift that has been out for a week, uncollected rubbish, a guard who was
rude. It is not a violation report (which accuses another resident and is
governed by the verification rules in `ViolationReport`) and not an assistant
escalation ticket.

The categories below are routing labels, not policy. They exist so Community
Management can triage, and so a resident sees their complaint land somewhere
specific rather than in a general inbox. Adding one is a code change on purpose:
a free-text category cannot be routed to a team.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Complaint

OPEN = "open"
IN_REVIEW = "in_review"
AWAITING_USER = "awaiting_user"
RESOLVED = "resolved"
CLOSED = "closed"

VALID_STATUSES = {OPEN, IN_REVIEW, AWAITING_USER, RESOLVED, CLOSED}

#: category -> (english label, arabic label, team it routes to)
CATEGORIES: dict[str, tuple[str, str, str]] = {
    "maintenance": ("Maintenance", "الصيانة", "maintenance"),
    "cleanliness": ("Cleanliness & waste", "النظافة والمخلفات", "facilities"),
    "security": ("Security & access", "الأمن والدخول", "security"),
    "facilities": ("Facilities", "المرافق", "facilities"),
    "noise": ("Noise & disturbance", "الإزعاج والضوضاء", "community_management"),
    "landscaping": ("Landscaping", "المسطحات الخضراء", "facilities"),
    "staff": ("Staff conduct", "تعامل الموظفين", "community_management"),
    "billing": ("Fees & billing", "الرسوم والفواتير", "community_management"),
    "other": ("Something else", "شيء آخر", "community_management"),
}

#: Complaints a resident should be told to phone in rather than file and wait
#: for. A form is the wrong channel for something already on fire.
URGENT_CATEGORIES = {"security"}


def new_complaint_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"CMP-{stamp}-{secrets.token_hex(3).upper()}"


def team_for(category: str) -> str:
    return CATEGORIES.get(category, CATEGORIES["other"])[2]


def create_complaint(
    db: Session,
    *,
    category: str,
    subject: str,
    description: str,
    compound: str | None = None,
    phase: str | None = None,
    location_text: str | None = None,
    contact_phone: str | None = None,
    user_id: str | None = None,
) -> Complaint:
    complaint = Complaint(
        complaint_id=new_complaint_id(),
        user_id=user_id,
        category=category,
        subject=subject.strip(),
        description=description.strip(),
        compound=compound,
        phase=phase,
        location_text=(location_text or "").strip() or None,
        contact_phone=(contact_phone or "").strip() or None,
        status=OPEN,
        assigned_team=team_for(category),
    )
    db.add(complaint)
    db.flush()
    return complaint


def list_complaints(
    db: Session, *, user_id: str | None = None, status: str | None = None
) -> list[Complaint]:
    stmt = select(Complaint)
    if user_id:
        stmt = stmt.where(Complaint.user_id == user_id)
    if status:
        stmt = stmt.where(Complaint.status == status)
    return list(db.execute(stmt.order_by(Complaint.created_at.desc())).scalars())


def set_status(
    db: Session,
    complaint: Complaint,
    *,
    status: str,
    resolution: str | None = None,
    assigned_team: str | None = None,
) -> Complaint:
    complaint.status = status
    if resolution is not None:
        complaint.resolution = resolution
    if assigned_team is not None:
        complaint.assigned_team = assigned_team
    if status in (RESOLVED, CLOSED):
        complaint.resolved_at = datetime.now(timezone.utc)
    else:
        # Reopening has to clear the timestamp, or a reopened complaint keeps
        # reporting the moment it was previously closed.
        complaint.resolved_at = None
    db.flush()
    return complaint
