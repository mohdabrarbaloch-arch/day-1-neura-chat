"""Shared FastAPI dependencies: current user, rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Bearer token, or raise 401."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or not credentials.credentials:
        raise unauthorized

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise unauthorized

    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise unauthorized from None

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized
    return user


class RateLimiter:
    """Small in-process sliding-window limiter, keyed by client IP.

    Good enough for a single instance; swap for Redis when you scale out.
    """

    def __init__(self, limit_per_minute: int) -> None:
        self.limit = max(1, limit_per_minute)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.monotonic()
        window = self._hits[key]
        while window and now - window[0] > 60.0:
            window.popleft()
        if len(window) >= self.limit:
            return False
        window.append(now)
        return True


_limiter = RateLimiter(settings.rate_limit_per_minute)


async def rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing the per-IP request budget."""
    client_ip = request.client.host if request.client else "unknown"
    if not _limiter.check(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests - slow down a little.",
            headers={"Retry-After": "60"},
        )
