"""Intent routing across the three languages."""

from __future__ import annotations

import pytest

from app.services.intent import (
    CONTACT_LOOKUP,
    FACILITY_LOOKUP,
    FINE_LOOKUP,
    GREETING,
    POLICY_QUESTION,
    REPORT_VIOLATION,
    classify_intent,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("What is the fine for parking on the grass?", FINE_LOOKUP),
        ("ايه غرامة الركنة على الزرع؟", FINE_LOOKUP),
        ("fe kam ghrama 3ala el parking 3al zar3?", FINE_LOOKUP),
        ("What's the security number?", CONTACT_LOOKUP),
        ("feen ra2m el maintenance?", CONTACT_LOOKUP),
        ("Where is the nearest pool?", FACILITY_LOOKUP),
        ("Can I build a pergola?", POLICY_QUESTION),
        ("I want to report a violation", REPORT_VIOLATION),
        ("Hello", GREETING),
    ],
)
def test_intent_routing(text: str, expected: str) -> None:
    assert classify_intent(text).intent == expected


@pytest.mark.parametrize(
    "text,category",
    [
        ("Can I build a pergola?", "maintenance_modifications"),
        ("Can I take my dog to the beach?", "north_coast_beach"),
        ("fine for parking on the sidewalk", "vehicle_regulations"),
        ("هل يمكن اصطحاب الكلب إلى حمام السباحة؟", "pet_regulations"),
        ("burning waste in the garden", "waste_management"),
    ],
)
def test_category_hints(text: str, category: str) -> None:
    assert category in classify_intent(text).category_hints


def test_greeting_yields_to_a_real_question() -> None:
    """"Hi, what's the fine for X" is a fine lookup, not a greeting."""
    assert classify_intent("Hi, what is the fine for burning waste?").intent == FINE_LOOKUP


def test_franco_beach_question_is_routed_by_topic() -> None:
    result = classify_intent("momken akhod el kalb 3al shate2?")
    assert "north_coast_beach" in result.category_hints or "pet_regulations" in result.category_hints


def test_momken_is_not_read_as_makan() -> None:
    """`momken` ("is it possible") must not be mistaken for `makan` ("place").

    A consonant skeleton drops vowels and collapses repeats, so both reduce to
    `mkn`. Because `mkn` is a facility keyword, every question opening with
    "momken ..." — the commonest way to start a Franco question — was routed to
    the facilities directory and answered with opening hours.
    """
    assert classify_intent("momken a3mel pergola fel gnena?").intent == POLICY_QUESTION
    assert classify_intent("momken akhod el kalb 3al shate2?").intent == POLICY_QUESTION


def test_makan_still_routes_to_facilities() -> None:
    """The fix excludes the function word by spelling, not the skeleton."""
    assert classify_intent("emta byeftah el makan?").intent == FACILITY_LOOKUP


def test_franco_filler_does_not_change_routing() -> None:
    """Stripping filler must not disturb the intents that already worked."""
    assert classify_intent("feen ra2m el maintenance?").intent == CONTACT_LOOKUP
    assert classify_intent("fe kam ghrama 3ala el zar3?").intent == FINE_LOOKUP
