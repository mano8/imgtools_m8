"""
Live Security Tests — Asymmetric Algorithms (RS256 / ES256)
============================================================
Target:  http://localhost:9000/user/    (auth_user_service)
         http://localhost:9000/fastapi/ (fastapi_service)
Config:  ACCESS_TOKEN_ALGORITHM=RS256 or ES256

The asymmetric attack surface (alg=none, algorithm confusion, JWKS key
exposure, attacker-generated key) is the same for RS256 and ES256.
Tests that forge tokens with committed RSA key material are RS256-specific
but the security contract they verify applies to all asymmetric stacks.

Auto-skipped when the running stack uses HS256.

Run:
    pytest tests/live/test_asymmetric.py -v --no-cov
    pytest tests/live -m live_asymmetric --no-cov
"""

import json
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import requests

from tests.live.suites.auth_flows import AUTH_BASE, SVC_BASE, TIMEOUT
from tests.live.suites.token_forge import (
    access_payload,
    b64url_nopad,
    forge_alg_none,
    forge_hs256_with_pubkey,
    forge_rs256,
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.live_asymmetric,
    pytest.mark.require_algorithm("RS256", "ES256"),
]

_ACCESS_KEY_ID = "6dbedbd549ede665"
_ME = f"{AUTH_BASE}/profile/get/me/"


def _auth(bearer: str) -> dict:
    return {"Authorization": f"Bearer {bearer}"}


# ═══════════════════════════════════════════════════════════════════════════════
# B  JWT ATTACKS  (RS256-specific)
# ═══════════════════════════════════════════════════════════════════════════════


class TestB_RS256JWTAttacks:
    """Category B — RS256-specific token forgery and algorithm confusion."""

    def test_b01_alg_none_rejected(self):
        """CRITICAL GUARD: unsigned token must never be accepted."""
        r = requests.get(_ME, headers=_auth(forge_alg_none()), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-B01] alg=none token ACCEPTED — full authentication bypass!"
        )

    def test_b02_algorithm_confusion_hs256_pubkey_rejected(
        self, public_key_pem: str
    ):
        """RS256→HS256 confusion: public key used as HMAC secret must be rejected."""
        token = forge_hs256_with_pubkey(public_key_pem)
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-B02] Algorithm-confusion (RS256→HS256) attack SUCCEEDED"
        )

    def test_b03_forged_rs256_with_committed_key_accepted_documents_critical_finding(
        self, private_key_pem: str
    ):
        """
        CRITICAL FINDING — Private key committed to repository.

        Anyone with read access to the repo can forge RS256 access tokens
        claiming ANY identity and ANY privilege level.  The forged token is
        cryptographically valid and therefore accepted by all services.

        Remediation:
          1. Rotate the RSA key pair immediately.
          2. Move keys to a secret manager (Vault, AWS Secrets Manager, …).
          3. Never commit key material; use Docker secrets or env injection.
          4. Add a pre-commit hook / CI secret-scanner (truffleHog, gitleaks).
        """
        token = forge_rs256(private_key_pem, is_superuser=True)
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 200, (
            "Forged token unexpectedly rejected — verify key matches running stack"
        )
        assert r.json().get("is_superuser") is True

    def test_b04_forged_token_reaches_admin_endpoint(self, private_key_pem: str):
        """CRITICAL: committed key grants admin access to all services."""
        token = forge_rs256(private_key_pem, is_superuser=True)
        r = requests.get(f"{AUTH_BASE}/users/", headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 200, (
            "[CRITICAL-B04] Committed private key allows admin endpoint access"
        )

    def test_b05_expired_token_rejected(self, private_key_pem: str):
        """Token that expired an hour ago must be refused."""
        payload = access_payload()
        payload["exp"] = int(
            (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
        )
        token = jwt.encode(
            payload,
            private_key_pem,
            algorithm="RS256",
            headers={"kid": _ACCESS_KEY_ID},
        )
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b06_wrong_token_type_refresh_as_access_rejected(
        self, private_key_pem: str
    ):
        """A refresh token presented to an access-protected route must be refused."""
        token = forge_rs256(private_key_pem, token_type="refresh")
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b07_inactive_user_claim_rejected(self, private_key_pem: str):
        """is_active=False in token payload must always deny access."""
        payload = access_payload(is_superuser=False)
        payload["is_active"] = False
        token = jwt.encode(
            payload,
            private_key_pem,
            algorithm="RS256",
            headers={"kid": _ACCESS_KEY_ID},
        )
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b08_path_traversal_kid_does_not_crash(self, private_key_pem: str):
        """Injecting a path-traversal kid must not cause 500 or load arbitrary keys."""
        payload = access_payload(is_superuser=True)
        token = jwt.encode(
            payload,
            private_key_pem,
            algorithm="RS256",
            headers={"kid": "../../etc/passwd"},
        )
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code != 500, (
            "[FINDING-B08] Path-traversal kid caused server error"
        )

    def test_b09_tampered_rs256_payload_rejected(self, admin_token: str):
        """Modify payload without re-signing — RS256 signature mismatch caught."""
        parts = admin_token.split(".")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        import base64

        claims = json.loads(base64.urlsafe_b64decode(padded))
        claims["is_superuser"] = True
        new_payload = b64url_nopad(json.dumps(claims).encode())
        tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        r = requests.get(_ME, headers=_auth(tampered), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b10_attacker_generated_rsa_key_rejected(self):
        """Token signed with an attacker's own RSA key pair must be rejected."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        attacker_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        attacker_pem = attacker_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ).decode()
        payload = access_payload(is_superuser=True)
        token = jwt.encode(
            payload,
            attacker_pem,
            algorithm="RS256",
            headers={"kid": _ACCESS_KEY_ID},
        )
        r = requests.get(_ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-B10] Token signed with attacker RSA key was ACCEPTED"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# H  JWKS ENDPOINT  (asymmetric stacks only)
# ═══════════════════════════════════════════════════════════════════════════════


class TestH_JWKS:
    """Category H — JWKS endpoint security for RS256 stacks."""

    def test_h01_jwks_endpoint_is_present(self):
        r = requests.get(f"{AUTH_BASE}/.well-known/jwks.json", timeout=TIMEOUT)
        assert r.status_code == 200, (
            "[FINDING-H01] RS256 stack has no JWKS endpoint — "
            "downstream consumers cannot fetch the public key"
        )

    def test_h02_jwks_contains_no_private_key_material(self):
        """JWKS must expose only the public key components."""
        r = requests.get(f"{AUTH_BASE}/.well-known/jwks.json", timeout=TIMEOUT)
        assert r.status_code == 200
        keys = r.json().get("keys", [])
        assert keys, "[FINDING-H02] JWKS has no keys"
        for key in keys:
            for priv in ("d", "p", "q", "dp", "dq", "qi"):
                assert priv not in key, (
                    f"[CRITICAL-H02] Private RSA component '{priv}' exposed in JWKS"
                )
            assert key.get("use") == "sig"
            assert key.get("alg") in ("RS256", "ES256")

    def test_h03_jwks_kid_matches_token_header(self):
        """The kid in the JWKS must match the kid in issued tokens."""
        login = requests.post(
            f"{AUTH_BASE}/login/access-token",
            data={"username": "admin@example.com", "password": "Ocoti123@#@"},
            timeout=TIMEOUT,
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        header = jwt.get_unverified_header(token)
        token_kid = header.get("kid")

        jwks = requests.get(f"{AUTH_BASE}/.well-known/jwks.json", timeout=TIMEOUT)
        jwks_kids = {k.get("kid") for k in jwks.json().get("keys", [])}
        assert token_kid in jwks_kids, (
            f"[FINDING-H03] Token kid '{token_kid}' not found in JWKS kids {jwks_kids}"
        )

    def test_h04_jwks_is_valid_json_with_keys_array(self):
        r = requests.get(f"{AUTH_BASE}/.well-known/jwks.json", timeout=TIMEOUT)
        body = r.json()
        assert "keys" in body
        assert isinstance(body["keys"], list)
        assert len(body["keys"]) >= 1

    def test_h05_jwks_key_has_required_fields(self):
        r = requests.get(f"{AUTH_BASE}/.well-known/jwks.json", timeout=TIMEOUT)
        for key in r.json().get("keys", []):
            for field in ("kty", "use", "kid", "alg", "n", "e"):
                assert field in key, (
                    f"[FINDING-H05] JWKS key missing required field '{field}'"
                )
            assert key["kty"] == "RSA"


# ═══════════════════════════════════════════════════════════════════════════════
# I  CROSS-SERVICE TOKEN PROPAGATION  (RS256)
# ═══════════════════════════════════════════════════════════════════════════════


class TestI_CrossServiceTokens:
    """Category I — RS256 token accepted/rejected by downstream fastapi service."""

    _SVC_LIST = f"{SVC_BASE}/category/"

    def test_i01_valid_auth_token_accepted_by_fastapi_service(
        self, admin_headers: dict
    ):
        r = requests.get(self._SVC_LIST, headers=admin_headers, timeout=TIMEOUT)
        assert r.status_code == 200, (
            f"Cross-service token propagation failed: {r.status_code} {r.text}"
        )

    def test_i02_forged_token_accepted_by_fastapi_service(
        self, private_key_pem: str
    ):
        """CRITICAL: committed key grants full access across all services."""
        token = forge_rs256(private_key_pem, is_superuser=True)
        r = requests.get(self._SVC_LIST, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 200, (
            "[CRITICAL-I02] Forged cross-service token unexpectedly rejected"
        )

    def test_i03_alg_none_rejected_by_fastapi_service(self):
        r = requests.get(
            self._SVC_LIST, headers=_auth(forge_alg_none()), timeout=TIMEOUT
        )
        assert r.status_code == 403, (
            "[CRITICAL-I03] alg=none accepted by downstream fastapi service"
        )

    def test_i04_fastapi_service_rejects_no_token(self):
        r = requests.get(self._SVC_LIST, timeout=TIMEOUT)
        assert r.status_code in (401, 403)

    def test_i05_attacker_rs256_key_rejected_by_fastapi_service(self):
        """Downstream service must also reject tokens from an attacker's key."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        attacker_key = rsa.generate_private_key(
            public_exponent=65537, key_size=2048
        )
        attacker_pem = attacker_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ).decode()
        token = forge_rs256(attacker_pem, is_superuser=True)
        r = requests.get(self._SVC_LIST, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-I05] Attacker RS256 token accepted by fastapi service"
        )
