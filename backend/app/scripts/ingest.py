"""Load the verified dataset into PostgreSQL and build embeddings.

    python -m app.scripts.ingest [--dataset PATH] [--activate]

Re-running is safe: a version that already exists is replaced wholesale
(delete + insert of its policies/violations), so a corrected dataset can be
re-ingested without renumbering stable IDs. Loading a *new* version with
--activate deactivates the previous one; the old rows stay in the database so
historical questions remain answerable via `as_of`.

`search_text` deliberately carries the English text, the Arabic text *and* the
Franco consonant skeleton of the English, so the trigram index can match a
Franco query such as `ghrama 3ala el parking` without a translation step.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.database import SessionLocal, init_db
from app.db.models import (
    VECTOR_ENABLED,
    Contact,
    Facility,
    Policy,
    PolicyCategory,
    PolicyVersion,
    Violation,
)
from app.providers.embeddings import get_embedding_provider
from app.services.language import phrase_skeleton

BATCH = 64


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _search_text(*parts: str | None) -> str:
    joined = " \n ".join(p for p in parts if p)
    return f"{joined} \n {phrase_skeleton(joined)}"


def _embed_all(texts: list[str]) -> list[list[float]]:
    if not VECTOR_ENABLED:
        return []  # no embedding column exists; nothing to store
    provider = get_embedding_provider()
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        vectors.extend(provider.embed(texts[start : start + BATCH]))
    return vectors


def ingest(dataset_path: Path, activate: bool = True) -> dict:
    with dataset_path.open(encoding="utf-8") as fh:
        dataset = json.load(fh)

    meta = dataset["metadata"]
    version_label = meta["version"]
    effective_from = _parse_date(meta.get("effective_from") or meta.get("effective_date"))
    effective_until = _parse_date(meta.get("effective_until"))

    init_db()
    session = SessionLocal()
    try:
        version = session.execute(
            select(PolicyVersion).where(PolicyVersion.version == version_label)
        ).scalar_one_or_none()

        if version is None:
            version = PolicyVersion(version=version_label)
            session.add(version)

        version.source_document = meta["source_document"]
        version.source_sha256 = meta.get("source_document_sha256")
        version.issuer = meta["issuer"]
        version.effective_from = effective_from
        version.effective_until = effective_until
        version.counts = meta.get("counts", {})
        session.flush()

        if activate:
            for other in session.execute(select(PolicyVersion)).scalars():
                other.is_active = other.id == version.id
        else:
            version.is_active = version.is_active or False

        # Replace this version's content wholesale.
        session.execute(delete(Policy).where(Policy.version_id == version.id))
        session.execute(delete(Violation).where(Violation.version_id == version.id))

        # --- categories -------------------------------------------------
        for category in dataset["policies"]:
            existing = session.get(PolicyCategory, category["category_id"])
            if existing is None:
                session.add(
                    PolicyCategory(
                        category_id=category["category_id"],
                        category_en=category["category_en"],
                        category_ar=category["category_ar"],
                    )
                )
            else:
                existing.category_en = category["category_en"]
                existing.category_ar = category["category_ar"]
        session.flush()

        # --- policies ---------------------------------------------------
        policy_rows: list[Policy] = []
        for category in dataset["policies"]:
            for rule in category["rules"]:
                text = _search_text(rule["en"], rule["ar"], category["category_en"])
                policy_rows.append(
                    Policy(
                        record_id=rule["id"],
                        version_id=version.id,
                        category_id=category["category_id"],
                        rule_en=rule["en"],
                        rule_ar=rule["ar"],
                        src_en=rule["src_en"],
                        src_ar=rule["src_ar"],
                        page_en=rule.get("page_en"),
                        page_ar=rule.get("page_ar"),
                        compound=None,
                        phase=None,
                        effective_from=effective_from,
                        effective_until=effective_until,
                        search_text=text,
                    )
                )
        for row, vector in zip(policy_rows, _embed_all([r.search_text for r in policy_rows])):
            row.embedding = vector
        session.add_all(policy_rows)

        # --- violations -------------------------------------------------
        violation_rows: list[Violation] = []
        for entry in dataset["violations"]:
            text = _search_text(
                entry["violation_en"], entry["violation_ar"], entry["action_en"], entry["category_id"]
            )
            violation_rows.append(
                Violation(
                    record_id=entry["id"],
                    version_id=version.id,
                    category_id=entry["category_id"],
                    violation_en=entry["violation_en"],
                    violation_ar=entry["violation_ar"],
                    penalty_egp=int(entry["penalty_egp"]),
                    action_en=entry["action_en"],
                    action_ar=entry["action_ar"],
                    related_policy_ids=entry.get("related_policy_ids", []),
                    page_en=entry.get("page_en"),
                    page_ar=entry.get("page_ar"),
                    compound=None,
                    phase=None,
                    effective_from=effective_from,
                    effective_until=effective_until,
                    search_text=text,
                )
            )
        for row, vector in zip(violation_rows, _embed_all([r.search_text for r in violation_rows])):
            row.embedding = vector
        session.add_all(violation_rows)

        # --- contacts (placeholder-safe) --------------------------------
        for entry in dataset["contacts"]["entries"]:
            contact = session.get(Contact, entry["id"]) or Contact(record_id=entry["id"])
            contact.name_en = entry["name_en"]
            contact.name_ar = entry["name_ar"]
            contact.role = entry["role"]
            # Never load a masked placeholder as if it were a phone number.
            phone = entry.get("phone")
            contact.phone = phone if phone and not set(str(phone).upper()) <= {"X", "-", " "} else None
            contact.email = entry.get("email")
            contact.hours = entry.get("hours")
            contact.compound = entry.get("compound")
            contact.phase = entry.get("phase")
            contact.status = entry.get("status", "unconfigured")
            contact.pending_fields = entry.get("pending_fields", [])
            session.add(contact)

        # --- facilities -------------------------------------------------
        for entry in dataset["facilities"]["entries"]:
            facility = session.get(Facility, entry["id"]) or Facility(record_id=entry["id"])
            facility.name_en = entry["name_en"]
            facility.name_ar = entry["name_ar"]
            facility.facility_type = entry["facility_type"]
            facility.compound = entry.get("compound")
            facility.phase = entry.get("phase")
            facility.location_note = entry.get("location_note")
            facility.hours = entry.get("hours")
            facility.hours_source = entry.get("hours_source")
            facility.restrictions_en = entry.get("restrictions_en", [])
            facility.restrictions_ar = entry.get("restrictions_ar", [])
            facility.related_policy_ids = entry.get("related_policy_ids", [])
            facility.contact_id = entry.get("contact_id")
            facility.status = entry.get("status", "unconfigured")
            facility.pending_fields = entry.get("pending_fields", [])
            session.add(facility)

        session.commit()
        return {
            "version": version_label,
            "policies": len(policy_rows),
            "violations": len(violation_rows),
            "contacts": len(dataset["contacts"]["entries"]),
            "facilities": len(dataset["facilities"]["entries"]),
            "embedding_provider": get_embedding_provider().name if VECTOR_ENABLED else "disabled",
        "retrieval_mode": "vector+trigram" if VECTOR_ENABLED else "trigram-only",
            "active": activate,
        }
    finally:
        session.close()


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Ingest the Palm Hills regulations dataset.")
    parser.add_argument("--dataset", default=str(settings.dataset_file))
    parser.add_argument(
        "--no-activate",
        dest="activate",
        action="store_false",
        help="Load the version without making it the active one.",
    )
    parser.set_defaults(activate=True)
    args = parser.parse_args()

    path = Path(args.dataset)
    if not path.exists():
        print(f"Dataset not found: {path}\nRun `python data/build_dataset.py` first.", file=sys.stderr)
        return 1

    summary = ingest(path, activate=args.activate)
    print("Ingest complete:")
    for key, value in summary.items():
        print(f"  {key}: {value}")
    if summary["embedding_provider"] == "hash":
        print(
            "\nNote: EMBEDDING_PROVIDER=hash gives deterministic offline vectors, not true "
            "semantic search. Set EMBEDDING_PROVIDER=local and re-run before evaluating quality."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
