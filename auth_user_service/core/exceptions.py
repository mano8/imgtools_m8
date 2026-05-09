"""Shared route-level exception-to-HTTP-response helpers."""

from typing import Optional

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from auth_sdk_m8.controllers.base import BaseController


def handle_route_exception(
    ex: Exception,
    session: Optional[Session] = None,
) -> JSONResponse:
    """Map a caught exception to the appropriate HTTP response.

    Raises HTTPException (not returns) for infrastructure failures so the
    correct status code reaches the client even when the caller uses ``return``.

    - HTTPException          → re-raised (preserves original status code)
    - OperationalError       → 503 (database unreachable)
    - RedisConnectionError   → 503 (cache unreachable)
    - everything else        → delegated to BaseController.handle_exception (500)
    """
    if isinstance(ex, HTTPException):
        raise ex
    if isinstance(ex, OperationalError):
        if session:
            session.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please try again.",
        )
    if isinstance(ex, RedisConnectionError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cache service temporarily unavailable. Please try again.",
        )
    return BaseController.handle_exception(ex=ex, session=session)
