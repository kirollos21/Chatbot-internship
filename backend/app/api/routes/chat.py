"""The assistant endpoint.

Routing is explicit rather than "everything through RAG":

    contact question  -> contacts directory   (structured lookup)
    facility question -> facilities directory (structured lookup)
    greeting          -> canned reply, no retrieval
    everything else   -> hybrid retrieval over policies + violations

Each branch ends in the same place: confidence assessment, escalation when the
system cannot verify an answer, and an audit row naming the source records.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import authenticated
from app.db.database import get_db
from app.repositories import catalog
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    LanguageProbe,
    LanguageProbeResponse,
    SourceRef,
)
from app.services import audit as audit_service
from app.services import escalation as escalation_service
from app.services import retrieval as retrieval_service
from app.services.answer import GeneratedAnswer, generate_answer
from app.services.confidence import HIGH, LOW, ConfidenceAssessment, assess
from app.services.intent import (
    CONTACT_LOOKUP,
    FACILITY_LOOKUP,
    GREETING,
    classify_intent,
)
from app.services.language import detect_language, phrase_skeleton

router = APIRouter(prefix="/chat", tags=["assistant"])

_GREETINGS = {
    "en": (
        "Hello! I'm the Palm Hills resident assistant. I can answer questions about the "
        "community regulations, violations and fines, facilities and contacts."
    ),
    "ar": (
        "أهلاً بحضرتك! أنا مساعد سكان بالم هيلز. أقدر أجاوب على أسئلتك عن لوائح المجتمع "
        "والمخالفات والغرامات والمرافق وأرقام التواصل."
    ),
    "franco": (
        "Ahlan beek! Ana el Palm Hills resident assistant. A2dar agaweb 3ala as2eltak 3an "
        "lawa2e7 el mogtama3, el mokhalfat wel gharamat, el facilities wel arkam."
    ),
}

_NO_CONTACT = {
    "en": "I couldn't find that contact in the directory. Would you like me to escalate this to Community Management?",
    "ar": "لم أجد جهة الاتصال المطلوبة في الدليل. هل تحب أن أحوّل الطلب إلى إدارة المجتمعات؟",
    "franco": "Ma la2etsh el raqm dah fel directory. Te7eb a7awwel el talab le Community Management?",
}

_NO_FACILITY = {
    "en": "I couldn't find that facility in the directory yet.",
    "ar": "لم أجد هذا المرفق في الدليل حتى الآن.",
    "franco": "Ma la2etsh el makan dah fel directory lessa.",
}


def _contact_answer(db: Session, query: str, language: str) -> tuple[str, list[str]]:
    role = catalog.role_from_query(query)
    contacts = catalog.list_contacts(db, role=role) if role else catalog.list_contacts(db)
    if not contacts:
        return _NO_CONTACT[language], []

    lines: list[str] = []
    ids: list[str] = []
    for contact in contacts[:3]:
        public = catalog.public_contact(contact, language)
        name = public["name_ar"] if language == "ar" else public["name_en"]
        ids.append(public["id"])
        if public["availability"] == catalog.CONFIGURED:
            hours = f" ({public['hours']})" if public["hours"] else ""
            lines.append(f"{name}: {public['phone']}{hours}")
        else:
            lines.append(f"{name}: {public['message']}")
    return "\n".join(lines), ids


def _facility_answer(db: Session, query: str, language: str, compound: str | None) -> tuple[str, list[str]]:
    facilities = catalog.list_facilities(db, compound=compound)
    if not facilities:
        return _NO_FACILITY[language], []

    lowered = (query or "").lower()
    ranked = sorted(
        facilities,
        key=lambda f: (
            f.name_en.lower() not in lowered and f.facility_type not in lowered,
            f.record_id,
        ),
    )
    lines: list[str] = []
    ids: list[str] = []
    for facility in ranked[:3]:
        public = catalog.public_facility(facility, language)
        name = public["name_ar"] if language == "ar" else public["name_en"]
        ids.append(public["id"])
        detail = public["hours"] or public["message"]
        location = public["location_note"] or public["compound"]
        suffix = f" — {location}" if location else ""
        lines.append(f"{name}{suffix}: {detail}")
    return "\n".join(lines), ids


@router.post("", response_model=ChatResponse, dependencies=[Depends(authenticated)])
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    detection = detect_language(payload.message)
    response_language = payload.language or detection.response_language
    if response_language not in ("en", "ar", "franco"):
        response_language = "en"

    intent_result = classify_intent(payload.message)
    intent = intent_result.intent

    empty = retrieval_service.RetrievalResult()

    # --- structured branches ------------------------------------------
    if intent == GREETING:
        answer = GeneratedAnswer(_GREETINGS[response_language], response_language, [], "template")
        confidence = ConfidenceAssessment(0.9, HIGH, ["greeting"])
        retrieval = empty
    elif intent == CONTACT_LOOKUP:
        text, ids = _contact_answer(db, payload.message, response_language)
        answer = GeneratedAnswer(text, response_language, ids, "directory")
        confidence = ConfidenceAssessment(0.85 if ids else 0.2, HIGH if ids else LOW, ["contact_directory"])
        retrieval = empty
    elif intent == FACILITY_LOOKUP:
        text, ids = _facility_answer(db, payload.message, response_language, payload.compound)
        answer = GeneratedAnswer(text, response_language, ids, "directory")
        confidence = ConfidenceAssessment(0.8 if ids else 0.2, HIGH if ids else LOW, ["facility_directory"])
        retrieval = empty
    else:
        # --- retrieval branch -----------------------------------------
        retrieval = retrieval_service.search(
            db,
            payload.message,
            intent=intent,
            category_hints=intent_result.category_hints,
            compound=payload.compound,
            phase=payload.phase,
            as_of=payload.as_of,
        )
        confidence = assess(
            payload.message,
            retrieval,
            intent=intent,
            category_hints=intent_result.category_hints,
            compound=payload.compound,
        )
        answer = generate_answer(
            payload.message,
            retrieval,
            response_language=response_language,
            detected_language=detection.language,
            confidence=confidence,
            compound=payload.compound,
            intent=intent,
        )

    # --- escalation ---------------------------------------------------
    ticket_id: str | None = None
    if confidence.should_escalate:
        ticket = escalation_service.create_ticket(
            db,
            query=payload.message,
            detected_language=detection.language,
            confidence=confidence,
            retrieval=retrieval,
            reason="low_confidence",
            compound=payload.compound,
            phase=payload.phase,
            user_id=payload.user_id,
        )
        ticket_id = ticket.ticket_id

    entry = audit_service.write_audit(
        db,
        query=payload.message,
        detected_language=detection.language,
        intent=intent,
        compound=payload.compound,
        phase=payload.phase,
        retrieval=retrieval,
        confidence=confidence,
        answer=answer,
        user_id=payload.user_id,
        session_id=payload.session_id,
        escalated=ticket_id is not None,
        ticket_id=ticket_id,
    )
    db.commit()

    sources = [
        SourceRef(
            id=record.record_id,
            kind=record.kind,
            category_id=record.category_id,
            label=(
                record.payload["violation_en"]
                if record.kind == retrieval_service.VIOLATION
                else record.payload["rule_en"]
            )[:160],
            score=record.score,
        )
        for record in retrieval.records[:4]
    ]

    return ChatResponse(
        answer=answer.text,
        language=response_language,
        detected_language=detection.language,
        intent=intent,
        confidence=confidence.score,
        confidence_band=confidence.band,
        needs_clarification=confidence.needs_clarification,
        escalated=ticket_id is not None,
        ticket_id=ticket_id,
        policy_version=retrieval.policy_version,
        sources=sources,
        audit_id=str(entry.id),
    )


@router.post("/language", response_model=LanguageProbeResponse, dependencies=[Depends(authenticated)])
def probe_language(payload: LanguageProbe) -> LanguageProbeResponse:
    """Diagnostic endpoint: what the detector and router see. No data access."""
    detection = detect_language(payload.text)
    intent_result = classify_intent(payload.text)
    return LanguageProbeResponse(
        language=detection.language,
        response_language=detection.response_language,
        confidence=detection.confidence,
        signals=detection.signals,
        intent=intent_result.intent,
        category_hints=intent_result.category_hints,
        normalised_skeleton=phrase_skeleton(payload.text),
    )
