"""Is the database still serving what the dataset file says?

Editing `data/palm_hills_regulations_v1.0.json` does not change the database.
Loading it is an explicit step (`run.bat ingest`) and that gate is deliberate:
the file is the verified record of a legal document, and a half-finished edit
must not silently replace the rules residents are being fined under.

What is *not* deliberate is failing to notice. Before this module the two could
drift apart with nothing to show it — the app would keep answering from the old
rows, confidently and wrongly, and the only way to find out was to remember.

So the file's hash is recorded at ingest and compared on demand. The gate stays
manual; the staleness stops being invisible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import PolicyVersion

#: Nothing has been ingested at all.
NOT_INGESTED = "not_ingested"
#: The file on disk is what the database holds.
IN_SYNC = "in_sync"
#: The file has been edited since it was last ingested.
STALE = "stale"
#: Ingested before hashes were recorded, so drift cannot be proven either way.
UNKNOWN = "unknown"


@dataclass(frozen=True)
class DatasetState:
    status: str
    version: str | None
    file_sha256: str | None
    ingested_sha256: str | None

    @property
    def needs_ingest(self) -> bool:
        return self.status in (NOT_INGESTED, STALE)

    @property
    def message(self) -> str | None:
        return {
            NOT_INGESTED: "No dataset has been ingested yet. Run: run.bat ingest",
            STALE: (
                "The dataset file has changed since it was ingested; the API is "
                "still answering from the previous load. Run: run.bat ingest"
            ),
            UNKNOWN: (
                "This version was ingested before file hashes were recorded, so "
                "drift cannot be detected. Re-ingest to start tracking it."
            ),
        }.get(self.status)


def file_digest(path: Path | None = None) -> str | None:
    """SHA-256 of the dataset file, or None when it is not on disk."""
    path = path or get_settings().dataset_file
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        # Chunked: the dataset is small today but this is the kind of file that
        # only grows, and a whole-file read would quietly become a problem.
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def current_state(db: Session) -> DatasetState:
    version = db.execute(
        select(PolicyVersion).where(PolicyVersion.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    on_disk = file_digest()

    if version is None:
        return DatasetState(NOT_INGESTED, None, on_disk, None)
    if not version.dataset_sha256:
        return DatasetState(UNKNOWN, version.version, on_disk, None)
    if on_disk is None:
        # The file is gone but rows remain. Not stale — unverifiable.
        return DatasetState(UNKNOWN, version.version, None, version.dataset_sha256)

    status = IN_SYNC if on_disk == version.dataset_sha256 else STALE
    return DatasetState(status, version.version, on_disk, version.dataset_sha256)
