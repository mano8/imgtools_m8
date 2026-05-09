"""Security regression: handle_route_exception() maps infra errors to correct HTTP codes.

Verifies that:
- HTTPException is re-raised with its original status code (not swallowed into 500)
- SQLAlchemy OperationalError → 503 (database unreachable)
- Redis ConnectionError → 503 (cache unreachable)
- Session is rolled back on OperationalError
- Everything else is delegated to BaseController (500)
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError

from auth_user_service.core.exceptions import handle_route_exception


class TestHTTPExceptionPassthrough:
    """HTTPException must never be swallowed into a 500."""

    def test_404_is_reraised(self):
        ex = HTTPException(status_code=404, detail="Not found")
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Not found"

    def test_403_is_reraised(self):
        ex = HTTPException(status_code=403, detail="Forbidden")
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex)
        assert exc_info.value.status_code == 403

    def test_409_is_reraised(self):
        ex = HTTPException(status_code=409, detail="Conflict")
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex)
        assert exc_info.value.status_code == 409

    def test_all_4xx_codes_preserved(self):
        for code in [400, 401, 403, 404, 409, 422, 429]:
            ex = HTTPException(status_code=code, detail=f"error {code}")
            with pytest.raises(HTTPException) as exc_info:
                handle_route_exception(ex)
            assert exc_info.value.status_code == code

    def test_http_exception_with_session_still_reraised(self):
        ex = HTTPException(status_code=404, detail="Not found")
        mock_session = MagicMock()
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex, session=mock_session)
        assert exc_info.value.status_code == 404
        mock_session.rollback.assert_not_called()


class TestDatabaseUnavailable:
    """OperationalError (DB unreachable) must produce a clear 503, not 500."""

    def test_operational_error_raises_503(self):
        ex = OperationalError("connection refused", None, None)
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex)
        assert exc_info.value.status_code == 503

    def test_503_detail_mentions_database(self):
        ex = OperationalError("connection refused", None, None)
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex)
        assert "Database" in exc_info.value.detail or "database" in exc_info.value.detail

    def test_session_rolled_back_on_operational_error(self):
        ex = OperationalError("connection refused", None, None)
        mock_session = MagicMock()
        with pytest.raises(HTTPException):
            handle_route_exception(ex, session=mock_session)
        mock_session.rollback.assert_called_once()

    def test_no_session_does_not_raise_on_operational_error(self):
        ex = OperationalError("connection refused", None, None)
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex, session=None)
        assert exc_info.value.status_code == 503


class TestRedisUnavailable:
    """RedisConnectionError must produce a clear 503, not 500."""

    def test_connection_error_raises_503(self):
        ex = RedisConnectionError("Redis unreachable")
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex)
        assert exc_info.value.status_code == 503

    def test_503_detail_mentions_cache(self):
        ex = RedisConnectionError("Redis unreachable")
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex)
        detail = exc_info.value.detail.lower()
        assert "cache" in detail or "unavailable" in detail

    def test_redis_error_without_session(self):
        ex = RedisConnectionError("refused")
        with pytest.raises(HTTPException) as exc_info:
            handle_route_exception(ex, session=None)
        assert exc_info.value.status_code == 503


class TestOtherExceptionDelegation:
    """Non-infra exceptions are delegated to BaseController (returns 500 JSONResponse)."""

    def test_value_error_delegates_to_base_controller(self):
        ex = ValueError("something broke")
        result = handle_route_exception(ex)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

    def test_runtime_error_delegates_to_base_controller(self):
        ex = RuntimeError("unexpected")
        result = handle_route_exception(ex)
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500

    def test_session_rolled_back_via_base_controller(self):
        """BaseController rolls back the session for generic errors."""
        ex = ValueError("boom")
        mock_session = MagicMock()
        handle_route_exception(ex, session=mock_session)
        mock_session.rollback.assert_called_once()
