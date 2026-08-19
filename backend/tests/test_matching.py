"""Concept matching: the layer that makes a reworded question find its record.

These tests are about *phrasing invariance*. The dataset says "pets" and
"landscaped zones"; residents write "dog" and "grass". If those stop meeting,
every paraphrase silently escalates to Community Management — which is exactly
the failure this module was added to fix, so it is worth pinning down.
"""

from __future__ import annotations

import pytest

from app.services.matching import (
    build_record_index,
    concept_matches,
    concept_weights,
    coverage,
    extract_concepts,
)


def _names(query: str) -> set[str]:
    return {c.name for c in extract_concepts(query)}


# --- the same question, written many ways -------------------------------

PARKING_ON_GRASS = [
    "what is the fine for parking on the grass",
    "can I park my car on the lawn?",
    "is parking on the green areas allowed",
    "ايه غرامة الركنة على الزرع؟",
    "fe kam ghrama 3ala el parking 3al zar3?",
    "fe kam 3'rama 3ala el parking 3al zar3?",
]


@pytest.mark.parametrize("query", PARKING_ON_GRASS)
def test_parking_on_grass_reduces_to_the_same_two_concepts(query: str) -> None:
    assert _names(query) == {"vehicle", "landscape"}


@pytest.mark.parametrize(
    "query",
    [
        "can I have a dog on the beach",
        "are pets permitted on the shore",
        "momken akhod el kalb 3al shate2?",
    ],
)
def test_dog_and_pet_and_beach_converge(query: str) -> None:
    assert {"pet", "beach"} <= _names(query)


def test_franco_spelling_variants_produce_identical_concepts() -> None:
    """`ghrama` and `3'rama` are one word; they must not diverge."""
    assert _names("fe kam ghrama 3ala el zar3") == _names("fe kam 3'rama 3ala el zar3")


def test_arabic_orthographic_variation_is_folded() -> None:
    """Hamza carriers and ة/ه are written freely; both spellings must match."""
    assert _names("هل يمكن وضع برجولة في الحديقة؟") == _names(
        "هل يمكن وضع برجوله فى الحديقه؟"
    )


# --- what must NOT become a concept ------------------------------------

def test_a_question_with_no_topic_yields_no_concepts() -> None:
    """"Is this allowed?" names nothing; it must not borrow a topic."""
    assert extract_concepts("Is this allowed?") == []


def test_qualifiers_are_not_topics() -> None:
    """A violation's text states the act, never the word "fine".

    Counting the qualifier would penalise every violation record it is asked
    about, which is the opposite of what a fine question needs.
    """
    assert "fine" not in " ".join(_names("what is the fine"))
    assert _names("what is the fine for burning waste") == {"burning", "waste"}


def test_unknown_words_are_kept_as_literals() -> None:
    """Kept, not discarded: they are how an out-of-scope question scores low."""
    assert _names("what is the wifi password") == {
        "literal:wifi",
        "literal:password",
    }


# --- regressions: consonant-skeleton collisions -------------------------

def test_franco_beach_is_not_read_as_a_cat() -> None:
    """`shate2` (beach) and `cat` share the skeleton `ct`.

    Deriving skeletons from English as well as Franco made the two collide, and
    a Franco beach question came back with pet rules.
    """
    assert "beach" in _names("momken akhod el kalb 3al shate2?")


def test_short_term_is_not_read_as_a_cart() -> None:
    """`short` and `cart` share the skeleton `crt`; "short term" is one thing."""
    assert "rent" in _names("is short term rental allowed")
    assert "buggy" not in _names("is short term rental allowed")


def test_franco_verb_is_not_read_as_workers() -> None:
    """`a3mel` ("I do") and `3ommal` ("workers") share the root m-l."""
    assert "worker" not in _names("momken a3mel bargola fel gnena?")
    assert "worker" in _names("3andi 3ommal fel we7da")


# --- coverage ranks the right record first ------------------------------

_V034 = (
    "Parking vehicles in non-designated areas, including sidewalks, landscaped "
    "zones, or spaces reserved for disabilities"
)
_V042 = "Parking in a non-assigned spot inside the building garage"
_P099 = (
    "Pets are only allowed on the beach during designated hours from 9:00 a.m. "
    "to 11:00 a.m."
)


def test_coverage_prefers_the_record_that_matches_every_concept() -> None:
    concepts = extract_concepts("what is the fine for parking on the grass")
    indexes = [build_record_index(t) for t in (_V034, _V042, _P099)]
    weights = concept_weights(concepts, indexes)

    on_grass, in_garage, unrelated = (
        coverage(concepts, index, weights) for index in indexes
    )
    assert on_grass == 1.0            # parking *and* landscaping
    assert in_garage < on_grass       # parking only
    assert unrelated == 0.0


def test_a_record_matching_nothing_scores_zero() -> None:
    concepts = extract_concepts("can I have a dog on the beach")
    index = build_record_index(_V042)
    weights = concept_weights(concepts, [index])
    assert coverage(concepts, index, weights) == 0.0


def test_no_concepts_means_no_coverage() -> None:
    """An empty question must not score 1.0 for vacuously matching everything."""
    index = build_record_index(_V034)
    assert coverage([], index, {}) == 0.0


def test_dataset_wording_matches_resident_wording() -> None:
    """The pairing the whole module exists for."""
    index = build_record_index(_P099)
    for concept in extract_concepts("dog"):
        assert concept_matches(concept, index)


def test_franco_qualifiers_do_not_collide_with_topics() -> None:
    """Filler skeletons must stay disjoint from the concept table's.

    An overlap does not fail loudly — it quietly deletes a real topic as
    filler, which is how a Franco question loses the very word it was about.
    """
    from app.services.matching import _drop, topic_skeletons

    _, filler = _drop()
    assert not (filler & topic_skeletons()), sorted(filler & topic_skeletons())
