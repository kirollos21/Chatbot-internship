"""Answer generation with a hard integrity guard.

Order of authority: **verified data > retrieval > LLM phrasing.**

The LLM receives the retrieved records and rewrites them in the resident's
language. Before the answer leaves this module, `enforce_integrity` re-reads
every number in the generated text and checks it against the numbers that
appear in the retrieved source records. A figure the sources do not contain
means the model altered or invented one, and the generated answer is discarded
in favour of a deterministic rendering of the same records. That makes an
invented fine structurally impossible to ship, rather than merely discouraged
by the prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.confidence import HIGH, LOW, ConfidenceAssessment
from app.services.intent import FINE_LOOKUP
from app.providers.llm import LLMResult, get_llm_provider
from app.services.retrieval import RetrievalResult, RetrievedRecord

# Placeholder shapes that must never reach a resident.
_PLACEHOLDER = re.compile(r"X{3,}|\bXXXX\b", re.IGNORECASE)
# Any integer of 2+ digits, with or without thousands separators.
_NUMBER = re.compile(r"\d[\d,٬،.]*\d|\d{2,}")

_SYSTEM_PROMPT = """You are the Palm Hills resident assistant. You explain verified community \
regulations to residents of Palm Hills communities.

AUTHORITY RULES — these are absolute:
1. The SOURCE RECORDS below are the only facts you may state. You have no other knowledge of \
Palm Hills rules, fines, contacts, facilities or hours.
2. Never change, round, estimate, convert or re-express a penalty amount. Write it exactly as \
given, in EGP.
3. Never write "probably", "usually", "around", "approximately", "I believe" or "it may be" \
about a rule or a penalty.
4. Never invent a rule, a phone number, a facility, an address or an opening time.
5. If the source records do not answer the question, say plainly that you cannot verify it from \
the current community regulations and offer to escalate to Community Management.
6. Cite the record IDs you used at the end of the answer, e.g. "Source: V034".

LANGUAGE:
- Answer in the requested response language and nothing else.
- English -> natural English. Arabic -> Modern Standard Arabic with Egyptian phrasing.
- Franco -> Egyptian Franco-Arabic (Latin letters + digits: 2=ء/أ, 3=ع, 4=ش, 5=خ, 6=ط, 7=ح, \
8=ق, 9=ص, 3'=غ, 6'=ظ, 9'=ض). In Franco you may write the connective and explanatory language \
freely, but the rule scope, the violation description and the penalty amount must be reproduced \
exactly as they appear in the source records — copy them verbatim rather than translating them.

STYLE: concise and practical, like a helpful community office, not a chatbot. Lead with the \
direct answer. State the fine and the action taken when the records include them."""


@dataclass
class GeneratedAnswer:
    text: str
    language: str
    source_ids: list[str] = field(default_factory=list)
    generator: str = "template"
    model: str | None = None
    integrity_guard_triggered: bool = False
    guard_reason: str | None = None


# --------------------------------------------------------------------------
# Source rendering
# --------------------------------------------------------------------------

def _record_block(record: RetrievedRecord) -> str:
    p = record.payload
    if record.kind == "violation":
        return (
            f"[{record.record_id}] VIOLATION (category: {record.category_id})\n"
            f"  english: {p['violation_en']}\n"
            f"  arabic: {p['violation_ar']}\n"
            f"  penalty_egp: {p['penalty_egp']}\n"
            f"  action_english: {p['action_en']}\n"
            f"  action_arabic: {p['action_ar']}"
        )
    return (
        f"[{record.record_id}] RULE (category: {record.category_id})\n"
        f"  english: {p['rule_en']}\n"
        f"  arabic: {p['rule_ar']}"
    )


def build_user_prompt(
    query: str,
    retrieval: RetrievalResult,
    *,
    response_language: str,
    detected_language: str,
    confidence: ConfidenceAssessment,
    compound: str | None,
) -> str:
    blocks = "\n\n".join(_record_block(r) for r in retrieval.records) or "(no records retrieved)"
    lines = [
        f"RESIDENT QUESTION: {query}",
        f"DETECTED LANGUAGE: {detected_language}",
        f"RESPONSE LANGUAGE: {response_language}",
        f"RESIDENT COMPOUND: {compound or 'unknown'}",
        f"RETRIEVAL CONFIDENCE: {confidence.band} ({confidence.score})",
        f"POLICY VERSION: {retrieval.policy_version or 'unknown'}",
        "",
        "SOURCE RECORDS:",
        blocks,
    ]
    if confidence.needs_clarification and confidence.clarification_topic == "compound":
        lines.append(
            "\nNOTE: the answer may differ by compound and the resident's compound is unknown. "
            "Ask which Palm Hills compound or phase they are in before giving a definitive answer."
        )
    if confidence.band == LOW:
        lines.append(
            "\nNOTE: retrieval confidence is low. Do not attempt an answer. Say you cannot verify "
            "this from the current community regulations and offer to escalate to Community Management."
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Deterministic renderers (fallback and guard replacement)
# --------------------------------------------------------------------------

_LOW_CONFIDENCE = {
    "en": (
        "I couldn't confidently verify this from the current community regulations. "
        "Would you like me to escalate this to Community Management?"
    ),
    "ar": (
        "لم أتمكن من التأكد من هذه المعلومة من لوائح المجتمع الحالية. "
        "هل تحب أن أحوّل الاستفسار إلى إدارة المجتمعات؟"
    ),
    "franco": (
        "Ma2dartsh at2akked mel ma3loma di men lawa2e7 el mogtama3 el 7aliya. "
        "Te7eb a7awwel el mawdoo3 le Community Management?"
    ),
}

_CLARIFY_COMPOUND = {
    "en": "Which Palm Hills compound or phase are you in? The answer can differ between locations.",
    "ar": "في أي كمبوند أو مرحلة من بالم هيلز حضرتك؟ الإجابة ممكن تختلف من مكان لآخر.",
    "franco": "Enta f anhi compound aw phase fe Palm Hills? El egaba momken tekhtelef men makan le makan.",
}

_LABELS = {
    "en": {
        "violation": "Violation", "fine": "Fine", "action": "Action taken",
        "rule": "Rule", "source": "Source", "egp": "EGP",
        "lead": "According to the Palm Hills community regulations:",
    },
    "ar": {
        "violation": "المخالفة", "fine": "الغرامة", "action": "الإجراء المتخذ",
        "rule": "اللائحة", "source": "المصدر", "egp": "جنيه مصري",
        "lead": "وفقاً للوائح المجتمع السكني في بالم هيلز:",
    },
    "franco": {
        "violation": "El mokhalfa", "fine": "El ghrama", "action": "El egraa2 el motakhaz",
        "rule": "El la2e7a", "source": "Source", "egp": "EGP",
        "lead": "7asab lawa2e7 el mogtama3 fe Palm Hills:",
    },
}


def _fmt_amount(value: int) -> str:
    return f"{value:,}"


def render_deterministic(
    retrieval: RetrievalResult,
    *,
    language: str,
    confidence: ConfidenceAssessment,
) -> str:
    lang = language if language in _LABELS else "en"
    labels = _LABELS[lang]

    if confidence.band == LOW or not retrieval.records:
        return _LOW_CONFIDENCE[lang]

    parts: list[str] = [labels["lead"], ""]

    for violation in retrieval.violations[:2]:
        p = violation.payload
        desc = p["violation_ar"] if lang == "ar" else p["violation_en"]
        action = p["action_ar"] if lang == "ar" else p["action_en"]
        parts.append(f"{labels['violation']}: {desc}")
        parts.append(f"{labels['fine']}: {_fmt_amount(p['penalty_egp'])} {labels['egp']}")
        parts.append(f"{labels['action']}: {action}")
        parts.append("")

    for policy in retrieval.policies[:2]:
        p = policy.payload
        rule = p["rule_ar"] if lang == "ar" else p["rule_en"]
        parts.append(f"{labels['rule']}: {rule}")
        parts.append("")

    if confidence.needs_clarification and confidence.clarification_topic == "compound":
        parts.append(_CLARIFY_COMPOUND[lang])
        parts.append("")

    parts.append(f"{labels['source']}: {', '.join(r.record_id for r in retrieval.records[:4])}")
    return "\n".join(parts).strip()


# --------------------------------------------------------------------------
# Integrity guard
# --------------------------------------------------------------------------

def _normalise_number(token: str) -> str:
    return re.sub(r"[,٬،.\s]", "", token)


def allowed_numbers(retrieval: RetrievalResult) -> set[str]:
    """Every number that legitimately appears in the retrieved source records."""
    allowed: set[str] = set()
    for record in retrieval.records:
        allowed.add(str(record.payload.get("penalty_egp", "")).strip())
        for value in record.payload.values():
            if isinstance(value, str):
                for match in _NUMBER.findall(value):
                    allowed.add(_normalise_number(match))
        # Record IDs carry digits (V034 -> 034), as do the related-rule IDs.
        allowed.add(re.sub(r"\D", "", record.record_id))
        for related in record.payload.get("related_policy_ids") or []:
            allowed.add(re.sub(r"\D", "", str(related)))
    allowed.discard("")
    return allowed


def enforce_integrity(text: str, retrieval: RetrievalResult) -> tuple[bool, str | None]:
    """Return (ok, reason). `ok=False` means the generated text must be discarded."""
    if _PLACEHOLDER.search(text):
        return False, "placeholder_leaked"

    permitted = allowed_numbers(retrieval)
    for match in _NUMBER.finditer(text):
        # Digits glued to a letter are part of an identifier (V034, P040),
        # not a quantity the model chose.
        if match.start() > 0 and text[match.start() - 1].isalpha():
            continue
        value = _normalise_number(match.group())
        if not value or len(value) < 2:
            continue
        if value in permitted:
            continue
        # Tolerate a source figure written with its own digits split by units,
        # e.g. "5000 EGP" vs "5,000 EGP" — already normalised — but nothing else.
        return False, f"unverified_number:{value}"

    hedges = ("probably", "approximately", "i believe", "it may be", "around ")
    lowered = text.lower()
    if retrieval.violations and any(h in lowered for h in hedges):
        return False, "hedged_penalty_language"

    return True, None


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def generate_answer(
    query: str,
    retrieval: RetrievalResult,
    *,
    response_language: str,
    detected_language: str,
    confidence: ConfidenceAssessment,
    compound: str | None,
    intent: str,
) -> GeneratedAnswer:
    source_ids = retrieval.record_ids[:4]
    deterministic = render_deterministic(retrieval, language=response_language, confidence=confidence)

    # Low confidence never reaches the model: there is nothing safe to phrase.
    if confidence.band == LOW or not retrieval.records:
        return GeneratedAnswer(
            text=deterministic,
            language=response_language,
            source_ids=source_ids,
            generator="template",
        )

    result: LLMResult = get_llm_provider().generate(
        _SYSTEM_PROMPT,
        build_user_prompt(
            query,
            retrieval,
            response_language=response_language,
            detected_language=detected_language,
            confidence=confidence,
            compound=compound,
        ),
    )

    if not result.text:
        return GeneratedAnswer(
            text=deterministic,
            language=response_language,
            source_ids=source_ids,
            generator="template",
            model=result.model,
            guard_reason=result.error,
        )

    ok, reason = enforce_integrity(result.text, retrieval)
    if not ok:
        return GeneratedAnswer(
            text=deterministic,
            language=response_language,
            source_ids=source_ids,
            generator="template",
            model=result.model,
            integrity_guard_triggered=True,
            guard_reason=reason,
        )

    text = result.text
    if intent == FINE_LOOKUP and confidence.band == HIGH and "Source:" not in text and "المصدر" not in text:
        text = f"{text}\n\nSource: {', '.join(source_ids)}"

    return GeneratedAnswer(
        text=text,
        language=response_language,
        source_ids=source_ids,
        generator=result.provider,
        model=result.model,
    )
