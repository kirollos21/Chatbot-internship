"""API key authentication and a simple in-process rate limiter.

The rate limiter is per-process and therefore only correct for a single API
container. Behind more than one replica, move this to Redis or the reverse
proxy — noted in the README as an open item rather than silently pretending it
scales.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings

_WINDOW_SECONDS = 60
_hits: dict[str, deque[float]] = defaultdict(deque)


def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """Auth dependency. With no API_KEYS configured, auth is disabled (dev only)."""
    settings = get_settings()
    keys = settings.api_key_set
    if not keys:
        return "anonymous"
    if not x_api_key or x_api_key not in keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key


def rate_limit(request: Request, x_api_key: str | None = Header(default=None)) -> None:
    settings = get_settings()
    limit = settings.rate_limit_per_minute
    if limit <= 0:
        return

    identity = x_api_key or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    bucket = _hits[identity]
    while bucket and now - bucket[0] > _WINDOW_SECONDS:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again shortly.",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )
    bucket.append(now)


def reset_rate_limiter() -> None:
    """Test helper."""
    _hits.clear()
