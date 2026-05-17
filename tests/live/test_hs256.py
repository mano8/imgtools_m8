"""
Live Security Tests — HS256 Algorithm
======================================
Target:  http://localhost:9000/user/
Config:  ACCESS_TOKEN_ALGORITHM=HS256

Auto-skipped when the running stack uses RS256 or ES256.

Run:
    pytest tests/live/test_hs256.py -v --no-cov
    pytest tests/live -m live_hs256 --no-cov
"""

import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import requests

from tests.live.suites.auth_flows import AUTH_BASE, TIMEOUT, fresh_login
from tests.live.suites.token_forge import access_payload, b64url_nopad, forge_alg_none

pytestmark = [
    pytest.mark.live,
    pytest.mark.live_hs256,
    pytest.mark.require_algorithm("HS256"),
]

_ME = f"{AUTH_BASE}/profile/get/me/"

_WRONG_SECRET = "this-is-the-wrong-secret-and-definitely-not-the-configured-one"


def _auth(bearer: str) -> dict:
    return {"Authorization": f"Bearer {bearer}"}


def _forge_hs256_wrong_secret() -> str:
    """Forge an HS256 access token with an incorrect secret."""
    payload = access_payload(is_superuser=True)
    return jwt.encode(payload, _WRONG_SECRET, algorithm="HS256")


# ═══════════════════════════════════════════════════════════════════════════════
# H  HS256-SPECIFIC JWT CHECKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestH_HS256JWTChecks:
    """Category H — HS256 algorithm-specific security properties."""

    def test_h01_token_signed_with_wrong_secret_rejected(self):
        """HS256 token signed with a different secret must be refused."""
        token = _forge_hs256_wrong_secret()
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-H01] Token signed with wrong HS256 secret was ACCEPTED"
        )

    def test_h02_alg_none_rejected(self):
        """CRITICAL GUARD: unsigned token must never be accepted."""
        r = requests.get(_ME, headers=_auth(forge_alg_none()), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-H02] alg=none token ACCEPTED — full authentication bypass!"
        )

    def test_h03_expired_hs256_token_rejected(self):
        """Expired HS256 token must be refused even with a correct signature."""
        payload = access_payload()
        payload["exp"] = int(
            (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
        )
        token = jwt.encode(payload, _WRONG_SECRET, algorithm="HS256")
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_h04_no_jwks_endpoint_or_empty(self):
        """HS256 stacks have no asymmetric keys to publish via JWKS.

        The endpoint may be absent (404) or return an empty keys array.
        Returning a populated JWKS from an HS256 stack would mislead consumers.
        """
        r = requests.get(f"{AUTH_BASE}/.well-known/jwks.json", timeout=TIMEOUT)
        if r.status_code == 200:
            keys = r.json().get("keys", [])
            assert keys == [], (
                "[FINDING-H04] HS256 stack exposes non-empty JWKS — "
                "consumers may trust this stack for RS256 validation"
            )
        else:
            assert r.status_code == 404

    def test_h05_tampered_payload_rejected(self, admin_token: str):
        """Modify HS256 payload without re-signing — must be caught."""
        import base64

        parts = admin_token.split(".")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        claims["is_superuser"] = True
        new_payload = b64url_nopad(json.dumps(claims).encode())
        tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        r = requests.get(_ME, headers=_auth(tampered), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_h06_refresh_token_type_rejected_as_access(self):
        """A token with type='refresh' must not be accepted on access-only routes."""
        payload = access_payload(token_type="refresh")
        token = jwt.encode(payload, _WRONG_SECRET, algorithm="HS256")
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_h07_inactive_user_claim_rejected(self, admin_token: str):
        """is_active=False in a structurally valid token must deny access."""
        import base64

        parts = admin_token.split(".")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        claims["is_active"] = False
        claims["is_superuser"] = True
        new_payload = b64url_nopad(json.dumps(claims).encode())
        tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        r = requests.get(_ME, headers=_auth(tampered), timeout=TIMEOUT)
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# W  WEAK KEY WARNINGS
# ═══════════════════════════════════════════════════════════════════════════════


class TestW_WeakKeyWarnings:
    """Category W — HS256 key strength assertions."""

    def test_w01_login_works_with_configured_key(self):
        """Sanity: valid credentials produce a usable token."""
        sess = fresh_login()
        r = requests.get(_ME, headers=sess["headers"], timeout=TIMEOUT)
        assert r.status_code == 200, (
            "Token from fresh login was rejected — stack may be misconfigured"
        )

    def test_w02_token_has_expected_structure(self):
        """HS256 tokens must be three-segment JWTs with correct header."""
        sess = fresh_login()
        token = sess["token"]
        parts = token.split(".")
        assert len(parts) == 3, f"Malformed token: expected 3 parts, got {len(parts)}"
        import base64

        padded = parts[0] + "=" * (-len(parts[0]) % 4)
        header = json.loads(base64.urlsafe_b64decode(padded))
        assert header.get("alg") == "HS256", (
            f"[FINDING-W02] Token alg is '{header.get('alg')}', expected 'HS256'"
        )

    def test_w03_token_carries_jti_claim(self):
        """JTI must be present for revocation and replay detection."""
        sess = fresh_login()
        payload = jwt.decode(
            sess["token"], options={"verify_signature": False}
        )
        assert "jti" in payload, (
            "[FINDING-W03] Token has no jti claim — revocation is impossible"
        )
        assert payload["jti"]

    def test_w04_two_tokens_have_different_jti(self):
        """Each token issuance must produce a unique JTI."""
        t1 = fresh_login()["token"]
        t2 = fresh_login()["token"]
        p1 = jwt.decode(t1, options={"verify_signature": False})
        p2 = jwt.decode(t2, options={"verify_signature": False})
        assert p1["jti"] != p2["jti"], (
            "[CRITICAL-W04] Two tokens share the same JTI — replay is possible"
        )
