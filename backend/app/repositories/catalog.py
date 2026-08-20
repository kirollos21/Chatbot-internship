"""Structured lookups for facilities and contacts.

These are *not* routed through the vector store. "What's the security number?"
is a directory lookup, not a semantic-similarity problem, and forcing it
through RAG would only add a way to get it wrong.

Placeholder safety lives here: `public_contact` and `public_facility` are the
only shapes the API is allowed to return. An unconfigured field comes back as
`null` with an explicit `availability` marker — never as a masked string such
as `XXXXXXXXXX`, which a resident could mistake for a real value.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Contact, Facility

CONFIGURED = "configured"
NOT_CONFIGURED = "not_configured"

_UNAVAILABLE_MESSAGE = {
    "en": "This number has not been configured in the system yet.",
    "ar": "لم يتم إدخال هذا الرقم في النظام حتى الآن.",
    "franco": "El raqm dah lessa mesh matsagel fel system.",
}

_FACILITY_UNAVAILABLE = {
    "en": "Location and hours for this facility have not been configured yet.",
    "ar": "لم يتم إدخال مكان ومواعيد هذا المرفق حتى الآن.",
    "franco": "El makan wel mawa3eed bta3et el makan dah lessa mesh matsagelin.",
}


def public_contact(contact: Contact, language: str = "en") -> dict:
    lang = language if language in _UNAVAILABLE_MESSAGE else "en"
    configured = bool(contact.phone) and contact.status == CONFIGURED
    return {
        "id": contact.record_id,
        "name_en": contact.name_en,
        "name_ar": contact.name_ar,
        "role": contact.role,
        "phone": contact.phone if configured else None,
        "email": contact.email if configured else None,
        "hours": contact.hours,
        "compound": contact.compound,
        "phase": contact.phase,
        "availability": CONFIGURED if configured else NOT_CONFIGURED,
        "message": None if configured else _UNAVAILABLE_MESSAGE[lang],
        "pending_fields": list(contact.pending_fields or []),
        # Dataset contacts come from the regulations document itself, so there
        # is no third-party provenance to report. Reference contacts fill this.
        "source": None,
    }


def public_facility(facility: Facility, language: str = "en") -> dict:
    lang = language if language in _FACILITY_UNAVAILABLE else "en"
    complete = facility.status == CONFIGURED
    restrictions = facility.restrictions_ar if lang == "ar" else facility.restrictions_en
    return {
        "id": facility.record_id,
        "name_en": facility.name_en,
        "name_ar": facility.name_ar,
        "facility_type": facility.facility_type,
        "compound": facility.compound,
        "phase": facility.phase,
        "location_note": facility.location_note,
        # Hours are surfaced only when we can say where they came from: either a
        # configured record or a rule in the regulations document.
        "hours": facility.hours if (facility.hours and (complete or facility.hours_source)) else None,
        "hours_source": facility.hours_source,
        "restrictions": list(restrictions or []),
        "related_policy_ids": list(facility.related_policy_ids or []),
        "contact_id": facility.contact_id,
        "availability": CONFIGURED if complete else NOT_CONFIGURED,
        "message": None if complete else _FACILITY_UNAVAILABLE[lang],
        "pending_fields": list(facility.pending_fields or []),
    }


def list_contacts(db: Session, *, role: str | None = None, compound: str | None = None) -> list[Contact]:
    stmt = select(Contact)
    if role:
        stmt = stmt.where(Contact.role == role)
    if compound:
        stmt = stmt.where(or_(Contact.compound.is_(None), Contact.compound == compound))
    return list(db.execute(stmt.order_by(Contact.record_id)).scalars())


def get_contact(db: Session, record_id: str) -> Contact | None:
    return db.get(Contact, record_id)


def list_facilities(
    db: Session,
    *,
    facility_type: str | None = None,
    compound: str | None = None,
    phase: str | None = None,
) -> list[Facility]:
    stmt = select(Facility)
    if facility_type:
        stmt = stmt.where(Facility.facility_type == facility_type)
    if compound:
        stmt = stmt.where(or_(Facility.compound.is_(None), Facility.compound == compound))
    if phase:
        stmt = stmt.where(or_(Facility.phase.is_(None), Facility.phase == phase))
    return list(db.execute(stmt.order_by(Facility.record_id)).scalars())


def get_facility(db: Session, record_id: str) -> Facility | None:
    return db.get(Facility, record_id)


# Intent keyword -> contact role, used by the chat route's contact shortcut.
_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "security": ("security", "guard", "gate", "أمن", "الأمن", "بوابة", "amn"),
    "maintenance": ("maintenance", "repair", "صيانة", "sianna", "siana", "syana"),
    "emergency": ("emergency", "ambulance", "fire", "طوارئ", "الطوارئ", "إسعاف", "حريق", "taware2"),
    "beach_office": ("beach", "north coast", "شاطئ", "الساحل", "shate2", "sahel"),
    "community_management": ("management", "office", "إدارة المجتمعات", "إدارة", "management"),
}


def role_from_query(query: str) -> str | None:
    lowered = (query or "").lower()
    for role, keywords in _ROLE_KEYWORDS.items():
        if any(kw in lowered or kw in query for kw in keywords):
            return role
    return None
