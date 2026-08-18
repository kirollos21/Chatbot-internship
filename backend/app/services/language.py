"""Language detection and Egyptian Franco-Arabic normalisation.

Franco-Arabic has no official spelling standard: `7abibi` and `7abeby` are the
same word. A rigid exact-match detector is therefore useless. The approach here
is a **consonant skeleton**:

    7abibi -> habibi -> hbb
    7abeby -> habeby -> hbb

Franco digits map to their Latin equivalents, digraphs collapse to single
symbols, vowels are dropped, and runs are de-duplicated. Two spellings of the
same word converge on the same skeleton, so lookups tolerate variation without
an explicit variant list. A fuzzy pass (difflib) catches the rest.

Detection never decides policy content — it only chooses the language the
answer is written in.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

ARABIC_RANGE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LATIN_TOKEN = re.compile(r"[A-Za-z0-9'`]+")

# Franco digit conventions confirmed by the project owner. Order matters:
# the two-character forms (3', 6', 9') must be replaced before the bare digits.
FRANCO_DIGRAPH_DIGITS: list[tuple[str, str]] = [
    ("3'", "gh"),
    ("6'", "z"),
    ("9'", "d"),
]
FRANCO_DIGITS: dict[str, str] = {
    "2": "",     # ء / أ  — glottal stop, carries no Latin consonant
    "3": "a",    # ع
    "4": "sh",   # ش
    "5": "kh",   # خ
    "6": "t",    # ط
    "7": "h",    # ح
    "8": "q",    # ق
    "9": "s",    # ص
}
FRANCO_DIGIT_CHARS = set(FRANCO_DIGITS) | {"'"}

# Collapse digraphs to single symbols so `kh`/`5`, `sh`/`4` etc. converge.
SKELETON_DIGRAPHS: list[tuple[str, str]] = [
    ("kh", "x"),
    ("gh", "g"),
    ("sh", "c"),
    ("ch", "c"),
    ("th", "t"),
    ("dh", "d"),
    ("ph", "f"),
]
VOWELS = set("aeiou")

# Minimal fallback lexicon, used only if the built dataset is unavailable.
_FALLBACK_FRANCO_WORDS = [
    "3amel eh", "3ayez", "7aga", "7abibi", "5alas", "shokran", "2ana", "2eih",
    "mesh", "enta", "enty", "feen", "leeh", "keda", "3ashan", "ma3lesh",
    "ma3aya", "delwa2ty", "ghrama", "mokhalfa", "kam", "masmoo7", "mamnoo3",
    "sianna", "ra2m", "shate2", "kalb", "3arabeya", "zar3", "tasre7",
]

ENGLISH_HINTS = {
    "the", "is", "are", "what", "how", "much", "can", "i", "my", "a", "an",
    "for", "to", "of", "in", "on", "at", "do", "does", "where", "when", "why",
    "fine", "rule", "allowed", "pool", "beach", "parking", "dog", "please",
    "and", "or", "with", "not", "if", "it", "this", "that", "there", "here",
}


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def franco_to_latin(token: str) -> str:
    """Replace Franco digit conventions with their Latin equivalents."""
    out = token.lower()
    for src, dst in FRANCO_DIGRAPH_DIGITS:
        out = out.replace(src, dst)
    for digit, latin in FRANCO_DIGITS.items():
        out = out.replace(digit, latin)
    return out


def skeleton(token: str) -> str:
    """Consonant skeleton of a Latin/Franco token."""
    out = franco_to_latin(strip_diacritics(token))
    for src, dst in SKELETON_DIGRAPHS:
        out = out.replace(src, dst)
    # A trailing `y` is a long /i/ (final ي), not a consonant: `7abeby` and
    # `7abibi` are the same word. Medial `y` is kept, so `3ayez` survives
    # skeletonisation instead of collapsing to a single letter.
    if out.endswith("y"):
        out = out[:-1]
    out = "".join(c for c in out if c.isalpha() and c not in VOWELS)
    # de-duplicate runs: "hbb" and "hb" should not diverge on gemination
    collapsed: list[str] = []
    for char in out:
        if not collapsed or collapsed[-1] != char:
            collapsed.append(char)
    return "".join(collapsed)


def phrase_skeleton(text: str) -> str:
    return " ".join(s for s in (skeleton(t) for t in LATIN_TOKEN.findall(text)) if s)


@lru_cache
def _franco_lexicon() -> tuple[frozenset[str], dict[str, str]]:
    """(skeletons, skeleton -> canonical franco spelling)."""
    words: list[str] = list(_FALLBACK_FRANCO_WORDS)
    path = Path(get_settings().dataset_path)
    if path.exists():
        try:
            with path.open(encoding="utf-8") as fh:
                notes = json.load(fh).get("franco_arabic_notes", {})
            for bucket in ("vocabulary", "domain_vocabulary"):
                for entry in notes.get(bucket, []):
                    words.append(entry["franco"])
                    words.extend(entry.get("variants", []))
        except (OSError, ValueError, KeyError):
            pass  # fall back to the built-in list

    skeletons: dict[str, str] = {}
    for word in words:
        for part in word.split():
            sk = skeleton(part)
            if len(sk) >= 2:
                skeletons.setdefault(sk, part)
    return frozenset(skeletons), skeletons


def looks_franco_token(token: str) -> bool:
    """A Latin token carrying a Franco digit *between/attached to* letters."""
    if not any(c in FRANCO_DIGIT_CHARS for c in token):
        return False
    if token.isdigit():
        return False  # a plain number such as "5000" is not Franco
    return any(c.isalpha() for c in token)


def franco_lexicon_hit(token: str, cutoff: float = 0.86) -> bool:
    sk = skeleton(token)
    if len(sk) < 2:
        return False
    known, _ = _franco_lexicon()
    if sk in known:
        return True
    for candidate in known:
        if abs(len(candidate) - len(sk)) > 1:
            continue
        if SequenceMatcher(None, sk, candidate).ratio() >= cutoff:
            return True
    return False


@dataclass
class LanguageResult:
    language: str          # en | ar | franco | mixed
    response_language: str # en | ar | franco  (never "mixed")
    confidence: float
    signals: dict = field(default_factory=dict)


def detect_language(text: str) -> LanguageResult:
    raw = (text or "").strip()
    if not raw:
        return LanguageResult("en", "en", 0.0, {"reason": "empty"})

    arabic_chars = len(ARABIC_RANGE.findall(raw))
    letter_chars = sum(1 for c in raw if c.isalpha())
    arabic_ratio = arabic_chars / letter_chars if letter_chars else 0.0

    latin_tokens = [t for t in LATIN_TOKEN.findall(raw) if any(c.isalpha() for c in t)]
    franco_digit_hits = sum(1 for t in latin_tokens if looks_franco_token(t))
    lexicon_hits = sum(1 for t in latin_tokens if franco_lexicon_hit(t))
    english_hits = sum(1 for t in latin_tokens if t.lower() in ENGLISH_HINTS)

    franco_hits = franco_digit_hits + lexicon_hits
    latin_count = len(latin_tokens)
    franco_ratio = franco_hits / latin_count if latin_count else 0.0

    signals = {
        "arabic_ratio": round(arabic_ratio, 3),
        "latin_tokens": latin_count,
        "franco_digit_hits": franco_digit_hits,
        "franco_lexicon_hits": lexicon_hits,
        "english_hits": english_hits,
    }

    franco_like = (
        franco_digit_hits >= 1
        or lexicon_hits >= 2
        or (franco_ratio >= 0.25 and franco_hits >= 1)
    )

    # Arabic script present alongside meaningful Latin content => mixed.
    if arabic_ratio >= 0.15 and latin_count >= 1 and (english_hits or franco_like or latin_count >= 2):
        response = "ar" if arabic_ratio >= 0.4 else "en"
        return LanguageResult("mixed", response, 0.7, signals)

    if arabic_ratio >= 0.5:
        return LanguageResult("ar", "ar", min(0.99, 0.6 + arabic_ratio / 2), signals)

    if franco_like and franco_hits >= english_hits:
        confidence = min(0.95, 0.5 + 0.15 * franco_hits)
        return LanguageResult("franco", "franco", confidence, signals)

    if arabic_ratio > 0:
        return LanguageResult("mixed", "ar" if arabic_ratio >= 0.4 else "en", 0.6, signals)

    return LanguageResult("en", "en", 0.75 if english_hits else 0.5, signals)


def normalise_for_search(text: str) -> str:
    """Query form used by the lexical retrieval layer.

    Franco input is expanded into its Latin skeleton *in addition to* the raw
    text, so `ghrama` and `3'rama` both reach the same lexical index entries.
    """
    raw = (text or "").strip()
    extra = phrase_skeleton(raw)
    return f"{raw} {extra}".strip()
