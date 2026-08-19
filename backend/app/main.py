"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import catalog, chat, support
from app.core.config import get_settings
from app.db.database import engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        init_db()
        logger.info("Database schema ready.")
    except Exception:  # pragma: no cover - startup diagnostics
        logger.exception("Database initialisation failed; the API will start but queries will fail.")
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description=(
        "Verified Palm Hills community assistant. Answers are traced to the "
        "Community Living Standards regulations dataset; the language model "
        "rephrases retrieved records and never supplies policy facts of its own."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


@health_router.get("/health/ready")
def readiness() -> dict:
    checks = {
        "database": "unknown",
        "embeddings": settings.embedding_provider if settings.vector_enabled else "disabled",
        "llm": settings.llm_provider,
        "retrieval_mode": "vector+trigram" if settings.vector_enabled else "trigram-only",
    }
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - depends on runtime env
        checks["database"] = f"error: {type(exc).__name__}"
    checks["status"] = "ok" if checks["database"] == "ok" else "degraded"
    return checks


api = APIRouter(prefix="/api/v1")
api.include_router(chat.router)
api.include_router(catalog.router)
api.include_router(support.router)

app.include_router(health_router)
app.include_router(api)
