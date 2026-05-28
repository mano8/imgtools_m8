"""Tests for the /private/v1/jti-status endpoint — 100% branch coverage."""

from unittest.mock import MagicMock, patch

import pytest

from auth_user_service.routes.private import (
    JtiStatusRequest,
    JtiStatusResponse,
    check_jti_status,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ── check_jti_status branches ─────────────────────────────────────────────────


@pytest.mark.anyio
async def test_jti_status_non_stateful_returns_active() -> None:
    """Non-stateful mode skips Redis and returns active=True immediately."""
    with patch("auth_user_service.routes.private.settings") as mock_cfg:
        mock_cfg.is_stateful = False
        result = await check_jti_status(
            body=JtiStatusRequest(jti="some-jti"),
            redis=None,
        )
    assert result == JtiStatusResponse(active=True)


@pytest.mark.anyio
async def test_jti_status_redis_unavailable_returns_active() -> None:
    """Redis unavailable (None) in stateful mode → fail-open, returns active=True."""
    with patch("auth_user_service.routes.private.settings") as mock_cfg:
        mock_cfg.is_stateful = True
        result = await check_jti_status(
            body=JtiStatusRequest(jti="some-jti"),
            redis=None,
        )
    assert result == JtiStatusResponse(active=True)


@pytest.mark.anyio
async def test_jti_status_not_revoked_returns_active() -> None:
    """Stateful mode, Redis available, JTI not in blacklist → active=True."""
    mock_redis = MagicMock()
    mock_blacklist = MagicMock()
    mock_blacklist.is_revoked.return_value = False

    with (
        patch("auth_user_service.routes.private.settings") as mock_cfg,
        # Patch where imported at runtime (deferred import inside function body)
        patch("auth_sdk_m8.security.AccessTokenBlacklist", return_value=mock_blacklist),
    ):
        mock_cfg.is_stateful = True
        result = await check_jti_status(
            body=JtiStatusRequest(jti="active-jti"),
            redis=mock_redis,
        )

    assert result == JtiStatusResponse(active=True)
    mock_blacklist.is_revoked.assert_called_once_with("active-jti")


@pytest.mark.anyio
async def test_jti_status_revoked_returns_inactive() -> None:
    """Stateful mode, Redis available, JTI in blacklist → active=False."""
    mock_redis = MagicMock()
    mock_blacklist = MagicMock()
    mock_blacklist.is_revoked.return_value = True

    with (
        patch("auth_user_service.routes.private.settings") as mock_cfg,
        # Patch where imported at runtime (deferred import inside function body)
        patch("auth_sdk_m8.security.AccessTokenBlacklist", return_value=mock_blacklist),
    ):
        mock_cfg.is_stateful = True
        result = await check_jti_status(
            body=JtiStatusRequest(jti="revoked-jti"),
            redis=mock_redis,
        )

    assert result == JtiStatusResponse(active=False)
    mock_blacklist.is_revoked.assert_called_once_with("revoked-jti")


# ── model validation ─────────────────────────────────────────────────────────


def test_jti_status_request_rejects_empty_jti() -> None:
    """JtiStatusRequest must reject empty jti (min_length=1)."""
    with pytest.raises(Exception):
        JtiStatusRequest(jti="")
