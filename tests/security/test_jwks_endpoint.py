"""Security tests for the JWKS endpoint and kid embedding.

Verifies that:
- RS256 mode: /.well-known/jwks.json returns a valid JWK with correct fields
- HS256 mode: endpoint returns an empty key set (shared secret must never be published)
- kid is embedded in issued JWTs when ACCESS_KEY_ID is configured explicitly
- kid is derived from key fingerprint when ACCESS_KEY_ID is absent
- _resolve_kid returns None for symmetric algorithms
"""

import hashlib
from datetime import timedelta
from unittest.mock import patch

import jwt

from auth_user_service.routes.jwks import _build_jwk
from auth_user_service.services.auth import _resolve_kid

# ── test RSA keypair (2048-bit, generated for tests only) ────────────────────

_RSA_PRIVATE_PEM = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAzWCXqrK+FlZPOYIieExjEQCqHeIQrEDiAJN6zIWAULZlV2BS
SUHlIhQqZQ0zSoORT30G6AHXCC+bjCz06piAhA/nMiD1szbymxThnumDVcS3/tdl
BIMmRyfdWzUCxgMdV1OsVtQAC0lVThwKfyDdoCeyRFUYa9tfwIjMSvuU0PFXAtvU
EDwJlLmH4a8lkTcfAB5DD0eWzK2Q6KLT34VLMT8PQxtNfucWvuGnyhBHe4Ze2cvG
hINTLL4nUGi0YqwWAnxkzb3NnWJ5PV/X08QKZtJUy2pbhysV/Th9gu8sxnKN2mNz
TgSeGVaE+Yk5hpi+UTqfWQCK594KTowJa0LTMwIDAQABAoIBACBlL5c/2YcJdzax
hcFm/ytj6PGMwqeBFoUTvkd7eWmB08tsCJ7Ak6WD+8nzwpbq2OVqacf33lTOuaDr
SHimtILgRU4db9QkgzEeIpaf69UAEivTCv6it0t7CMoFuxnDzQGE08bgat9c4mVP
PAKgiwTjrhVkPNVqhZiHm33qYCdy2blTOBotgnG5tMUpKmT5BtXAq3/f8qadH5SB
CNqL0lwlfBB5CzTO/RIFNDA4IwwbpVYrIWKq83q0DlyDRl4/4qLY/0osZW506NJf
A8QUOgQGiW6X7IaPSZ5OaL1c8EnmhrGanZnYjh7dMsDJFAoY2yQ6a7iJqPMAivVd
tA2jDOECgYEA5x8NRDsMt9C/DbixP3YAsVBkCBUQAHuumC4YNphKN7M/SE0oDc57
7dkJghLJbrQ5ssuFodUKVIXM1UCZk7EgAUKrKCNli01/bhIxgPcKbSxLGjKRWAUW
UxhK00tLRrR1QiEoR077huLewHuG+mw4FL1I2MEP+/tYEaPwf0hIaKECgYEA43we
3JE0Tm3OwY8CcRRhMEn++DZFioobm0pIT80p5GEKjolbQQex+dulpd9i/0GLER+C
vW+ickW62Z6L7tez2u51GSyQEAUEKKsUbruKjCW/8KKx7s4/f/qiLrYkzhcSGGvZ
A4t7WoLxt0sV2gk0yWXYJWRVgomtXBv/tnsch1MCgYBVmqi9RunVA5pgKLJuAPUM
t+v1GmgM5cKrVxdc0Vdb/iZIT1uwkXRRinv9E5xMRrDASqW6ZUAoQk62BfFcRNTH
4rumaEXqLNAwIsj3LYlNGoTOtUAkS+4S5QKB9HdzPs/XqJRUpSqAsXMz9AzwoDi9
ZcafkhKrkFL0ZbZkTo+TQQKBgQDE8jm51hDF8fV1yD1h7zXxW67d8Aam2cjq2hXe
2Q3yxj0giDS0CViBrDMud0c7HOCsc256WYL3kf0h2Uzm/GKfIaHJqLYU2HLwTqVC
9SUPDsOtLv4DdRau0yvEazdUIc8ty3k3w3OJOiLRALWrbhsAXicSwFnzyQSI4Uiz
EMTzNwKBgQDkKBaMUOr2M5uhRltCZTiZIFJTlFUB4NEt0JurqwlMgGrHsQIH7b+w
CfXhpg/P/cn2UjoHonHYWAw/5AWv7NJAMiSoPFM41ypgqdWecwSDzm2aPOpQE4oZ
an056qoZgrQRdeX5bYMCU+t+DJFFJCItpFkQ2jGGEFe6oslrZvgNMw==
-----END RSA PRIVATE KEY-----"""

_RSA_PUBLIC_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzWCXqrK+FlZPOYIieExj
EQCqHeIQrEDiAJN6zIWAULZlV2BSSUHlIhQqZQ0zSoORT30G6AHXCC+bjCz06piA
hA/nMiD1szbymxThnumDVcS3/tdlBIMmRyfdWzUCxgMdV1OsVtQAC0lVThwKfyDd
oCeyRFUYa9tfwIjMSvuU0PFXAtvUEDwJlLmH4a8lkTcfAB5DD0eWzK2Q6KLT34VL
MT8PQxtNfucWvuGnyhBHe4Ze2cvGhINTLL4nUGi0YqwWAnxkzb3NnWJ5PV/X08QK
ZtJUy2pbhysV/Th9gu8sxnKN2mNzTgSeGVaE+Yk5hpi+UTqfWQCK594KTowJa0LT
MwIDAQAB
-----END PUBLIC KEY-----"""

_EXPECTED_KID_FINGERPRINT = hashlib.sha256(
    _RSA_PUBLIC_PEM.strip().encode()
).hexdigest()[:16]


# ── _build_jwk ────────────────────────────────────────────────────────────────


def test_build_jwk_rsa_has_required_fields():
    jwk = _build_jwk(_RSA_PUBLIC_PEM, "RS256", "my-kid")
    assert jwk["kty"] == "RSA"
    assert jwk["use"] == "sig"
    assert jwk["alg"] == "RS256"
    assert jwk["kid"] == "my-kid"
    assert "n" in jwk
    assert "e" in jwk


def test_build_jwk_kid_is_injected():
    jwk = _build_jwk(_RSA_PUBLIC_PEM, "RS256", "rotation-key-v2")
    assert jwk["kid"] == "rotation-key-v2"


# ── jwks_endpoint ─────────────────────────────────────────────────────────────


def test_jwks_endpoint_rs256_returns_valid_keyset():
    from auth_user_service.routes.jwks import jwks_endpoint

    with (
        patch("auth_user_service.routes.jwks.settings") as mock_settings,
        patch("auth_user_service.routes.jwks._resolve_kid", return_value="fp-kid-1234"),
    ):
        mock_settings.ACCESS_TOKEN_ALGORITHM = "RS256"
        mock_settings.ACCESS_PUBLIC_KEY = _RSA_PUBLIC_PEM

        result = jwks_endpoint()

    assert "keys" in result
    assert len(result["keys"]) == 1
    key = result["keys"][0]
    assert key["kty"] == "RSA"
    assert key["use"] == "sig"
    assert key["alg"] == "RS256"
    assert key["kid"] == "fp-kid-1234"
    assert "n" in key
    assert "e" in key


def test_jwks_endpoint_hs256_returns_empty_keyset():
    """Symmetric secrets must never be published via JWKS."""
    from auth_user_service.routes.jwks import jwks_endpoint

    with patch("auth_user_service.routes.jwks.settings") as mock_settings:
        mock_settings.ACCESS_TOKEN_ALGORITHM = "HS256"
        mock_settings.ACCESS_PUBLIC_KEY = None

        result = jwks_endpoint()

    assert result == {"keys": []}


def test_jwks_endpoint_no_public_key_returns_empty_keyset():
    """RS256 with missing public key returns an empty key set, not a crash."""
    from auth_user_service.routes.jwks import jwks_endpoint

    with patch("auth_user_service.routes.jwks.settings") as mock_settings:
        mock_settings.ACCESS_TOKEN_ALGORITHM = "RS256"
        mock_settings.ACCESS_PUBLIC_KEY = None

        result = jwks_endpoint()

    assert result == {"keys": []}


# ── _resolve_kid ──────────────────────────────────────────────────────────────


def test_resolve_kid_returns_none_for_hs256():
    with patch("auth_user_service.services.auth.settings") as mock_settings:
        mock_settings.ACCESS_TOKEN_ALGORITHM = "HS256"
        result = _resolve_kid("HS256")
    assert result is None


def test_resolve_kid_uses_explicit_access_key_id():
    with patch("auth_user_service.services.auth.settings") as mock_settings:
        mock_settings.ACCESS_KEY_ID = "my-explicit-kid"
        mock_settings.ACCESS_PUBLIC_KEY = _RSA_PUBLIC_PEM

        result = _resolve_kid("RS256")

    assert result == "my-explicit-kid"


def test_resolve_kid_derives_fingerprint_when_no_access_key_id():
    with patch("auth_user_service.services.auth.settings") as mock_settings:
        mock_settings.ACCESS_KEY_ID = None
        mock_settings.ACCESS_PUBLIC_KEY = _RSA_PUBLIC_PEM

        result = _resolve_kid("RS256")

    assert result == _EXPECTED_KID_FINGERPRINT
    assert len(result) == 16


def test_resolve_kid_fingerprint_is_stable():
    """Same PEM always produces the same fingerprint (deterministic)."""
    with patch("auth_user_service.services.auth.settings") as mock_settings:
        mock_settings.ACCESS_KEY_ID = None
        mock_settings.ACCESS_PUBLIC_KEY = _RSA_PUBLIC_PEM

        result1 = _resolve_kid("RS256")
        result2 = _resolve_kid("RS256")

    assert result1 == result2


# ── kid embedded in issued JWT ────────────────────────────────────────────────


def test_issued_token_contains_kid_header_for_rs256():
    """JWT issued with RS256 must carry the kid header so consumers can select the key."""
    from auth_sdk_m8.schemas.auth import TokenAccessData, TokenSecret
    from auth_user_service.core.security import SecurityHelper

    secret = TokenSecret(secret_key=_RSA_PRIVATE_PEM, algorithm="RS256")
    data = TokenAccessData(
        sub="user-123",
        full_name="Test User",
        email="test@example.com",
        avatar=None,
        is_active=True,
        email_verified=True,
        is_superuser=False,
        role="user",
    )
    token, _ = SecurityHelper.create_access_token(
        data=data,
        expires_delta=timedelta(minutes=15),
        secrets=secret,
        kid="test-kid-abc",
    )
    header = jwt.get_unverified_header(token)
    assert header["kid"] == "test-kid-abc"
    assert header["alg"] == "RS256"


def test_issued_token_has_no_kid_header_for_hs256():
    """HS256 tokens must not carry a kid header (no public key to reference)."""
    from auth_sdk_m8.schemas.auth import TokenAccessData, TokenSecret
    from auth_user_service.core.security import SecurityHelper

    secret = TokenSecret(
        secret_key="Super-Secret-Key-1234-Test-abcDEF", algorithm="HS256"
    )
    data = TokenAccessData(
        sub="user-456",
        full_name="Test User",
        email="hs@example.com",
        avatar=None,
        is_active=True,
        email_verified=True,
        is_superuser=False,
        role="user",
    )
    token, _ = SecurityHelper.create_access_token(
        data=data,
        expires_delta=timedelta(minutes=15),
        secrets=secret,
        kid=None,
    )
    header = jwt.get_unverified_header(token)
    assert "kid" not in header
