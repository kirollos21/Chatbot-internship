"""Hybrid retrieval over the verified policy and violation stores.

Not everything goes through RAG. Facilities and contacts are structured lookups
(`app.repositories.catalog`); this module covers the two stores where semantic
matching earns its place — policies and violations — and even there it fuses
three signals:

1. **vector** similarity (pgvector, cosine)
2. **lexical** similarity (pg_trgm, which handles Arabic and Latin alike)
3. **category** agreement with the intent classifier's topic hints

Metadata filtering (version, effective date, compound, phase) is applied in SQL
*before* ranking, so an out-of-scope or superseded rule can never be ranked at
all — it is not merely down-weighted.

Compound scoping rule: when the resident's compound is unknown we return only
globally-scoped rules, and separately report whether compound-specific rules
exist for the same topic. The caller uses that to ask which compound the
resident is in rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.providers.embeddings import get_embedding_provider
from app.services.intent import FINE_LOOKUP
from app.services.language import normalise_for_search

VIOLATION = "violation"
POLICY = "policy"


@dataclass
class RetrievedRecord:
    kind: str
    record_id: str
    category_id: str
    score: float
    vector_score: float
    lexical_score: float
    payload: dict

    @property
    def citation(self) -> str:
        return self.record_id


@dataclass
class RetrievalResult:
    records: list[RetrievedRecord] = field(default_factory=list)
    policy_version: str | None = None
    compound_specific_alternatives: bool = False
    top_score: float = 0.0
    score_margin: float = 0.0

    @property
    def violations(self) -> list[RetrievedRecord]:
        return [r for r in self.records if r.kind == VIOLATION]

    @property
    def policies(self) -> list[RetrievedRecord]:
        return [r for r in self.records if r.kind == POLICY]

    @property
    def record_ids(self) -> list[str]:
        return [r.record_id for r in self.records]

    @property
    def penalties(self) -> set[int]:
        return {r.payload["penalty_egp"] for r in self.violations}


_SCOPE_SQL = """
    v.is_active = TRUE
    AND t.effective_from <= :as_of
    AND (t.effective_until IS NULL OR t.effective_until >= :as_of)
    AND (t.compound IS NULL OR t.compound = :compound)
    AND (t.phase IS NULL OR t.phase = :phase)
"""

_SEARCH_TEMPLATE = """
SELECT
    t.record_id,
    t.category_id,
    {columns},
    1 - (t.embedding <=> (:qvec)::vector) AS vector_score,
    GREATEST(
        similarity(t.search_text, :q),
        word_similarity(:q, t.search_text)
    ) AS lexical_score,
    v.version AS policy_version
FROM {table} AS t
JOIN policy_versions AS v ON v.id = t.version_id
WHERE {scope}
-- Rank on the fused score, not on vector distance alone: ordering by distance
-- and then re-scoring in Python would drop a strong lexical match that the
-- vector index happens to rank low, and it would never reach the candidate set.
ORDER BY (
    :vector_weight * (1 - (t.embedding <=> (:qvec)::vector))
    + :lexical_weight * GREATEST(
        similarity(t.search_text, :q),
        word_similarity(:q, t.search_text)
    )
) DESC
LIMIT :candidate_limit
"""

_VIOLATION_COLUMNS = (
    "t.violation_en, t.violation_ar, t.penalty_egp, t.action_en, t.action_ar, "
    "t.related_policy_ids, t.page_en, t.page_ar, t.compound, t.phase"
)
_POLICY_COLUMNS = (
    "t.rule_en, t.rule_ar, t.src_en, t.src_ar, t.page_en, t.page_ar, t.compound, t.phase"
)


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{v:.6f}" for v in vector) + "]"


def _fetch(
    db: Session,
    table: str,
    columns: str,
    *,
    qvec: str,
    query: str,
    as_of: date,
    compound: str | None,
    phase: str | None,
    candidate_limit: int,
    vector_weight: float,
    lexical_weight: float,
) -> list[dict]:
    sql = _SEARCH_TEMPLATE.format(table=table, columns=columns, scope=_SCOPE_SQL)
    rows = db.execute(
        text(sql),
        {
            "qvec": qvec,
            "q": query,
            "as_of": as_of,
            "compound": compound,
            "phase": phase,
            "candidate_limit": candidate_limit,
            "vector_weight": vector_weight,
            "lexical_weight": lexical_weight,
        },
    ).mappings()
    return [dict(row) for row in rows]


def _compound_specific_exists(
    db: Session, category_ids: list[str], as_of: date
) -> bool:
    """Do compound-scoped rules exist for these topics? Drives the clarify path."""
    if not category_ids:
        return False
    sql = text(
        """
        SELECT EXISTS (
            SELECT 1 FROM policies t JOIN policy_versions v ON v.id = t.version_id
            WHERE v.is_active AND t.compound IS NOT NULL
              AND t.category_id = ANY(:cats)
              AND t.effective_from <= :as_of
              AND (t.effective_until IS NULL OR t.effective_until >= :as_of)
            UNION ALL
            SELECT 1 FROM violations t JOIN policy_versions v ON v.id = t.version_id
            WHERE v.is_active AND t.compound IS NOT NULL
              AND t.category_id = ANY(:cats)
              AND t.effective_from <= :as_of
              AND (t.effective_until IS NULL OR t.effective_until >= :as_of)
            LIMIT 1
        )
        """
    )
    return bool(db.execute(sql, {"cats": category_ids, "as_of": as_of}).scalar())


def search(
    db: Session,
    query: str,
    *,
    intent: str,
    category_hints: list[str] | None = None,
    compound: str | None = None,
    phase: str | None = None,
    as_of: date | None = None,
    top_k: int | None = None,
) -> RetrievalResult:
    settings = get_settings()
    as_of = as_of or date.today()
    top_k = top_k or settings.retrieval_top_k
    hints = set(category_hints or [])

    lexical_query = normalise_for_search(query)
    qvec = _vector_literal(get_embedding_provider().embed_one(lexical_query))
    candidate_limit = max(top_k * 3, 24)

    violation_rows = _fetch(
        db, "violations", _VIOLATION_COLUMNS,
        qvec=qvec, query=lexical_query, as_of=as_of,
        compound=compound, phase=phase, candidate_limit=candidate_limit,
        vector_weight=settings.vector_weight, lexical_weight=settings.lexical_weight,
    )
    policy_rows = _fetch(
        db, "policies", _POLICY_COLUMNS,
        qvec=qvec, query=lexical_query, as_of=as_of,
        compound=compound, phase=phase, candidate_limit=candidate_limit,
        vector_weight=settings.vector_weight, lexical_weight=settings.lexical_weight,
    )

    # A fine question is answered from the violations table; the related rule is
    # supporting context. Any other question inverts that ordering.
    kind_bonus = {VIOLATION: 0.10, POLICY: 0.0} if intent == FINE_LOOKUP else {VIOLATION: 0.0, POLICY: 0.06}

    records: list[RetrievedRecord] = []
    policy_version: str | None = None

    for kind, rows in ((VIOLATION, violation_rows), (POLICY, policy_rows)):
        for row in rows:
            policy_version = policy_version or row.get("policy_version")
            vector_score = max(0.0, float(row.pop("vector_score") or 0.0))
            lexical_score = max(0.0, float(row.pop("lexical_score") or 0.0))
            category_id = row["category_id"]
            score = (
                settings.vector_weight * vector_score
                + settings.lexical_weight * lexical_score
                + (0.08 if category_id in hints else 0.0)
                + kind_bonus[kind]
            )
            row.pop("policy_version", None)
            records.append(
                RetrievedRecord(
                    kind=kind,
                    record_id=row.pop("record_id"),
                    category_id=category_id,
                    score=round(min(score, 1.0), 4),
                    vector_score=round(vector_score, 4),
                    lexical_score=round(lexical_score, 4),
                    payload=row,
                )
            )

    records.sort(key=lambda r: r.score, reverse=True)
    top = records[:top_k]

    result = RetrievalResult(records=top, policy_version=policy_version)
    if top:
        result.top_score = top[0].score
        result.score_margin = round(top[0].score - (top[1].score if len(top) > 1 else 0.0), 4)
    if compound is None:
        result.compound_specific_alternatives = _compound_specific_exists(
            db, [r.category_id for r in top], as_of
        )
    return result
