"""Database engine, session factory and schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    future=True,
    echo=_settings.debug,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def init_db() -> None:
    """Create the pgvector extension, the schema, and the vector indexes.

    Idempotent: safe to run on every boot. Kept deliberately simple instead of
    pulling in a migration tool at this stage; the schema-version table gives us
    somewhere to hang real migrations later.
    """
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for table in ("policies", "violations"):
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
