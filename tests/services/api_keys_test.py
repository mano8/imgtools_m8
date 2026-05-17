"""Unit tests for services.api_keys (ApiKeyService, RateLimitEnforcer)."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from auth_sdk_m8.schemas.base import Period
from auth_user_service.db_models.api_keys import ApiKey, RateLimit
from auth_user_service.services.api_keys import ApiKeyService, RateLimitEnforcer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def active_api_key(db_session, sample_user):
    plaintext, key_hash = ApiKeyService.generate_key()
    api_key = ApiKey(
        name="test-key",
        key_hash=key_hash,
        user_id=sample_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        revoked=False,
    )
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)
    return plaintext, api_key


@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.API_KEY_DEFAULT_LIMIT_MINUTE = 60
    s.API_KEY_DEFAULT_LIMIT_HOUR = 1000
    s.API_KEY_DEFAULT_LIMIT_DAY = 10000
    s.API_KEY_DEFAULT_LIMIT_MONTH = 200000
    return s


# ---------------------------------------------------------------------------
# ApiKeyService.generate_key
# ---------------------------------------------------------------------------


class TestGenerateKey:
    def test_returns_tuple(self):
        result = ApiKeyService.generate_key()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_plaintext_has_prefix(self):
        plaintext, _ = ApiKeyService.generate_key()
        assert plaintext.startswith(ApiKeyService.KEY_PREFIX)

    def test_hash_is_64_chars(self):
        _, key_hash = ApiKeyService.generate_key()
        assert len(key_hash) == 64  # SHA-256 hex

    def test_each_call_generates_unique_key(self):
        plaintext1, _ = ApiKeyService.generate_key()
        plaintext2, _ = ApiKeyService.generate_key()
        assert plaintext1 != plaintext2


# ---------------------------------------------------------------------------
# ApiKeyService.verify_key
# ---------------------------------------------------------------------------


class TestVerifyKey:
    def test_correct_plaintext_verifies(self):
        plaintext, key_hash = ApiKeyService.generate_key()
        assert ApiKeyService.verify_key(plaintext, key_hash) is True

    def test_wrong_plaintext_fails(self):
        _, key_hash = ApiKeyService.generate_key()
        assert ApiKeyService.verify_key("ak_wrong", key_hash) is False

    def test_empty_string_fails(self):
        _, key_hash = ApiKeyService.generate_key()
        assert ApiKeyService.verify_key("", key_hash) is False


# ---------------------------------------------------------------------------
# ApiKeyService.get_active_key
# ---------------------------------------------------------------------------


class TestGetActiveKey:
    def test_returns_key_for_valid_plaintext(self, db_session, active_api_key):
        plaintext, api_key = active_api_key
        found = ApiKeyService.get_active_key(db_session, plaintext)
        assert found is not None
        assert found.id == api_key.id

    def test_returns_none_for_unknown_key(self, db_session):
        assert ApiKeyService.get_active_key(db_session, "ak_unknown") is None

    def test_returns_none_for_revoked_key(self, db_session, active_api_key):
        plaintext, api_key = active_api_key
        api_key.revoked = True
        db_session.add(api_key)
        db_session.commit()
        assert ApiKeyService.get_active_key(db_session, plaintext) is None

    def test_returns_none_for_expired_key(self, db_session, sample_user):
        plaintext, key_hash = ApiKeyService.generate_key()
        api_key = ApiKey(
            name="expired",
            key_hash=key_hash,
            user_id=sample_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            revoked=False,
        )
        db_session.add(api_key)
        db_session.commit()
        assert ApiKeyService.get_active_key(db_session, plaintext) is None

    def test_invalid_key_emits_metric(self, db_session):
        mock_m = MagicMock()
        mock_m.api_key_validations_total = MagicMock()
        with patch("auth_user_service.services.api_keys._metrics.get", return_value=mock_m):
            result = ApiKeyService.get_active_key(db_session, "ak_nonexistent")
        assert result is None
        mock_m.api_key_validations_total.labels.assert_called_once_with(result="invalid")

    def test_revoked_key_emits_metric(self, db_session, sample_user):
        plaintext, key_hash = ApiKeyService.generate_key()
        api_key = ApiKey(name="revoked-m", key_hash=key_hash, user_id=sample_user.id, revoked=True)
        db_session.add(api_key)
        db_session.commit()

        mock_m = MagicMock()
        mock_m.api_key_validations_total = MagicMock()
        with patch("auth_user_service.services.api_keys._metrics.get", return_value=mock_m):
            result = ApiKeyService.get_active_key(db_session, plaintext)
        assert result is None
        mock_m.api_key_validations_total.labels.assert_called_once_with(result="revoked")

    def test_expired_key_emits_metric(self, db_session, sample_user):
        plaintext, key_hash = ApiKeyService.generate_key()
        api_key = ApiKey(
            name="expired-m",
            key_hash=key_hash,
            user_id=sample_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            revoked=False,
        )
        db_session.add(api_key)
        db_session.commit()

        mock_m = MagicMock()
        mock_m.api_key_validations_total = MagicMock()
        with patch("auth_user_service.services.api_keys._metrics.get", return_value=mock_m):
            result = ApiKeyService.get_active_key(db_session, plaintext)
        assert result is None
        mock_m.api_key_validations_total.labels.assert_called_once_with(result="expired")

    def test_valid_key_emits_success_metric(self, db_session, active_api_key):
        plaintext, _ = active_api_key
        mock_m = MagicMock()
        mock_m.api_key_validations_total = MagicMock()
        with patch("auth_user_service.services.api_keys._metrics.get", return_value=mock_m):
            result = ApiKeyService.get_active_key(db_session, plaintext)
        assert result is not None
        mock_m.api_key_validations_total.labels.assert_called_once_with(result="success")

    def test_returns_key_when_no_expiry(self, db_session, sample_user):
        plaintext, key_hash = ApiKeyService.generate_key()
        api_key = ApiKey(
            name="no-expiry",
            key_hash=key_hash,
            user_id=sample_user.id,
            expires_at=None,
            revoked=False,
        )
        db_session.add(api_key)
        db_session.commit()
        found = ApiKeyService.get_active_key(db_session, plaintext)
        assert found is not None


# ---------------------------------------------------------------------------
# ApiKeyService.get_limits
# ---------------------------------------------------------------------------


class TestGetLimits:
    def test_returns_empty_when_no_rows(self, db_session, active_api_key):
        _, api_key = active_api_key
        limits = ApiKeyService.get_limits(db_session, api_key.id, api_key.user_id)
        assert limits == []

    def test_key_specific_limit_returned(self, db_session, active_api_key):
        _, api_key = active_api_key
        row = RateLimit(api_key_id=api_key.id, period=Period.MINUTE, limit=30)
        db_session.add(row)
        db_session.commit()

        limits = ApiKeyService.get_limits(db_session, api_key.id, api_key.user_id)
        assert (Period.MINUTE, 30) in limits

    def test_user_default_limit_returned_when_no_key_limit(
        self, db_session, active_api_key, sample_user
    ):
        _, api_key = active_api_key
        row = RateLimit(user_id=sample_user.id, period=Period.HOUR, limit=500)
        db_session.add(row)
        db_session.commit()

        limits = ApiKeyService.get_limits(db_session, api_key.id, api_key.user_id)
        assert (Period.HOUR, 500) in limits

    def test_key_limit_overrides_user_limit_for_same_period(
        self, db_session, active_api_key, sample_user
    ):
        _, api_key = active_api_key
        user_row = RateLimit(user_id=sample_user.id, period=Period.DAY, limit=5000)
        key_row = RateLimit(api_key_id=api_key.id, period=Period.DAY, limit=100)
        db_session.add(user_row)
        db_session.add(key_row)
        db_session.commit()

        limits = ApiKeyService.get_limits(db_session, api_key.id, api_key.user_id)
        day_limits = [lim for p, lim in limits if p == Period.DAY]
        assert day_limits == [100]  # key-specific wins

    def test_results_ordered_by_period(self, db_session, active_api_key):
        _, api_key = active_api_key
        db_session.add(RateLimit(api_key_id=api_key.id, period=Period.DAY, limit=1000))
        db_session.add(RateLimit(api_key_id=api_key.id, period=Period.MINUTE, limit=10))
        db_session.commit()

        limits = ApiKeyService.get_limits(db_session, api_key.id, api_key.user_id)
        periods = [p for p, _ in limits]
        assert periods.index(Period.MINUTE) < periods.index(Period.DAY)


# ---------------------------------------------------------------------------
# RateLimitEnforcer
# ---------------------------------------------------------------------------


class TestRateLimitEnforcer:
    def _make_enforcer(self, mock_redis, mock_settings):
        return RateLimitEnforcer(mock_redis, mock_settings)

    def _make_api_key(self):
        api_key = MagicMock(spec=ApiKey)
        api_key.id = uuid.uuid4()
        return api_key

    def _make_pipe(self, mock_redis, count):
        pipe = MagicMock()
        mock_redis.pipeline.return_value.__enter__ = MagicMock(return_value=pipe)
        mock_redis.pipeline.return_value.__exit__ = MagicMock(return_value=False)
        pipe.execute.return_value = (count, True)
        return pipe

    def test_allowed_result_when_under_limit(self, mock_settings):
        redis = MagicMock()
        self._make_pipe(redis, 1)
        api_key = self._make_api_key()
        enforcer = self._make_enforcer(redis, mock_settings)

        result = enforcer.enforce(api_key, [(Period.MINUTE, 10)])

        assert result.allowed is True

    def test_blocked_result_when_over_limit(self, mock_settings):
        redis = MagicMock()
        self._make_pipe(redis, 11)
        api_key = self._make_api_key()
        enforcer = self._make_enforcer(redis, mock_settings)

        result = enforcer.enforce(api_key, [(Period.MINUTE, 10)])

        assert result.allowed is False
        assert result.exceeded_period == Period.MINUTE

    def test_falls_back_to_settings_when_no_limits(self, mock_settings):
        mock_settings.API_KEY_DEFAULT_LIMIT_MINUTE = 60
        mock_settings.API_KEY_DEFAULT_LIMIT_HOUR = 0
        mock_settings.API_KEY_DEFAULT_LIMIT_DAY = 0
        mock_settings.API_KEY_DEFAULT_LIMIT_MONTH = 0

        redis = MagicMock()
        self._make_pipe(redis, 1)
        api_key = self._make_api_key()
        enforcer = self._make_enforcer(redis, mock_settings)

        result = enforcer.enforce(api_key, [])  # empty limits → use defaults

        assert result.allowed is True

    def test_default_limits_includes_day_when_positive(self, mock_settings):
        mock_settings.API_KEY_DEFAULT_LIMIT_MINUTE = 0
        mock_settings.API_KEY_DEFAULT_LIMIT_HOUR = 0
        mock_settings.API_KEY_DEFAULT_LIMIT_DAY = 5000
        mock_settings.API_KEY_DEFAULT_LIMIT_MONTH = 0

        enforcer = RateLimitEnforcer(MagicMock(), mock_settings)
        defaults = enforcer._default_limits()

        assert (Period.DAY, 5000) in defaults

    def test_default_limits_includes_month_when_positive(self, mock_settings):
        mock_settings.API_KEY_DEFAULT_LIMIT_MINUTE = 0
        mock_settings.API_KEY_DEFAULT_LIMIT_HOUR = 0
        mock_settings.API_KEY_DEFAULT_LIMIT_DAY = 0
        mock_settings.API_KEY_DEFAULT_LIMIT_MONTH = 100000

        enforcer = RateLimitEnforcer(MagicMock(), mock_settings)
        defaults = enforcer._default_limits()

        assert (Period.MONTH, 100000) in defaults

    def test_default_limits_excludes_zero_values(self, mock_settings):
        mock_settings.API_KEY_DEFAULT_LIMIT_MINUTE = 0
        mock_settings.API_KEY_DEFAULT_LIMIT_HOUR = 1000
        mock_settings.API_KEY_DEFAULT_LIMIT_DAY = 0
        mock_settings.API_KEY_DEFAULT_LIMIT_MONTH = 0

        enforcer = RateLimitEnforcer(MagicMock(), mock_settings)
        defaults = enforcer._default_limits()

        assert (Period.MINUTE, 0) not in defaults
        assert any(p == Period.HOUR for p, _ in defaults)

    def test_metrics_allowed_incremented(self, mock_settings):
        from unittest.mock import patch, MagicMock as MM

        redis = MagicMock()
        self._make_pipe(redis, 1)
        api_key = self._make_api_key()
        enforcer = self._make_enforcer(redis, mock_settings)

        mock_metrics = MM()
        mock_counter = MM()
        mock_metrics.api_key_rate_limit_checks_total = mock_counter
        mock_metrics.api_key_rate_limit_hits_total = None

        with patch("auth_user_service.services.api_keys._metrics.get", return_value=mock_metrics):
            result = enforcer.enforce(api_key, [(Period.MINUTE, 10)])

        assert result.allowed is True
        assert mock_counter.labels.call_count >= 2  # "checked" + "allowed"

    def test_metrics_blocked_incremented(self, mock_settings):
        from unittest.mock import patch, MagicMock as MM

        redis = MagicMock()
        self._make_pipe(redis, 100)
        api_key = self._make_api_key()
        enforcer = self._make_enforcer(redis, mock_settings)

        mock_metrics = MM()
        mock_counter = MM()
        mock_hits = MM()
        mock_metrics.api_key_rate_limit_checks_total = mock_counter
        mock_metrics.api_key_rate_limit_hits_total = mock_hits

        with patch("auth_user_service.services.api_keys._metrics.get", return_value=mock_metrics):
            result = enforcer.enforce(api_key, [(Period.MINUTE, 10)])

        assert result.allowed is False
        mock_hits.labels.assert_called_once_with(period=Period.MINUTE.value)
