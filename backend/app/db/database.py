"""Database engine, session factory and schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import VECTOR_ENABLED, Base

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
    echo=_settings.debug,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


class VectorExtensionMissing(RuntimeError):
    """pgvector was requested but the server cannot provide it."""


def init_db() -> None:
    """Create extensions, schema and indexes. Idempotent - safe on every boot.

    Kept deliberately simple instead of pulling in a migration tool at this
    stage; the policy_versions table gives us somewhere to hang real migrations
    later.
    """
    with engine.begin() as conn:
        # pg_trgm is bundled with PostgreSQL, so it is always required.
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

        if VECTOR_ENABLED:
            try:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            except Exception as exc:
                raise VectorExtensionMissing(
                    "VECTOR_ENABLED=true but this PostgreSQL has no pgvector "
                    "extension. Either install pgvector (see README), or set "
                    "VECTOR_ENABLED=false to run on trigram search alone."
                ) from exc

    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        for table in ("policies", "violations"):
            if VECTOR_ENABLED:
                conn.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS ix_{table}_embedding "
                        f"ON {table} USING hnsw (embedding vector_cosine_ops)"
                    )
                )
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS ix_{table}_search_trgm "
                    f"ON {table} USING gin (search_text gin_trgm_ops)"
                )
            )


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
