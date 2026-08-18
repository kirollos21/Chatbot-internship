"""Language detection and Franco tolerance."""

from __future__ import annotations

import pytest

from app.services.language import (
    detect_language,
    franco_lexicon_hit,
    normalise_for_search,
    skeleton,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what is the fine for parking on the grass?", "en"),
        ("Can I build a pergola in my garden?", "en"),
        ("ايه غرامة الركنة على الزرع؟", "ar"),
        ("هل يسمح باصطحاب الكلب إلى الشاطئ؟", "ar"),
        ("fe kam ghrama 3ala el parking 3al zar3?", "franco"),
        ("feen ra2m el maintenance?", "franco"),
    ],
)
def test_detects_primary_languages(text: str, expected: str) -> None:
    assert detect_language(text).language == expected


def test_mixed_arabic_and_english_is_flagged_mixed() -> None:
    result = detect_language("هو ال pool allowed للضيوف؟")
    assert result.language == "mixed"
    # A mixed question still needs a single language to answer in.
    assert result.response_language in ("ar", "en")


def test_mixed_arabic_and_english_second_example() -> None:
    assert detect_language("هو ال pool allowed after 8?").language == "mixed"


# --- the spelling-variation requirement --------------------------------

def test_franco_spelling_variants_share_a_skeleton() -> None:
    """7abibi and 7abeby are the same word spelled two ways."""
    assert skeleton("7abibi") == skeleton("7abeby")


@pytest.mark.parametrize(
    "a,b",
    [
        ("7abibi", "7abeby"),
        ("shokran", "4okran"),
        ("mamnoo3", "mamnou3"),
        ("masmoo7", "masmouh"),
        ("mokhalfa", "mo5alfa"),
        ("ghrama", "3'rama"),
        ("delwa2ty", "delwa2ti"),
    ],
)
def test_variant_pairs_converge(a: str, b: str) -> None:
    assert skeleton(a) == skeleton(b), f"{a} / {b} should normalise to the same skeleton"


@pytest.mark.parametrize("word", ["7abibi", "7abeby", "3ayez", "ghrama", "mokhalfa"])
def test_lexicon_recognises_variants(word: str) -> None:
    assert franco_lexicon_hit(word)


def test_plain_numbers_are_not_franco_digits() -> None:
    """A penalty amount must not make an English sentence look like Franco."""
    assert detect_language("the fine is 5000 EGP for burning waste").language == "en"


def test_arabic_only_is_not_mixed() -> None:
    assert detect_language("ما هي غرامة إلقاء القمامة في غير الأماكن المخصصة؟").language == "ar"


def test_normalise_for_search_appends_skeleton() -> None:
    normalised = normalise_for_search("ghrama 3ala el parking")
    assert "ghrama" in normalised          # the raw query survives
    assert skeleton("ghrama") in normalised  # and the skeleton is added


def test_empty_input_is_safe() -> None:
    result = detect_language("")
    assert result.language == "en"
    assert result.confidence == 0.0
