"""Assemble and validate the canonical Palm Hills regulations dataset.

Reads the hand-verified extraction parts in data/parts/ and emits
data/palm_hills_regulations_v1.json in the structure consumed by the backend
ingestion job.

Run:  python data/build_dataset.py
Exit code is non-zero if any integrity check fails, so this is safe to wire
into CI before an ingestion run.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
PARTS_DIR = DATA_DIR / "parts"
REPO_ROOT = DATA_DIR.parent
SOURCE_PDF = REPO_ROOT / "docs" / "source" / "Community_Living_standards_regulations_and_penalties.pdf"

DATASET_VERSION = "1.0"
EFFECTIVE_FROM = "2026-08-18"
ISSUER = "Palm Hills Developments - Community Management"

# Expected counts, asserted so a bad edit to a part file fails loudly.
EXPECTED_CATEGORIES = 10
EXPECTED_VIOLATIONS = 90


def _load(name: str) -> dict:
    with (PARTS_DIR / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build() -> tuple[dict, list[str]]:
    policies = _load("policies.json")
    violations = _load("violations.json")
    contacts = _load("contacts.json")
    facilities = _load("facilities.json")
    franco = _load("franco.json")

    errors: list[str] = []
    categories = policies["categories"]
    rules = [rule for cat in categories for rule in cat["rules"]]
    rule_ids = {rule["id"] for rule in rules}
    violation_rows = violations["violations"]
    category_ids = {cat["category_id"] for cat in categories}

    if len(categories) != EXPECTED_CATEGORIES:
        errors.append(f"expected {EXPECTED_CATEGORIES} categories, found {len(categories)}")
    if len(violation_rows) != EXPECTED_VIOLATIONS:
        errors.append(f"expected {EXPECTED_VIOLATIONS} violations, found {len(violation_rows)}")

    if len(rule_ids) != len(rules):
        errors.append("duplicate policy rule ids")

    seen_violation_ids: set[str] = set()
    for row in violation_rows:
        vid = row["id"]
        if vid in seen_violation_ids:
            errors.append(f"duplicate violation id {vid}")
        seen_violation_ids.add(vid)
        if row["category_id"] not in category_ids:
            errors.append(f"{vid}: unknown category_id {row['category_id']}")
        penalty = row["penalty_egp"]
        if not isinstance(penalty, int) or isinstance(penalty, bool) or penalty <= 0:
            errors.append(f"{vid}: penalty_egp must be a positive integer, got {penalty!r}")
        for field in ("violation_en", "violation_ar", "action_en", "action_ar"):
            if not row.get(field, "").strip():
                errors.append(f"{vid}: empty {field}")
        for pid in row.get("related_policy_ids", []):
            if pid not in rule_ids:
                errors.append(f"{vid}: related_policy_ids references unknown rule {pid}")

    for rule in rules:
        for field in ("en", "ar"):
            if not rule.get(field, "").strip():
                errors.append(f"{rule['id']}: empty {field}")
        for field in ("src_en", "src_ar"):
            if rule.get(field) not in {"pdf", "derived"}:
                errors.append(f"{rule['id']}: {field} must be 'pdf' or 'derived'")

    for facility in facilities["facilities"]:
        for pid in facility.get("related_policy_ids", []):
            if pid not in rule_ids:
                errors.append(f"{facility['id']}: unknown related policy {pid}")

    # Placeholder safety: nothing that looks like a fake phone number may ship.
    for contact in contacts["contacts"]:
        phone = contact.get("phone")
        if phone is not None and set(str(phone).upper()) <= {"X", "0", "-", " "}:
            errors.append(f"{contact['id']}: masked placeholder phone must be null, not {phone!r}")
        if phone is None and contact.get("status") != "unconfigured":
            errors.append(f"{contact['id']}: phone is null so status must be 'unconfigured'")

    derived_rules = [r["id"] for r in rules if "derived" in (r["src_en"], r["src_ar"])]

    dataset = {
        "metadata": {
            "source_document": SOURCE_PDF.name,
            "source_document_sha256": _sha256(SOURCE_PDF),
            "issuer": ISSUER,
            "version": DATASET_VERSION,
            "effective_from": EFFECTIVE_FROM,
            "effective_until": None,
            "effective_date": EFFECTIVE_FROM,
            "languages_available": ["en", "ar"],
            "generated_languages": ["franco"],
            "counts": {
                "categories": len(categories),
                "rules": len(rules),
                "violations": len(violation_rows),
                "contacts": len(contacts["contacts"]),
                "facilities": len(facilities["facilities"]),
                "rules_with_derived_translation": len(derived_rules),
            },
            "integrity_notes": [
                "penalty_egp values are transcribed verbatim from the source violation tables and are authoritative.",
                "Franco-Arabic is generated at query time and is never an authoritative policy language.",
                "Contacts and facilities contain placeholder records; unconfigured fields are null and must never be surfaced as real values.",
            ],
        },
        "policies": categories,
        "violations": violation_rows,
        "contacts": {"entries": contacts["contacts"], "notice": contacts["_comment"]},
        "facilities": {"entries": facilities["facilities"], "notice": facilities["_comment"]},
        "franco_arabic_notes": franco,
    }
    return dataset, errors


def main() -> int:
    dataset, errors = build()
    if errors:
        print("DATASET VALIDATION FAILED", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    out_path = DATA_DIR / f"palm_hills_regulations_v{DATASET_VERSION}.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(dataset, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    counts = dataset["metadata"]["counts"]
    print(f"wrote {out_path.relative_to(REPO_ROOT)}")
    print(
        "  categories={categories} rules={rules} violations={violations} "
        "contacts={contacts} facilities={facilities}".format(**counts)
    )
    print(f"  rules needing translation review: {counts['rules_with_derived_translation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
