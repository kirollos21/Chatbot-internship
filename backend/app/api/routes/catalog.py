"""Browsing endpoints for the Flutter Policies / Violations / Facilities / Contacts tabs.

Everything here is a plain filtered lookup against the active policy version —
no retrieval, no model. `as_of` lets a caller ask what was in force on a given
date, which is what makes historical questions answerable once a second version
is loaded.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import authenticated
from app.db.database import get_db
from app.db.models import Contact, Facility, Policy, PolicyCategory, PolicyVersion, Violation
from app.repositories import catalog as catalog_repo
from app.schemas.catalog import (
    CategoryOut,
    ContactOut,
    DatasetStatus,
    FacilityOut,
    PolicyOut,
    ViolationOut,
)

router = APIRouter(tags=["catalog"], dependencies=[Depends(authenticated)])


def _active_version(db: Session) -> PolicyVersion | None:
    return db.execute(
        select(PolicyVersion).where(PolicyVersion.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()


def _scope(stmt, model, compound: str | None, phase: str | None, as_of: date):
    stmt = stmt.where(model.effective_from <= as_of).where(
        or_(model.effective_until.is_(None), model.effective_until >= as_of)
    )
    if compound:
        stmt = stmt.where(or_(model.compound.is_(None), model.compound == compound))
    else:
        stmt = stmt.where(model.compound.is_(None))
    if phase:
        stmt = stmt.where(or_(model.phase.is_(None), model.phase == phase))
    return stmt


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryOut]:
    rows = db.execute(select(PolicyCategory).order_by(PolicyCategory.category_id)).scalars()
    return [CategoryOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/policies", response_model=list[PolicyOut])
def list_policies(
    db: Session = Depends(get_db),
    category_id: str | None = None,
    compound: str | None = None,
    phase: str | None = None,
    as_of: date | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[PolicyOut]:
    version = _active_version(db)
    if version is None:
        return []
    as_of = as_of or date.today()
    stmt = select(Policy).where(Policy.version_id == version.id)
    if category_id:
        stmt = stmt.where(Policy.category_id == category_id)
    stmt = _scope(stmt, Policy, compound, phase, as_of)
    rows = db.execute(stmt.order_by(Policy.record_id).limit(limit).offset(offset)).scalars()
    return [
        PolicyOut(
            id=r.record_id,
            category_id=r.category_id,
            rule_en=r.rule_en,
            rule_ar=r.rule_ar,
            src_en=r.src_en,
            src_ar=r.src_ar,
            compound=r.compound,
            phase=r.phase,
            effective_from=r.effective_from,
            effective_until=r.effective_until,
            version=version.version,
        )
        for r in rows
    ]


@router.get("/violations", response_model=list[ViolationOut])
def list_violations(
    db: Session = Depends(get_db),
    category_id: str | None = None,
    compound: str | None = None,
    phase: str | None = None,
    as_of: date | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ViolationOut]:
    version = _active_version(db)
    if version is None:
        return []
    as_of = as_of or date.today()
    stmt = select(Violation).where(Violation.version_id == version.id)
    if category_id:
        stmt = stmt.where(Violation.category_id == category_id)
    stmt = _scope(stmt, Violation, compound, phase, as_of)
    rows = db.execute(stmt.order_by(Violation.record_id).limit(limit).offset(offset)).scalars()
    return [
        ViolationOut(
            id=r.record_id,
            category_id=r.category_id,
            violation_en=r.violation_en,
            violation_ar=r.violation_ar,
            penalty_egp=r.penalty_egp,
            action_en=r.action_en,
            action_ar=r.action_ar,
            related_policy_ids=list(r.related_policy_ids or []),
            compound=r.compound,
            phase=r.phase,
            effective_from=r.effective_from,
            effective_until=r.effective_until,
            version=version.version,
        )
        for r in rows
    ]


@router.get("/violations/{record_id}", response_model=ViolationOut)
def get_violation(record_id: str, db: Session = Depends(get_db)) -> ViolationOut:
    version = _active_version(db)
    row = db.execute(
        select(Violation).where(
            Violation.record_id == record_id.upper(),
            Violation.version_id == (version.id if version else None),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Violation not found.")
    return ViolationOut(
        id=row.record_id,
        category_id=row.category_id,
        violation_en=row.violation_en,
        violation_ar=row.violation_ar,
        penalty_egp=row.penalty_egp,
        action_en=row.action_en,
        action_ar=row.action_ar,
        related_policy_ids=list(row.related_policy_ids or []),
        compound=row.compound,
        phase=row.phase,
        effective_from=row.effective_from,
        effective_until=row.effective_until,
        version=version.version if version else None,
    )


@router.get("/contacts", response_model=list[ContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    role: str | None = None,
    compound: str | None = None,
    language: str = "en",
) -> list[ContactOut]:
    rows = catalog_repo.list_contacts(db, role=role, compound=compound)
    return [ContactOut(**catalog_repo.public_contact(r, language)) for r in rows]


@router.get("/facilities", response_model=list[FacilityOut])
def list_facilities(
    db: Session = Depends(get_db),
    facility_type: str | None = None,
    compound: str | None = None,
    phase: str | None = None,
    language: str = "en",
) -> list[FacilityOut]:
    rows = catalog_repo.list_facilities(
        db, facility_type=facility_type, compound=compound, phase=phase
    )
    return [FacilityOut(**catalog_repo.public_facility(r, language)) for r in rows]


@router.get("/facilities/{record_id}", response_model=FacilityOut)
def get_facility(record_id: str, language: str = "en", db: Session = Depends(get_db)) -> FacilityOut:
    row = catalog_repo.get_facility(db, record_id.upper())
    if row is None:
        raise HTTPException(status_code=404, detail="Facility not found.")
    return FacilityOut(**catalog_repo.public_facility(row, language))


@router.get("/dataset", response_model=DatasetStatus)
def dataset_status(db: Session = Depends(get_db)) -> DatasetStatus:
    """What is loaded, and what still needs real Palm Hills data."""
    version = _active_version(db)
    unconfigured_contacts = [
        c.record_id
        for c in db.execute(select(Contact).where(Contact.status != "configured")).scalars()
    ]
    unconfigured_facilities = [
        f.record_id
        for f in db.execute(select(Facility).where(Facility.status != "configured")).scalars()
    ]
    return DatasetStatus(
        version=version.version if version else None,
        source_document=version.source_document if version else None,
        issuer=version.issuer if version else None,
        effective_from=version.effective_from if version else None,
        counts=dict(version.counts) if version else {},
        unconfigured_contacts=unconfigured_contacts,
        unconfigured_facilities=unconfigured_facilities,
    )
