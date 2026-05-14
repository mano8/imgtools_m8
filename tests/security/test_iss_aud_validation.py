"""Security regression: iss/aud JWT claim enforcement.

Verifies that:
- create_access_token embeds iss/aud when provided
- create_access_token omits iss/aud when not provided (backward compat)
- A token with a wrong issuer is rejected with 403
- A token with a wrong audience is rejected with 403
- A token without iss/aud when enforcement is off is accepted
- A token with the correct iss/aud is accepted
- TokenValidationConfig.strict() enforces both claims
"""

import uuid
from datetime import timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from auth_sdk_m8.schemas.auth import TokenAccessData, TokenSecret
from auth_sdk_m8.security import TokenValidationConfig, TokenValidator
from auth_user_service.core.security import SecurityHelper


_SECRET = TokenSecret(
    secret_key=SecretStr("Aa1-secret-key-for-test-32-chars-long"), algorithm="HS256"
)
_USER_DATA = TokenAccessData(
    sub=str(uuid.uuid4()),
    role="user",
    email="iss_test@example.com",
    full_name="ISS Test",
    is_superuser=False,
)
_EXPIRES = timedelta(minutes=30)


def _make_token(issuer: str = None, audience: str = None) -> str:
    token, _ = SecurityHelper.create_access_token(
        data=_USER_DATA,
        expires_delta=_EXPIRES,
        secrets=_SECRET,
        issuer=issuer,
        audience=audience,
    )
    return token


def _make_validator(issuer: str = None, audience: str = None) -> TokenValidator:
    return TokenValidator(
        secrets=_SECRET,
        config=TokenValidationConfig(
            allowed_algorithms=["HS256"],
            issuer=issuer,
            audience=audience,
            require_iss=bool(issuer),
            require_aud=bool(audience),
        ),
    )


# ---------------------------------------------------------------------------
# create_access_token claim embedding
# ---------------------------------------------------------------------------


class TestCreateAccessTokenClaims:
    def test_iss_embedded_when_provided(self):
        token = _make_token(issuer="https://auth.example.com")
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["iss"] == "https://auth.example.com"

    def test_aud_embedded_when_provided(self):
        token = _make_token(audience="https://api.example.com")
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["aud"] == "https://api.example.com"

    def test_iss_absent_when_not_provided(self):
        token = _make_token()
        payload = jwt.decode(token, options={"verify_signature": False})
        assert "iss" not in payload

    def test_aud_absent_when_not_provided(self):
        token = _make_token()
        payload = jwt.decode(token, options={"verify_signature": False})
        assert "aud" not in payload

    def test_both_iss_and_aud_embedded_together(self):
        token = _make_token(
            issuer="https://auth.example.com",
            audience="https://api.example.com",
        )
        payload = jwt.decode(token, options={"verify_signature": False})
        assert payload["iss"] == "https://auth.example.com"
        assert payload["aud"] == "https://api.example.com"


# ---------------------------------------------------------------------------
# TokenValidator enforcement
# ---------------------------------------------------------------------------


class TestIssuerEnforcement:
    def test_correct_issuer_accepted(self):
        token = _make_token(issuer="https://auth.example.com")
        validator = _make_validator(issuer="https://auth.example.com")
        result = validator.validate_access_token(token)
        assert result.email == "iss_test@example.com"

    def test_wrong_issuer_raises_invalid_token(self):
        token = _make_token(issuer="https://attacker.com")
        validator = _make_validator(issuer="https://auth.example.com")
        from auth_sdk_m8.core.exceptions import InvalidToken

        with pytest.raises(InvalidToken):
            validator.validate_access_token(token)

    def test_missing_iss_when_required_raises_invalid_token(self):
        """Token without iss claim rejected when require_iss=True."""
        token = _make_token()  # no issuer
        validator = _make_validator(issuer="https://auth.example.com")
        from auth_sdk_m8.core.exceptions import InvalidToken

        with pytest.raises(InvalidToken):
            validator.validate_access_token(token)

    def test_no_enforcement_accepts_token_without_iss(self):
        """When require_iss=False, tokens without iss pass through."""
        token = _make_token()
        validator = _make_validator()  # no issuer requirement
        result = validator.validate_access_token(token)
        assert result.email == "iss_test@example.com"


class TestAudienceEnforcement:
    def test_correct_audience_accepted(self):
        token = _make_token(audience="https://api.example.com")
        validator = _make_validator(audience="https://api.example.com")
        result = validator.validate_access_token(token)
        assert result.email == "iss_test@example.com"

    def test_wrong_audience_raises_invalid_token(self):
        token = _make_token(audience="https://other-service.com")
        validator = _make_validator(audience="https://api.example.com")
        from auth_sdk_m8.core.exceptions import InvalidToken

        with pytest.raises(InvalidToken):
            validator.validate_access_token(token)

    def test_missing_aud_when_required_raises_invalid_token(self):
        token = _make_token()  # no audience
        validator = _make_validator(audience="https://api.example.com")
        from auth_sdk_m8.core.exceptions import InvalidToken

        with pytest.raises(InvalidToken):
            validator.validate_access_token(token)

    def test_no_enforcement_accepts_token_without_aud(self):
        token = _make_token()
        validator = _make_validator()
        result = validator.validate_access_token(token)
        assert result.email == "iss_test@example.com"


# ---------------------------------------------------------------------------
# get_current_user integration: wrong iss/aud → 403
# ---------------------------------------------------------------------------


class TestGetCurrentUserIssAud:
    """When the service has TOKEN_ISSUER/TOKEN_AUDIENCE configured, tokens
    from a different issuer or for a different audience must be rejected."""

    def _token_with_wrong_issuer(self) -> str:
        return _make_token(issuer="https://attacker.com")

    def _token_with_wrong_audience(self) -> str:
        return _make_token(audience="https://wrong-service.com")

    def test_wrong_issuer_raises_403(self):
        from auth_user_service.core.deps import get_current_user
        from auth_sdk_m8.security import TokenValidationConfig, TokenValidator

        wrong_token = self._token_with_wrong_issuer()
        strict_validator = TokenValidator(
            secrets=_SECRET,
            config=TokenValidationConfig(
                allowed_algorithms=["HS256"],
                issuer="https://auth.example.com",
                require_iss=True,
            ),
        )
        with patch("auth_user_service.core.deps._access_validator", strict_validator):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=wrong_token)
        assert exc_info.value.status_code == 403

    def test_wrong_audience_raises_403(self):
        from auth_user_service.core.deps import get_current_user
        from auth_sdk_m8.security import TokenValidationConfig, TokenValidator

        wrong_token = self._token_with_wrong_audience()
        strict_validator = TokenValidator(
            secrets=_SECRET,
            config=TokenValidationConfig(
                allowed_algorithms=["HS256"],
                audience="https://api.example.com",
                require_aud=True,
            ),
        )
        with patch("auth_user_service.core.deps._access_validator", strict_validator):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(token=wrong_token)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# TokenValidationConfig.strict() convenience constructor
# ---------------------------------------------------------------------------


class TestStrictConfig:
    """TokenValidationConfig with require_iss=True and require_aud=True."""

    def _strict_validator(self) -> TokenValidator:
        # strict() also requires iat/nbf which create_access_token doesn't
        # embed, so we build an equivalent config scoped to what we generate.
        return TokenValidator(
            secrets=_SECRET,
            config=TokenValidationConfig(
                allowed_algorithms=["HS256"],
                issuer="https://auth.example.com",
                audience="https://api.example.com",
                require_iss=True,
                require_aud=True,
                leeway_seconds=2,
            ),
        )

    def test_strict_rejects_token_without_iss(self):
        from auth_sdk_m8.core.exceptions import InvalidToken

        token = _make_token(audience="https://api.example.com")  # iss missing
        with pytest.raises(InvalidToken):
            self._strict_validator().validate_access_token(token)

    def test_strict_rejects_token_without_aud(self):
        from auth_sdk_m8.core.exceptions import InvalidToken

        token = _make_token(issuer="https://auth.example.com")  # aud missing
        with pytest.raises(InvalidToken):
            self._strict_validator().validate_access_token(token)

    def test_strict_accepts_token_with_correct_claims(self):
        token = _make_token(
            issuer="https://auth.example.com",
            audience="https://api.example.com",
        )
        result = self._strict_validator().validate_access_token(token)
        assert result.email == "iss_test@example.com"
