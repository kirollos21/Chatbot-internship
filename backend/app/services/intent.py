"""Intent classification.

Deliberately rule-based and multilingual, not model-based: intent decides
*which store to query* (violations vs policies vs the facility/contact
directories), and that routing must be predictable and auditable. Franco terms
are matched on their consonant skeleton so spelling variants all hit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.language import LATIN_TOKEN, skeleton

FINE_LOOKUP = "fine_lookup"
POLICY_QUESTION = "policy_question"
FACILITY_LOOKUP = "facility_lookup"
CONTACT_LOOKUP = "contact_lookup"
REPORT_VIOLATION = "report_violation"
GREETING = "greeting"
UNKNOWN = "unknown"

# --- keyword banks ------------------------------------------------------
# `en` matches on lowercase substrings, `ar` on raw substrings, `franco` on
# consonant skeletons of individual tokens.
_INTENT_KEYWORDS: dict[str, dict[str, list[str]]] = {
    FINE_LOOKUP: {
        "en": ["fine", "fines", "penalty", "penalties", "how much", "cost me", "charged", "egp"],
        "ar": ["غرامة", "الغرامة", "غرامات", "كام", "عقوبة", "مخالفة", "المخالفة", "جنيه"],
        "franco": ["grm", "mxlf", "km", "3qb"],
    },
    CONTACT_LOOKUP: {
        # The service words (maintenance/security/...) are here as well as in the
        # category bank: "feen ra2m el maintenance" must route to the directory,
        # not to the facilities tab, and `feen` alone would otherwise win.
        "en": ["phone", "number", "contact", "call", "hotline", "reach", "emergency",
               "maintenance", "security", "ambulance"],
        "ar": ["رقم", "تليفون", "هاتف", "اتصال", "الطوارئ", "خط ساخن", "صيانة", "الأمن", "إسعاف"],
        # ra2m -> "rm" (the 2 is a glottal stop), raqm/ra8m -> "rqm".
        "franco": ["rqm", "rm", "tlfn", "twr", "sn", "syn"],
    },
    FACILITY_LOOKUP: {
        "en": ["where is", "nearest", "opening hours", "open", "close", "closes", "location", "gym", "playground", "pool hours"],
        "ar": ["فين", "أقرب", "اقرب", "مواعيد", "ساعات العمل", "مكان", "بيفتح", "بيقفل"],
        "franco": ["fn", "qrb", "mw3d", "mkn"],
    },
    REPORT_VIOLATION: {
        "en": ["report a violation", "report violation", "i want to report", "complain", "complaint"],
        "ar": ["أبلغ", "ابلغ", "بلاغ", "شكوى", "أشتكي"],
        "franco": ["blg", "ckw"],
    },
    GREETING: {
        "en": ["hello", "hi ", "good morning", "good evening", "thanks", "thank you"],
        "ar": ["السلام عليكم", "صباح الخير", "مساء الخير", "شكرا", "شكرًا", "أهلا", "اهلا"],
        "franco": ["slm", "sbh", "ckr", "hl"],
    },
}

# Category routing hints. Used to bias retrieval toward the right slice; never
# used to *decide* an answer.
_CATEGORY_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "waste_management": {
        "en": ["waste", "garbage", "rubbish", "trash", "debris", "burning", "paint spill"],
        "ar": ["قمامة", "مخلفات", "زبالة", "حرق", "دهانات"],
        "franco": ["qmm", "mxlf", "zbl", "hrq"],
    },
    "rental_regulations": {
        "en": ["rent", "rental", "lease", "sublease", "tenant", "signage", "advertis"],
        "ar": ["إيجار", "ايجار", "تأجير", "الباطن", "لافتة", "إعلان"],
        "franco": ["yjr", "tjr", "lft"],
    },
    "elevator_regulations": {
        "en": ["elevator", "lift"],
        "ar": ["مصعد", "أسانسير", "المصاعد"],
        "franco": ["ms3d", "msd", "snsr"],
    },
    "pet_regulations": {
        "en": ["pet", "pets", "dog", "dogs", "cat", "leash", "muzzle", "barking", "vaccination"],
        "ar": ["حيوان", "حيوانات", "كلب", "كلاب", "قطة", "سلسلة", "كمامة", "نباح", "تطعيم"],
        "franco": ["hywn", "klb", "qt", "slsl", "kmm"],
    },
    "general_site_regulations": {
        "en": ["noise", "party", "parties", "fireworks", "generator", "barbecue", "bbq", "hookah",
               "shisha", "vandal", "qr code", "gathering", "assault", "landscap", "tree", "planting"],
        "ar": ["ضوضاء", "إزعاج", "حفلة", "حفلات", "ألعاب نارية", "مولد", "شواء", "شيشة",
               "تخريب", "تجمع", "اعتداء", "زراعة", "أشجار"],
        "franco": ["dwd", "z3j", "hfl", "cwy", "cc", "tjm3", "zr3", "cjr"],
    },
    "vehicle_regulations": {
        "en": ["park", "parking", "car", "vehicle", "speed", "driving", "licence", "license",
               "golf cart", "caravan", "sidewalk", "grass"],
        "ar": ["ركن", "الركنة", "عربية", "سيارة", "مركبة", "سرعة", "قيادة", "رخصة",
               "جولف", "كرافان", "رصيف", "زرع", "الزرع"],
        "franco": ["rkn", "3rby", "syr", "mrkb", "sr3", "qyd", "rxs", "rsf", "zr3"],
    },
    "swimming_pool_regulations": {
        "en": ["pool", "swim", "swimming", "sunbed", "lounger", "swimwear", "diaper"],
        "ar": ["حمام السباحة", "المسبح", "سباحة", "شازلونج", "مايوه", "حفاضة"],
        "franco": ["hmm", "sbh", "msbh", "czlnj"],
    },
    "playground_regulations": {
        "en": ["playground", "play area", "kids area", "children area", "slide", "swing"],
        "ar": ["منطقة الألعاب", "ألعاب الأطفال", "ملعب الأطفال"],
        "franco": ["l3b", "tfl"],
    },
    "maintenance_modifications": {
        "en": ["pergola", "facade", "façade", "paint", "renovat", "finishing", "modif", "permit",
               "jacuzzi", "satellite", "solar", "camera", "air conditioner", "a/c", "garage",
               "worker", "workshop", "shaft", "drainage", "balcony", "roof"],
        "ar": ["برجولة", "برجولات", "واجهة", "دهان", "تشطيب", "تعديل", "تصريح", "جاكوزي",
               "ستالايت", "سخان شمسي", "كاميرا", "تكييف", "جراج", "عمال", "ورشة", "منور",
               "غرف الصرف", "السطح"],
        "franco": ["brjl", "wjh", "dhn", "tctb", "t3dl", "tsrh", "jkz", "kmr", "tkyf",
                   "jrj", "3ml", "wrc"],
    },
    "north_coast_beach": {
        "en": ["beach", "north coast", "sahel", "lagoon", "cabin", "cabana", "lifeguard", "buggy"],
        "ar": ["الشاطئ", "شاطئ", "الساحل الشمالي", "البحيرة", "البحيرات", "الكبائن", "الإنقاذ", "بيتش باجي"],
        "franco": ["ct2", "shl", "bhr", "kbn", "bj"],
    },
}


@dataclass
class IntentResult:
    intent: str
    confidence: float
    category_hints: list[str]
    matched: list[str]


# Franco function words, excluded before skeletonisation.
#
# A skeleton drops vowels and collapses repeated consonants, which makes some
# function words indistinguishable from real keywords: `momken` ("is it
# possible") reduces to `mkn`, exactly like `makan` ("place"). Since `mkn` is a
# facility keyword, every question opening with "momken ..." - the commonest way
# to start a Franco question - was routed to the facilities directory and
# answered with opening hours instead of the rule that was asked about.
#
# Excluded by spelling rather than by skeleton, so `makan` itself still matches.
_FRANCO_FUNCTION_WORDS = frozenset(
    {
        "momken", "momkin", "mumkin", "momkn", "yenfa3", "ynfa3", "yenfa",
        "3ayez", "3ayza", "3awez", "3awza", "3aiz",
        "ana", "enta", "enti", "enty", "e7na", "howa", "heya",
        "da", "di", "de", "dah", "deh", "dee",
        "eh", "ezay", "ezzay", "leh", "lih", "keda", "kda", "bas", "kol",
        "fel", "fil", "bel", "bil", "wel", "3al", "3ala", "el", "al",
        "lw", "law", "aw", "wala", "ya",
    }
)


def _token_skeletons(text: str) -> set[str]:
    return {
        sk
        for token in LATIN_TOKEN.findall(text)
        if token.lower() not in _FRANCO_FUNCTION_WORDS
        for sk in (skeleton(token),)
        if len(sk) >= 2
    }


def _score_bank(text_lower: str, raw: str, skeletons: set[str], bank: dict[str, list[str]]) -> tuple[int, list[str]]:
    hits: list[str] = []
    for kw in bank.get("en", []):
        if kw in text_lower:
            hits.append(kw)
    for kw in bank.get("ar", []):
        if kw in raw:
            hits.append(kw)
    for sk in bank.get("franco", []):
        if sk in skeletons:
            hits.append(f"~{sk}")
    return len(hits), hits


def classify_intent(text: str) -> IntentResult:
    raw = (text or "").strip()
    lower = raw.lower()
    skeletons = _token_skeletons(raw)

    scores: dict[str, tuple[int, list[str]]] = {}
    for intent, bank in _INTENT_KEYWORDS.items():
        score, hits = _score_bank(lower, raw, skeletons, bank)
        if score:
            scores[intent] = (score, hits)

    category_hints: list[str] = []
    for category, bank in _CATEGORY_KEYWORDS.items():
        score, _ = _score_bank(lower, raw, skeletons, bank)
        if score:
            category_hints.append(category)

    if not scores:
        # No intent keyword but a recognisable topic => treat as a policy question.
        if category_hints:
            return IntentResult(POLICY_QUESTION, 0.55, category_hints, [])
        return IntentResult(UNKNOWN, 0.2, [], [])

    # A greeting only wins when nothing substantive was asked.
    if GREETING in scores and len(scores) > 1:
        scores.pop(GREETING)

    intent, (score, hits) = max(scores.items(), key=lambda kv: kv[1][0])
    confidence = min(0.95, 0.5 + 0.15 * score)

    if intent == GREETING and not category_hints:
        return IntentResult(GREETING, confidence, [], hits)

    return IntentResult(intent, confidence, category_hints, hits)
