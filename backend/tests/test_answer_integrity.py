"""The integrity guard and the deterministic renderers.

These are the tests that matter most: they are what stops an invented or
altered fine from reaching a resident.
"""

from __future__ import annotations

import pytest

from app.services.answer import (
    enforce_integrity,
    render_deterministic,
)
from app.services.confidence import HIGH, LOW, MEDIUM, ConfidenceAssessment
from app.services.retrieval import POLICY, VIOLATION, RetrievalResult, RetrievedRecord


def _violation(record_id: str = "V034", penalty: int = 500) -> RetrievedRecord:
    return RetrievedRecord(
        kind=VIOLATION,
        record_id=record_id,
        category_id="vehicle_regulations",
        score=0.81,
        vector_score=0.7,
        lexical_score=0.6,
        payload={
            "violation_en": "Parking vehicles in non-designated areas, including sidewalks, "
            "landscaped zones, or spaces reserved for disabilities",
            "violation_ar": "ركن المركبات في غير الأماكن المخصصة لها سواء فوق الرصيف أو الزراعات",
            "penalty_egp": penalty,
            "action_en": "Placement of a violation sticker",
            "action_ar": "وضع ملصق",
            "related_policy_ids": ["P040"],
            "page_en": 23,
            "page_ar": 10,
            "compound": None,
            "phase": None,
        },
    )


def _policy() -> RetrievedRecord:
    return RetrievedRecord(
        kind=POLICY,
        record_id="P040",
        category_id="vehicle_regulations",
        score=0.72,
        vector_score=0.6,
        lexical_score=0.55,
        payload={
            "rule_en": "Parking on sidewalks, landscaped areas, or in spaces reserved for "
            "disabilities is strictly prohibited.",
            "rule_ar": "عدم ركن المركبات في غير الأماكن المخصصة لها.",
            "src_en": "pdf",
            "src_ar": "pdf",
            "page_en": 17,
            "page_ar": 3,
            "compound": None,
            "phase": None,
        },
    )


@pytest.fixture
def retrieval() -> RetrievalResult:
    result = RetrievalResult(records=[_violation(), _policy()], policy_version="1.0")
    result.top_score = 0.81
    result.score_margin = 0.09
    return result


HIGH_CONFIDENCE = ConfidenceAssessment(0.8, HIGH, ["test"])
LOW_CONFIDENCE = ConfidenceAssessment(0.1, LOW, ["test"])


# --- the guard ----------------------------------------------------------

def test_exact_penalty_passes(retrieval: RetrievalResult) -> None:
    ok, reason = enforce_integrity("The fine is 500 EGP. Source: V034", retrieval)
    assert ok, reason


def test_thousands_separator_is_accepted(retrieval: RetrievalResult) -> None:
    result = RetrievalResult(records=[_violation(penalty=5000)], policy_version="1.0")
    ok, reason = enforce_integrity("The fine is 5,000 EGP.", result)
    assert ok, reason


def test_altered_penalty_is_rejected(retrieval: RetrievalResult) -> None:
    """5000 instead of the verified 500 must never ship."""
    ok, reason = enforce_integrity("The fine is 5000 EGP.", retrieval)
    assert not ok
    assert reason is not None and reason.startswith("unverified_number")


def test_invented_penalty_is_rejected(retrieval: RetrievalResult) -> None:
    ok, reason = enforce_integrity("You will be charged 750 EGP for this.", retrieval)
    assert not ok


def test_hedged_penalty_language_is_rejected(retrieval: RetrievalResult) -> None:
    ok, reason = enforce_integrity("The fine is probably 500 EGP.", retrieval)
    assert not ok
    assert reason == "hedged_penalty_language"


def test_placeholder_leak_is_rejected(retrieval: RetrievalResult) -> None:
    ok, reason = enforce_integrity("Call security on XXXXXXXXXX.", retrieval)
    assert not ok
    assert reason == "placeholder_leaked"


def test_numbers_present_in_source_text_are_allowed() -> None:
    """Ages, day counts and times quoted from the rule text are legitimate."""
    record = RetrievedRecord(
        kind=POLICY,
        record_id="P057",
        category_id="swimming_pool_regulations",
        score=0.8,
        vector_score=0.7,
        lexical_score=0.6,
        payload={
            "rule_en": "Children under the age of 14 must be accompanied by an adult.",
            "rule_ar": "يشترط وجود شخص بالغ مع الأطفال دون سن الـ14 عاماً.",
            "src_en": "pdf",
            "src_ar": "pdf",
            "page_en": 18,
            "page_ar": 4,
            "compound": None,
            "phase": None,
        },
    )
    result = RetrievalResult(records=[record], policy_version="1.0")
    ok, reason = enforce_integrity("Children under 14 need an adult with them.", result)
    assert ok, reason


# --- deterministic rendering -------------------------------------------

@pytest.mark.parametrize("language", ["en", "ar", "franco"])
def test_renderer_preserves_the_exact_penalty(retrieval: RetrievalResult, language: str) -> None:
    text = render_deterministic(retrieval, language=language, confidence=HIGH_CONFIDENCE)
    assert "500" in text
    assert "5000" not in text and "5,000" not in text
    assert "V034" in text


def test_franco_answer_reproduces_the_verified_description(retrieval: RetrievalResult) -> None:
    """Franco may flex the connectives; the violation description must not change."""
    text = render_deterministic(retrieval, language="franco", confidence=HIGH_CONFIDENCE)
    source = retrieval.violations[0].payload["violation_en"]
    assert source in text
    assert "El ghrama" in text  # Franco connective wording is present


def test_arabic_answer_uses_the_arabic_source_fields(retrieval: RetrievalResult) -> None:
    text = render_deterministic(retrieval, language="ar", confidence=HIGH_CONFIDENCE)
    assert retrieval.violations[0].payload["violation_ar"] in text


def test_low_confidence_never_asserts_a_fine(retrieval: RetrievalResult) -> None:
    text = render_deterministic(retrieval, language="en", confidence=LOW_CONFIDENCE)
    assert "500" not in text
    assert "escalate" in text.lower()


def test_clarification_is_requested_when_compound_matters(retrieval: RetrievalResult) -> None:
    confidence = ConfidenceAssessment(0.6, MEDIUM, ["test"], needs_clarification=True, clarification_topic="compound")
    text = render_deterministic(retrieval, language="en", confidence=confidence)
    assert "compound" in text.lower()


def test_rendered_answer_passes_its_own_guard(retrieval: RetrievalResult) -> None:
    """Whatever the fallback renderer produces must itself be clean."""
    for language in ("en", "ar", "franco"):
        text = render_deterministic(retrieval, language=language, confidence=HIGH_CONFIDENCE)
        ok, reason = enforce_integrity(text, retrieval)
        assert ok, f"{language}: {reason}"
