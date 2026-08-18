"""Request/response models for the assistant endpoints."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    compound: str | None = Field(default=None, max_length=128)
    phase: str | None = Field(default=None, max_length=128)
    language: str | None = Field(
        default=None,
        description="Force the response language (en|ar|franco). Omit to auto-detect.",
    )
    user_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    as_of: date | None = Field(
        default=None,
        description="Evaluate against the policy version effective on this date. Defaults to today.",
    )


class SourceRef(BaseModel):
    id: str
    kind: str
    category_id: str
    label: str
    score: float


class ChatResponse(BaseModel):
    answer: str
    language: str
    detected_language: str
    intent: str
    confidence: float
    confidence_band: str
    needs_clarification: bool = False
    escalated: bool = False
    ticket_id: str | None = None
    policy_version: str | None = None
    sources: list[SourceRef] = []
    audit_id: str | None = None


class LanguageProbe(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class LanguageProbeResponse(BaseModel):
    language: str
    response_language: str
    confidence: float
    signals: dict
    intent: str
    category_hints: list[str]
    normalised_skeleton: str
