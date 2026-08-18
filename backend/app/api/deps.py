"""Shared route dependencies."""

from __future__ import annotations

from fastapi import Depends

from app.core.security import rate_limit, require_api_key


def authenticated(
    _rate: None = Depends(rate_limit),
    api_key: str = Depends(require_api_key),
) -> str:
    return api_key
