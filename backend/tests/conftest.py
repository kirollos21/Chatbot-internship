"""Test configuration.

Pure-logic tests (language, intent, integrity guard, rendering) run anywhere.
API tests need PostgreSQL with pgvector and are skipped automatically when it
is not reachable, so `pytest` is always green on a clean checkout.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Deterministic, offline defaults for the whole test session.
os.environ.setdefault("EMBEDDING_PROVIDER", "hash")
os.environ.setdefault("LLM_PROVIDER", "template")
os.environ.setdefault("API_KEYS", "")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")

DATASET_PATH = BACKEND_ROOT.parent / "data" / "palm_hills_regulations_v1.0.json"
os.environ.setdefault("DATASET_PATH", str(DATASET_PATH))


def _database_reachable() -> bool:
    try:
        from sqlalchemy import text

        from app.db.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def api_client():
    if not _database_reachable():
        pytest.skip("PostgreSQL is not reachable; skipping API integration tests.")

    from fastapi.testclient import TestClient

    from app.db.database import SessionLocal, init_db
    from app.db.models import PolicyVersion
    from app.main import app
    from app.scripts.ingest import ingest

    init_db()
    session = SessionLocal()
    try:
        loaded = session.query(PolicyVersion).count()
    finally:
        session.close()
    if loaded == 0:
        if not DATASET_PATH.exists():
            pytest.skip("Dataset not built; run `python data/build_dataset.py`.")
        ingest(DATASET_PATH, activate=True)

    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="session")
def dataset() -> dict:
    import json

    if not DATASET_PATH.exists():
        pytest.skip("Dataset not built; run `python data/build_dataset.py`.")
    with DATASET_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)
