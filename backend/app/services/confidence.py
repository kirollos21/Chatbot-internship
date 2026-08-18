"""Confidence scoring and the clarify/escalate decision."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.intent import FACILITY_LOOKUP, FINE_LOOKUP, POLICY_QUESTION, UNKNOWN
from app.services.retrieval import RetrievalResult

HIGH = "high"
MEDIUM = "medium"
LOW = "low"

_WORD = re.compile(r"\w+", re.UNICODE)

# Questions that cannot be answered without knowing what "this" refers to.
_DEICTIC = {
    "en": ["is this allowed", "can i do this", "what is the fine for this", "is it allowed", "what about this"],
    "ar": ["ده مسموح", "هل ده مسموح", "الغرامة كام على ده", "ينفع كده"],
}


@dataclass
class ConfidenceAssessment:
    score: float
    band: str
    reasons: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    clarification_topic: str | None = None

    @property
    def should_escalate(self) -> bool:
        return self.band == LOW


def assess(
    query: str,
    retrieval: RetrievalResult,
    *,
    intent: str,
    category_hints: list[str],
    compound: str | None,
) -> ConfidenceAssessment:
    settings = get_settings()
    reasons: list[str] = []

    if not retrieval.records:
        return ConfidenceAssessment(0.0, LOW, ["no_matching_records"])

    score = retrieval.top_score
    reasons.append(f"top_score={retrieval.top_score}")

    # A clear winner is worth more than a cluster of near-ties.
    if retrieval.score_margin >= 0.08:
        score += 0.05
        reasons.append("clear_margin")
    elif retrieval.score_margin < 0.02:
        score -= 0.05
        reasons.append("ambiguous_margin")

    # Intent/route agreement.
    if intent == FINE_LOOKUP:
        if retrieval.violations:
            score += 0.05
            reasons.append("fine_intent_matched_violation")
        else:
            score -= 0.20
            reasons.append("fine_intent_without_violation_record")
    elif intent in (POLICY_QUESTION, FACILITY_LOOKUP) and retrieval.policies:
        score += 0.03
        reasons.append("policy_intent_matched_rule")
    elif intent == UNKNOWN:
        score -= 0.08
        reasons.append("unknown_intent")

    if not category_hints:
        score -= 0.05
        reasons.append("no_topic_signal")

    lowered = query.lower().strip()
    if any(p in lowered for p in _DEICTIC["en"]) or any(p in query for p in _DEICTIC["ar"]):
        score -= 0.30
        reasons.append("deictic_query_without_referent")
    elif len(_WORD.findall(query)) <= 2:
        score -= 0.15
        reasons.append("very_short_query")

    score = max(0.0, min(1.0, round(score, 4)))

    if score >= settings.confidence_high:
        band = HIGH
    elif score >= settings.confidence_low:
        band = MEDIUM
    else:
        band = LOW

    assessment = ConfidenceAssessment(score, band, reasons)

    # The answer could differ by compound and we do not know the resident's.
    # Never guess: ask. This caps confidence regardless of retrieval score.
    if compound is None and retrieval.compound_specific_alternatives:
        assessment.needs_clarification = True
        assessment.clarification_topic = "compound"
        assessment.reasons.append("compound_dependent_answer")
        if assessment.band == HIGH:
            assessment.band = MEDIUM

    return assessment
