"""Ticket and violation-report schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TicketCreate(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    detected_language: str = "en"
    compound: str | None = Field(default=None, max_length=128)
    phase: str | None = Field(default=None, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)
    reason: str = Field(default="resident_request", max_length=64)


class TicketOut(BaseModel):
    ticket_id: str
    status: str
    reason: str
    assigned_team: str | None
    created_at: datetime
    resolved_at: datetime | None = None
    resolution: str | None = None


class TicketStatusUpdate(BaseModel):
    status: str
    resolution: str | None = Field(default=None, max_length=4000)
    assigned_team: str | None = Field(default=None, max_length=64)


class ComplaintCreate(BaseModel):
    category: str = Field(max_length=32)
    subject: str = Field(min_length=3, max_length=256)
    description: str = Field(min_length=5, max_length=4000)
    compound: str | None = Field(default=None, max_length=128)
    phase: str | None = Field(default=None, max_length=128)
    location_text: str | None = Field(default=None, max_length=512)
    contact_phone: str | None = Field(default=None, max_length=64)
    user_id: str | None = Field(default=None, max_length=128)


class ComplaintOut(BaseModel):
    complaint_id: str
    category: str
    subject: str
    description: str
    compound: str | None
    phase: str | None
    location_text: str | None
    contact_phone: str | None
    status: str
    assigned_team: str | None
    resolution: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class ComplaintStatusUpdate(BaseModel):
    status: str
    resolution: str | None = Field(default=None, max_length=4000)
    assigned_team: str | None = Field(default=None, max_length=64)


class ComplaintCategoryOut(BaseModel):
    id: str
    label_en: str
    label_ar: str
    team: str
    #: True when a form is the wrong channel - the resident should call instead.
    urgent: bool = False


class ViolationReportCreate(BaseModel):
    description: str = Field(min_length=5, max_length=4000)
    category_id: str | None = Field(default=None, max_length=64)
    location_text: str | None = Field(default=None, max_length=512)
    compound: str | None = Field(default=None, max_length=128)
    phase: str | None = Field(default=None, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)


class ViolationReportOut(BaseModel):
    report_id: str
    status: str
    category_id: str | None
    description: str
    location_text: str | None
    compound: str | None
    phase: str | None
    attachments: list[dict] = []
    # A hint for staff triage. It never makes the report an enforced violation:
    # `status` stays "reported" until a human verifies it.
    suggested_violation_id: str | None = None
    suggested_confidence: float | None = None
    suggested_disclaimer: str = (
        "AI classification is a triage hint for Community Management staff only. "
        "A reported violation is not a verified violation until staff confirm it."
    )
    created_at: datetime
