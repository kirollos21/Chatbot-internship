"""Per-project contact numbers.

Two things live in the contacts directory, and they must not be confused:

1. **Dataset contacts** — the five records ingested from the regulations
   document (security gate, maintenance hotline, emergency, community
   management office, North Coast office). Every one of them ships with a
   `null` phone, because the source document does not contain the numbers. They
   render as "not configured yet" and that is correct.

2. **Reference contacts** — this module. Numbers taken from Palm Hills' own
   public listings so a resident has *something* to call, scoped per project so
   the number changes when the resident changes their location.

**Every entry here is `unverified` and says so.** They were read off public
directory listings, not handed over by Community Management, so they surface with
an explicit caveat rather than as confirmed numbers. That is the whole reason for
the third availability state: the codebase's rule is that a resident must never
be shown a number that might be wrong *as though it were right*, and the honest
way to keep that rule while still being useful is to show the number and say
where it came from.

**What is deliberately absent:** per-project maintenance, security and emergency
numbers. Those are not published anywhere public — they are given to residents
by their own community management office. Inventing them would be the single most
dangerous thing this app could do, so those slots stay `not_configured` until
somebody supplies the real list. When they do, it goes here and nothing else
changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.projects import CAIRO_EAST, CAIRO_WEST

#: Availability marker for a number we have but cannot vouch for. See the
#: module docstring; `app.repositories.catalog.public_contact` renders it.
UNVERIFIED = "unverified"

#: Roles. `community_office` is deliberately not `maintenance`: an office
#: landline is not a maintenance hotline and must not be labelled as one.
CUSTOMER_CARE = "customer_care"
COMMUNITY_OFFICE = "community_office"


@dataclass(frozen=True)
class ReferenceContact:
    record_id: str
    role: str
    name_en: str
    name_ar: str
    phone: str
    hours: str | None
    #: Where the number came from, shown to staff and carried in the API.
    source: str
    #: None applies to every project; otherwise the `compound` token it belongs
    #: to (see `app.services.projects`).
    compound: str | None = None


#: Group-wide. Offered for every project.
_GROUP: tuple[ReferenceContact, ...] = (
    ReferenceContact(
        record_id="R-CARE-HOTLINE",
        role=CUSTOMER_CARE,
        name_en="Palm Hills customer care",
        name_ar="خدمة عملاء بالم هيلز",
        phone="16547",
        hours="10:00 - 17:00",
        source="Palm Hills public customer-care hotline listings",
    ),
    ReferenceContact(
        record_id="R-CARE-WHATSAPP",
        role=CUSTOMER_CARE,
        name_en="Palm Hills customer care (WhatsApp)",
        name_ar="خدمة عملاء بالم هيلز (واتساب)",
        phone="01012268500",
        hours=None,
        source="Palm Hills public customer-care listings",
    ),
)

#: Regional offices. This is what makes the directory change with the resident's
#: project. Only the two offices whose numbers came back unambiguously are here;
#: the Alexandria and 6th-of-October listings were inconsistently formatted
#: across sources and are omitted rather than published wrong.
_OFFICES: tuple[tuple[str, ReferenceContact], ...] = (
    (
        CAIRO_WEST,
        ReferenceContact(
            record_id="R-OFFICE-WEST",
            role=COMMUNITY_OFFICE,
            name_en="Palm Hills office — Head Office, Smart Village",
            name_ar="مكتب بالم هيلز — المقر الرئيسي، سمارت فيليدج",
            phone="+20 2 3535 1200",
            hours=None,
            source="Public business directory listing (Abou Rawash / Smart Village)",
        ),
    ),
    (
        CAIRO_EAST,
        ReferenceContact(
            record_id="R-OFFICE-EAST",
            role=COMMUNITY_OFFICE,
            name_en="Palm Hills office — 5th Settlement",
            name_ar="مكتب بالم هيلز — التجمع الخامس",
            phone="+20 2 2810 4530",
            hours=None,
            source="Public business directory listing (Road 90, 1st section)",
        ),
    ),
)


def _region_of(compound: str | None) -> str | None:
    """Which region a compound token belongs to, via the projects list."""
    if not compound:
        return None
    from app.services.projects import PROJECTS

    return next((p.region for p in PROJECTS if p.compound == compound), None)


def reference_contacts(compound: str | None = None) -> list[ReferenceContact]:
    """Group contacts, plus the office for this project's region.

    With no compound the resident has not told us where they live, so only the
    group-wide numbers apply — the same reasoning the rule scoping uses.
    """
    out = list(_GROUP)
    region = _region_of(compound)
    if region is not None:
        out.extend(
            contact for office_region, contact in _OFFICES if office_region == region
        )
    return out


def public_reference_contact(contact: ReferenceContact, language: str = "en") -> dict:
    """Same shape as `catalog.public_contact`, so the API can merge the two."""
    caveat = {
        "en": (
            "Listed publicly by Palm Hills but not yet confirmed by Community "
            "Management."
        ),
        "ar": (
            "رقم منشور من بالم هيلز ولكن لم تؤكده إدارة المجتمعات حتى الآن."
        ),
        "franco": (
            "El raqm dah manshoor men Palm Hills bas lessa Community Management "
            "ma2akkedetoh."
        ),
    }
    lang = language if language in caveat else "en"
    return {
        "id": contact.record_id,
        "name_en": contact.name_en,
        "name_ar": contact.name_ar,
        "role": contact.role,
        "phone": contact.phone,
        "email": None,
        "hours": contact.hours,
        "compound": contact.compound,
        "phase": None,
        "availability": UNVERIFIED,
        "message": caveat[lang],
        "pending_fields": [],
        "source": contact.source,
    }
