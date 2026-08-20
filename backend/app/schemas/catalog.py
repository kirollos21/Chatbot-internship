"""Directory and regulation browsing schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CategoryOut(BaseModel):
    category_id: str
    category_en: str
    category_ar: str


class PolicyOut(BaseModel):
    id: str
    category_id: str
    rule_en: str
    rule_ar: str
    # 'pdf' = present in that language in the source document.
    # 'derived' = translated during data preparation; the other language is the source.
    src_en: str
    src_ar: str
    compound: str | None = None
    phase: str | None = None
    effective_from: date
    effective_until: date | None = None
    version: str | None = None


class ViolationOut(BaseModel):
    id: str
    category_id: str
    violation_en: str
    violation_ar: str
    penalty_egp: int
    action_en: str
    action_ar: str
    related_policy_ids: list[str] = []
    compound: str | None = None
    phase: str | None = None
    effective_from: date
    effective_until: date | None = None
    version: str | None = None


class ContactOut(BaseModel):
    id: str
    name_en: str
    name_ar: str
    role: str
    phone: str | None = None
    email: str | None = None
    hours: str | None = None
    compound: str | None = None
    phase: str | None = None
    availability: str
    message: str | None = None
    pending_fields: list[str] = []
    #: Set only on reference contacts - where the number was taken from.
    source: str | None = None


class FacilityOut(BaseModel):
    id: str
    name_en: str
    name_ar: str
    facility_type: str
    compound: str | None = None
    phase: str | None = None
    location_note: str | None = None
    hours: str | None = None
    hours_source: str | None = None
    restrictions: list[str] = []
    related_policy_ids: list[str] = []
    contact_id: str | None = None
    availability: str
    message: str | None = None
    pending_fields: list[str] = []


class ProjectOut(BaseModel):
    id: str
    name_en: str
    name_ar: str
    region: str
    region_en: str
    region_ar: str
    #: Send this back as `compound`; it is not always the project id.
    compound: str


class DatasetStatus(BaseModel):
    version: str | None
    #: in_sync | stale | not_ingested | unknown - whether the database still
    #: holds what the dataset file currently says.
    sync_status: str = "unknown"
    sync_message: str | None = None
    file_sha256: str | None = None
    ingested_sha256: str | None = None
    source_document: str | None
    issuer: str | None
    effective_from: date | None
    counts: dict
    unconfigured_contacts: list[str]
    unconfigured_facilities: list[str]
