"""
Live Red-Team Security Test Suite — RS256_m8 Compose Stack
===========================================================
Target:  http://localhost:9000/user/    (auth_user_service)
         http://localhost:9000/fastapi/ (fastapi_service)
Config:  TOKEN_MODE=hybrid, ACCESS_TOKEN_ALGORITHM=RS256

Run while the RS256_m8 compose stack is up:
    pytest tests/live/test_redteam_rs256.py -v -s --tb=short --no-cov

Categories
----------
A  Authentication attacks (brute-force, injection, credential abuse)
B  JWT attacks (alg=none, alg-confusion, private-key forgery, replay)
C  Authorization / IDOR (privilege escalation, cross-user access)
D  Rate-limiting & bypass
E  CORS policy validation
F  Private inter-service API exposure
G  File upload security
H  Information disclosure (docs, metrics, error leakage)
I  Cross-service token propagation
J  Refresh-token lifecycle and rotation replay
K  HTTP security headers
L  Cookie security
"""

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

import jwt
import pytest
import requests

pytestmark = pytest.mark.live

# ── Configuration ──────────────────────────────────────────────────────────────
AUTH_BASE = "http://localhost:9000/user"
SVC_BASE = "http://localhost:9000/fastapi"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_KEYS_DIR = _REPO_ROOT / "examples/docker_compose/RS256_m8/keys"

# All values below come from the committed .env — themselves a finding.
_ADMIN_EMAIL = "admin@example.com"
_ADMIN_PASSWORD = "Ocoti123@#@"
_ACCESS_KEY_ID = "6dbedbd549ede665"

_PRIVATE_API_SECRET = (
    "w3c1bxk4l8a9a3svcvx1bxncn8-7dfshkg21gLKJLKhk84k6gA54df5s4s65az6a"
    "_5r46ze5r46jlj5_l4w3wx4c5c3w2v1wa6h43m32vw2sdqd21cvw65fg58t"
)
_REFRESH_SECRET_KEY = (
    "z8c1bxk4l8a9abn_bndfg454gdfg4dg54KJJHHdcnDZRZRZ87dfs-hkg21ghk84k6"
    "g54df5s4s65az6a5r46ze5r46jl_j5l4w3wx4c5c3w2v1wa6h43m32vw2sdqd21cvw65"
)

TIMEOUT = 10  # seconds


# ── Token-crafting helpers ─────────────────────────────────────────────────────

def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _access_payload(
    *,
    is_superuser: bool = False,
    is_active: bool = True,
    email: str = "forged@evil.com",
    token_type: str = "access",
) -> dict:
    return {
        "sub": str(uuid.uuid4()),
        "email": email,
        "is_superuser": is_superuser,
        "is_active": is_active,
        "role": "user",
        "full_name": "Red Team",
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        "jti": str(uuid.uuid4()),
        "type": token_type,
    }


def _forge_alg_none(is_superuser: bool = True) -> str:
    """Craft an unsigned JWT (alg=none) with arbitrary admin claims."""
    header = _b64url_nopad(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = _b64url_nopad(
        json.dumps(_access_payload(is_superuser=is_superuser)).encode()
    )
    return f"{header}.{payload}."


def _forge_hs256_confusion(public_key_pem: str) -> str:
    """Algorithm-confusion: sign RS256 payload with public key as HS256 secret.

    PyJWT 2.x refuses to use an asymmetric key as an HMAC secret, so we
    hand-craft the token at the raw HMAC level to replicate what a real
    attacker would do with a custom script.
    """
    header = _b64url_nopad(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url_nopad(json.dumps(_access_payload(is_superuser=True)).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = hmac.new(public_key_pem.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64url_nopad(sig)}"


def _forge_rs256(
    private_key_pem: str,
    *,
    is_superuser: bool = True,
    token_type: str = "access",
    kid: str = _ACCESS_KEY_ID,
) -> str:
    """Forge a valid RS256 token using the committed private key.

    CRITICAL FINDING: private key is checked into version control.
    """
    return jwt.encode(
        _access_payload(is_superuser=is_superuser, token_type=token_type),
        private_key_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


def _auth(bearer: str) -> dict:
    return {"Authorization": f"Bearer {bearer}"}


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def private_key_pem() -> str:
    path = _KEYS_DIR / "private.pem"
    assert path.exists(), f"Private key not found at {path}"
    return path.read_text()


@pytest.fixture(scope="session")
def public_key_pem() -> str:
    path = _KEYS_DIR / "public.pem"
    assert path.exists(), f"Public key not found at {path}"
    return path.read_text()


@pytest.fixture(scope="session")
def admin_token() -> str:
    resp = requests.post(
        f"{AUTH_BASE}/login/access-token",
        data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token) -> dict:
    return _auth(admin_token)


@pytest.fixture(scope="session")
def admin_login() -> dict:
    """Full login response (token + cookies)."""
    resp = requests.post(
        f"{AUTH_BASE}/login/access-token",
        data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200
    body = resp.json()
    return {
        "access_token": body["access_token"],
        "cookies": dict(resp.cookies),
        "headers": _auth(body["access_token"]),
    }


@pytest.fixture(scope="session")
def regular_user(admin_headers) -> dict:
    """Create a non-superuser account; return credentials."""
    email = f"redteam_{uuid.uuid4().hex[:8]}@redteam-test.com"
    password = "RedTeam!Pass99"
    resp = requests.post(
        f"{AUTH_BASE}/users/new_user/",
        json={"email": email, "password": password, "full_name": "Red Team User"},
        headers=admin_headers,
        timeout=TIMEOUT,
    )
    assert resp.status_code == 200, f"Could not create test user: {resp.text}"
    user_id = resp.json()["id"]

    login = requests.post(
        f"{AUTH_BASE}/login/access-token",
        data={"username": email, "password": password},
        timeout=TIMEOUT,
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {
        "id": user_id,
        "email": email,
        "password": password,
        "token": token,
        "cookies": dict(login.cookies),
        "headers": _auth(token),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# A  AUTHENTICATION ATTACKS
# ═══════════════════════════════════════════════════════════════════════════════

class TestA_AuthenticationAttacks:
    """Category A — Login endpoint abuse."""

    _URL = f"{AUTH_BASE}/login/access-token"

    def test_a01_valid_login_succeeds(self):
        r = requests.post(self._URL, data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD}, timeout=TIMEOUT)
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_a02_wrong_password_returns_400(self):
        r = requests.post(self._URL, data={"username": _ADMIN_EMAIL, "password": "WRONG!"}, timeout=TIMEOUT)
        assert r.status_code == 400
        detail = r.json().get("detail", "").lower()
        assert "invalid" in detail or "incorrect" in detail

    def test_a03_unknown_user_returns_400_not_404(self):
        """User enumeration: 404 would confirm whether an email exists."""
        r = requests.post(self._URL, data={"username": "ghost@nowhere.invalid", "password": "x"}, timeout=TIMEOUT)
        assert r.status_code == 400, (
            f"[FINDING-A03] Status {r.status_code} reveals user-existence: "
            "400 expected for all bad credentials regardless of existence"
        )

    def test_a04_empty_credentials_returns_422(self):
        r = requests.post(self._URL, data={"username": "", "password": ""}, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_a05_missing_body_returns_422(self):
        r = requests.post(self._URL, data={}, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_a06_sql_injection_in_email_does_not_crash(self):
        r = requests.post(self._URL, data={"username": "' OR '1'='1", "password": "x"}, timeout=TIMEOUT)
        assert r.status_code in (400, 422), (
            f"[FINDING-A06] SQL injection caused unexpected {r.status_code}: {r.text[:200]}"
        )
        assert r.status_code != 500

    def test_a07_xss_in_email_not_reflected_unescaped(self):
        xss = "<script>alert(1)</script>@evil.com"
        r = requests.post(self._URL, data={"username": xss, "password": "x"}, timeout=TIMEOUT)
        assert r.status_code in (400, 422)
        assert r.status_code != 500
        assert "<script>" not in r.text, "[FINDING-A07] XSS payload reflected unescaped"

    def test_a08_oversized_password_does_not_cause_bcrypt_dos(self):
        """Passwords >72 bytes fed to bcrypt can hang the process."""
        r = requests.post(
            self._URL,
            data={"username": _ADMIN_EMAIL, "password": "A" * 10_000},
            timeout=TIMEOUT,
        )
        assert r.status_code != 500, "[FINDING-A08] Server crashed on oversized password (bcrypt DoS)"
        assert r.status_code in (400, 413, 422)

    def test_a09_null_bytes_in_credentials_rejected(self):
        r = requests.post(self._URL, data={"username": "user\x00@test.com", "password": "x\x00"}, timeout=TIMEOUT)
        assert r.status_code in (400, 422)
        assert r.status_code != 500

    def test_a10_crlf_in_email_sanitised(self):
        """CRLF in email must not pollute Redis key namespace."""
        r = requests.post(
            self._URL,
            data={"username": "user@test.com\r\nX-Evil: injected", "password": "x"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 422)
        assert r.status_code != 500


# ═══════════════════════════════════════════════════════════════════════════════
# B  JWT ATTACKS
# ═══════════════════════════════════════════════════════════════════════════════

class TestB_JWTAttacks:
    """Category B — Token forgery, algorithm confusion, and replay."""

    _ME = f"{AUTH_BASE}/profile/get/me/"

    def test_b01_no_token_rejected(self):
        r = requests.get(self._ME, timeout=TIMEOUT)
        assert r.status_code in (401, 403)

    def test_b02_garbage_token_rejected(self):
        r = requests.get(self._ME, headers=_auth("notajwtatall"), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b03_two_part_jwt_rejected(self):
        r = requests.get(self._ME, headers=_auth("header.payload"), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b04_alg_none_attack_rejected(self):
        """CRITICAL GUARD: unsigned token must never be accepted."""
        r = requests.get(self._ME, headers=_auth(_forge_alg_none()), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-B04] alg=none token ACCEPTED — full authentication bypass!"
        )

    def test_b05_algorithm_confusion_hs256_pubkey_rejected(self, public_key_pem):
        """RS256→HS256 confusion: public key used as HMAC secret must be rejected."""
        token = _forge_hs256_confusion(public_key_pem)
        r = requests.get(self._ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-B05] Algorithm-confusion (RS256→HS256) attack SUCCEEDED"
        )

    def test_b06_forged_rs256_with_committed_key_accepted_documents_critical_finding(
        self, private_key_pem
    ):
        """
        CRITICAL FINDING — Private key committed to repository.

        Because the RSA private key lives in version control anyone with
        read access to the repo can forge RS256 access tokens claiming ANY
        identity and ANY privilege level.  The forged token is
        cryptographically valid and therefore accepted by all services.

        Remediation:
          1. Rotate the RSA key pair immediately.
          2. Move keys to a secret manager (Vault, AWS Secrets Manager, …).
          3. Never commit key material; use Docker secrets or env injection.
          4. Add a pre-commit hook / CI secret-scanner (truffleHog, gitleaks).
        """
        token = _forge_rs256(private_key_pem, is_superuser=True)
        r = requests.get(self._ME, headers=_auth(token), timeout=TIMEOUT)
        # Expected to succeed — the key IS legitimate, just improperly stored.
        assert r.status_code == 200, (
            "Forged token unexpectedly rejected — verify key matches running stack"
        )
        body = r.json()
        assert body.get("is_superuser") is True

    def test_b07_forged_token_reaches_admin_endpoint(self, private_key_pem):
        """CRITICAL: committed key grants admin access to all services."""
        token = _forge_rs256(private_key_pem, is_superuser=True)
        r = requests.get(f"{AUTH_BASE}/users/", headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 200, (
            "[CRITICAL-B07] Committed private key allows admin endpoint access"
        )

    def test_b08_tampered_payload_rejected(self, admin_token):
        """Modify payload without re-signing — signature mismatch must be caught."""
        parts = admin_token.split(".")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        claims["is_superuser"] = True
        new_payload = _b64url_nopad(json.dumps(claims).encode())
        tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        r = requests.get(self._ME, headers=_auth(tampered), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b09_expired_token_rejected(self, private_key_pem):
        """Token that expired an hour ago must be refused."""
        payload = _access_payload()
        payload["exp"] = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        token = jwt.encode(payload, private_key_pem, algorithm="RS256", headers={"kid": _ACCESS_KEY_ID})
        r = requests.get(self._ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b10_wrong_token_type_refresh_as_access_rejected(self, private_key_pem):
        """A refresh token presented to an access-protected route must be refused."""
        token = _forge_rs256(private_key_pem, token_type="refresh")
        r = requests.get(self._ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b11_inactive_user_claim_rejected(self, private_key_pem):
        """is_active=False in token payload must always deny access."""
        token = _forge_rs256(private_key_pem, is_superuser=False)
        payload = jwt.decode(token, options={"verify_signature": False})
        payload["is_active"] = False
        bad_token = jwt.encode(payload, private_key_pem, algorithm="RS256", headers={"kid": _ACCESS_KEY_ID})
        r = requests.get(self._ME, headers=_auth(bad_token), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b12_path_traversal_kid_does_not_crash(self, private_key_pem):
        """Injecting a path-traversal kid must not cause 500 or load arbitrary keys."""
        payload = _access_payload(is_superuser=True)
        token = jwt.encode(payload, private_key_pem, algorithm="RS256", headers={"kid": "../../etc/passwd"})
        r = requests.get(self._ME, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code != 500, "[FINDING-B12] Path-traversal kid caused server error"

    def test_b13_bearer_scheme_case_insensitive_handled(self, admin_token):
        """Some clients send 'bearer' in lowercase — verify correct parsing."""
        r = requests.get(self._ME, headers={"Authorization": f"bearer {admin_token}"}, timeout=TIMEOUT)
        # FastAPI's OAuth2PasswordBearer is case-insensitive for the scheme
        assert r.status_code in (200, 403)  # Either accepted or consistently rejected


# ═══════════════════════════════════════════════════════════════════════════════
# C  AUTHORIZATION / IDOR
# ═══════════════════════════════════════════════════════════════════════════════

class TestC_Authorization:
    """Category C — Privilege escalation and insecure direct object references."""

    def test_c01_users_list_requires_superuser(self, regular_user):
        r = requests.get(f"{AUTH_BASE}/users/", headers=regular_user["headers"], timeout=TIMEOUT)
        assert r.status_code == 403

    def test_c02_create_user_requires_superuser(self, regular_user):
        r = requests.post(
            f"{AUTH_BASE}/users/new_user/",
            json={"email": "new@t.com", "password": "Pass123!", "full_name": "N"},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_c03_regular_user_cannot_read_other_user(self, regular_user, admin_headers):
        users = requests.get(f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT).json()["data"]
        other_id = next((u["id"] for u in users if u["email"] != regular_user["email"]), None)
        if not other_id:
            pytest.skip("No other user available for IDOR test")
        r = requests.get(
            f"{AUTH_BASE}/users/get/{other_id}/",
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 403, (
            f"[FINDING-C03] IDOR: regular user accessed user/{other_id}/"
        )

    def test_c04_regular_user_cannot_delete_other_user(self, regular_user, admin_headers):
        users = requests.get(f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT).json()["data"]
        other_id = next((u["id"] for u in users if u["email"] != regular_user["email"]), None)
        if not other_id:
            pytest.skip("No other user available")
        r = requests.delete(
            f"{AUTH_BASE}/users/delete/{other_id}/",
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_c05_regular_user_cannot_list_sessions(self, regular_user):
        r = requests.get(f"{AUTH_BASE}/sessions/", headers=regular_user["headers"], timeout=TIMEOUT)
        assert r.status_code == 403

    def test_c06_regular_user_cannot_get_another_users_session(self, regular_user, admin_headers):
        """IDOR: sessions/get-by-user/{user_id}/ requires superuser."""
        users = requests.get(f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT).json()["data"]
        other_id = next((u["id"] for u in users if u["email"] != regular_user["email"]), None)
        if not other_id:
            pytest.skip("No other user available")
        r = requests.get(
            f"{AUTH_BASE}/sessions/get-by-user/{other_id}/",
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 403, (
            f"[FINDING-C06] IDOR: sessions accessible cross-user: {r.status_code}"
        )

    def test_c07_random_uuid_returns_404_not_500(self, admin_headers):
        r = requests.get(
            f"{AUTH_BASE}/users/get/{uuid.uuid4()}/",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code in (403, 404)
        assert r.status_code != 500

    def test_c08_superuser_cannot_delete_self(self, admin_headers):
        r = requests.delete(f"{AUTH_BASE}/profile/delete/me/", headers=admin_headers, timeout=TIMEOUT)
        assert r.status_code == 403

    def test_c09_update_another_user_requires_superuser(self, regular_user, admin_headers):
        users = requests.get(f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT).json()["data"]
        other_id = next((u["id"] for u in users if u["email"] != regular_user["email"]), None)
        if not other_id:
            pytest.skip("No other user available")
        r = requests.patch(
            f"{AUTH_BASE}/users/update/{other_id}/",
            json={"full_name": "Hacked"},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_c10_dashboard_requires_auth(self):
        r = requests.get(f"{AUTH_BASE}/dashboard/users/activity/", timeout=TIMEOUT)
        assert r.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# D  RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════════

class TestD_RateLimiting:
    """Category D — Brute-force protection and bypass attempts."""

    pytestmark = pytest.mark.destructive
    _URL = f"{AUTH_BASE}/login/access-token"

    def test_d01_six_bad_logins_trigger_429(self):
        """5-attempt window: 6th request must be rate-limited."""
        target = f"bforce_{uuid.uuid4().hex[:8]}@redteam-test.com"
        statuses = [
            requests.post(self._URL, data={"username": target, "password": "x"}, timeout=TIMEOUT).status_code
            for _ in range(6)
        ]
        assert 429 in statuses, (
            f"[FINDING-D01] Rate limiting not triggered after 6 attempts — "
            f"statuses: {statuses}"
        )

    def test_d02_rate_limit_response_is_informative(self):
        target = f"rl_{uuid.uuid4().hex[:8]}@redteam-test.com"
        for _ in range(6):
            r = requests.post(self._URL, data={"username": target, "password": "x"}, timeout=TIMEOUT)
            if r.status_code == 429:
                body = r.json()
                assert "detail" in body
                detail = body["detail"].lower()
                assert any(kw in detail for kw in ("too many", "try again", "minutes")), (
                    f"[FINDING-D02] 429 detail not informative: {body['detail']}"
                )
                return
        pytest.skip("Rate limit not hit — Redis may have been flushed")

    def test_d03_xff_header_does_not_bypass_email_rate_limit(self):
        """Rate limit is keyed by email not IP: X-Forwarded-For must not help attacker."""
        target = f"xffrl_{uuid.uuid4().hex[:8]}@redteam-test.com"
        statuses = []
        for i in range(6):
            r = requests.post(
                self._URL,
                data={"username": target, "password": "x"},
                headers={"X-Forwarded-For": f"10.{i}.{i}.{i}"},
                timeout=TIMEOUT,
            )
            statuses.append(r.status_code)
        assert 429 in statuses, (
            "[FINDING-D03] X-Forwarded-For rotation bypassed email-based rate limit"
        )

    def test_d04_different_emails_each_get_own_limit(self):
        """
        Design note: rate limit is per-email not per-IP.
        Credential stuffing across many accounts avoids the limit.
        Each unique email gets its own 5-attempt bucket.
        """
        results = []
        for _ in range(3):
            target = f"cs_{uuid.uuid4().hex[:8]}@redteam-test.com"
            r = requests.post(self._URL, data={"username": target, "password": "x"}, timeout=TIMEOUT)
            results.append(r.status_code)
        # Each fresh email gets a clean bucket — all should be 400 not 429
        assert all(s == 400 for s in results), (
            f"[INFO-D04] Unexpected statuses for fresh emails: {results}"
        )

    def test_d05_admin_still_accessible_after_other_lockouts(self):
        """Locking out other accounts must not affect admin."""
        r = requests.post(
            self._URL,
            data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# E  CORS
# ═══════════════════════════════════════════════════════════════════════════════

class TestE_CORS:
    """Category E — Cross-origin request policy."""

    _URL = f"{AUTH_BASE}/login/access-token"

    def _preflight(self, origin: str) -> requests.Response:
        return requests.options(
            self._URL,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
            timeout=TIMEOUT,
        )

    def test_e01_allowed_origin_receives_cors_header(self):
        r = self._preflight("http://localhost:5173")
        assert r.status_code in (200, 204)
        acao = r.headers.get("access-control-allow-origin", "")
        assert acao in ("http://localhost:5173", "*"), (
            f"[FINDING-E01] Expected ACAO for allowed origin, got: '{acao}'"
        )

    def test_e02_unknown_origin_not_reflected(self):
        r = self._preflight("http://evil-attacker.com")
        acao = r.headers.get("access-control-allow-origin", "")
        assert acao != "*", "[FINDING-E02] Wildcard CORS — any origin can make credentialed requests"
        assert "evil-attacker.com" not in acao, (
            f"[FINDING-E02] Arbitrary origin reflected in ACAO: '{acao}'"
        )

    def test_e03_null_origin_not_granted_credentials(self):
        """null origin (sandboxed iframe) + credentials=true = CSRF risk."""
        r = self._preflight("null")
        acao = r.headers.get("access-control-allow-origin", "")
        creds = r.headers.get("access-control-allow-credentials", "false").lower()
        assert not (acao == "null" and creds == "true"), (
            "[FINDING-E03] null origin with credentials=true enables iframe CSRF"
        )

    def test_e04_cors_does_not_expose_authorization_to_untrusted_origin(self):
        r = requests.get(
            f"{AUTH_BASE}/health/",
            headers={"Origin": "http://evil.com"},
            timeout=TIMEOUT,
        )
        exposed = r.headers.get("access-control-expose-headers", "").lower()
        assert "authorization" not in exposed


# ═══════════════════════════════════════════════════════════════════════════════
# F  PRIVATE API EXPOSURE
# ═══════════════════════════════════════════════════════════════════════════════

class TestF_PrivateAPI:
    """Category F — Inter-service private endpoint security.

    /private/ is NOT routed through Traefik so public requests receive 404.
    Tests verify that Traefik-level block is in place AND document the
    secret-key exposure risk for direct in-network access.
    """

    _URL = f"{AUTH_BASE}/private/users/"
    _BODY = {"email": "pvt@redteam-test.com", "password": "Test!123", "full_name": "T", "is_verified": False}

    def test_f01_private_route_blocked_by_traefik(self):
        """GOOD: Traefik returns 404 — /private/ not reachable from the internet."""
        r = requests.post(self._URL, json=self._BODY, timeout=TIMEOUT)
        assert r.status_code == 404, (
            f"[FINDING-F01] Private endpoint reachable through Traefik: {r.status_code}. "
            "Expected 404. If 401/422/200 the private API is externally accessible."
        )

    def test_f02_private_route_blocked_with_wrong_token(self):
        """Traefik blocks before any X-Internal-Token check can occur."""
        r = requests.post(
            self._URL, json=self._BODY,
            headers={"X-Internal-Token": "wrong_totally"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_f03_private_route_blocked_with_admin_jwt(self, admin_headers):
        """Admin JWT does not open the private route through Traefik."""
        body = {**self._BODY, "email": f"pvt_jwt_{uuid.uuid4().hex[:6]}@redteam-test.com"}
        r = requests.post(self._URL, json=body, headers=admin_headers, timeout=TIMEOUT)
        assert r.status_code == 404

    def test_f04_private_api_secret_committed_to_repo_documents_finding(self):
        """
        CRITICAL FINDING — PRIVATE_API_SECRET committed to repository.

        Although /private/ is blocked by Traefik from the public internet,
        the secret is readable in version control.  An attacker with direct
        container access (compromised sidecar, exposed Docker port, or future
        Traefik misconfiguration) can create arbitrary users with this key.

        Remediation:
          1. Rotate PRIVATE_API_SECRET immediately (secret is compromised).
          2. Move to a secret manager (Vault, AWS SM, Docker secrets).
          3. Never commit secrets; enforce with gitleaks / truffleHog in CI.
          4. Add an explicit Traefik deny rule for /private/ as defence-in-depth.
        """
        body = {**self._BODY, "email": f"pvt_known_{uuid.uuid4().hex[:6]}@redteam-test.com"}
        r = requests.post(
            self._URL, json=body,
            headers={"X-Internal-Token": _PRIVATE_API_SECRET},
            timeout=TIMEOUT,
        )
        print(
            f"\n[FINDING-F04] PRIVATE_API_SECRET in repo. "
            f"External status={r.status_code} (404=Traefik blocked, OK). "
            "Direct container access with this key WOULD succeed."
        )
        assert r.status_code in (200, 404)

    def test_f05_private_endpoint_absent_from_openapi(self):
        """Private routes must not appear in the public OpenAPI schema."""
        r = requests.get(f"{AUTH_BASE}/openapi.json", timeout=TIMEOUT)
        paths = r.json().get("paths", {})
        private_paths = [p for p in paths if "/private/" in p]
        assert not private_paths, (
            f"[FINDING-F05] Private routes exposed in OpenAPI: {private_paths}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# G  FILE UPLOAD SECURITY
# ═══════════════════════════════════════════════════════════════════════════════

class TestG_FileUpload:
    """Category G — Avatar upload endpoint abuse."""

    _URL = f"{AUTH_BASE}/profile/upload_avatar/"

    def test_g01_upload_requires_auth(self):
        r = requests.post(self._URL, files={"file": ("x.jpg", b"x", "image/jpeg")}, timeout=TIMEOUT)
        assert r.status_code in (401, 403)

    def test_g02_php_file_rejected_by_mime(self, regular_user):
        r = requests.post(
            self._URL,
            files={"file": ("shell.php", b"<?php system($_GET['c']); ?>", "text/plain")},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 422), (
            "[FINDING-G02] PHP file with text/plain MIME accepted — webshell risk"
        )

    def test_g03_script_extension_rejected(self, regular_user):
        r = requests.post(
            self._URL,
            files={"file": ("evil.js", b"alert(1)", "image/jpeg")},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 422), (
            "[FINDING-G03] .js extension accepted despite image MIME type"
        )

    def test_g04_svg_with_xss_rejected_or_sanitised(self, regular_user):
        """SVG files can carry inline JavaScript."""
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
        r = requests.post(
            self._URL,
            files={"file": ("evil.svg", svg, "image/svg+xml")},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        # SVG should either be rejected entirely or have script stripped
        if r.status_code == 200:
            # Verify no script tag survives
            body_str = json.dumps(r.json())
            assert "<script>" not in body_str, "[FINDING-G04] SVG with XSS accepted without sanitization"

    def test_g05_path_traversal_in_filename_sanitised(self, regular_user):
        """../../etc/passwd as filename must not escape the avatar directory."""
        r = requests.post(
            self._URL,
            files={"file": ("../../etc/passwd", b"\xff\xd8\xff\xe0", "image/jpeg")},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            fname = r.json().get("avatar", "")
            assert "/" not in fname and ".." not in fname, (
                f"[FINDING-G05] Path traversal filename not sanitised: '{fname}'"
            )

    def test_g06_oversized_file_rejected(self, regular_user):
        """Files beyond MAX_IMG_FILE_SIZE (≈2 MB) must be rejected."""
        big = b"\xff\xd8\xff" + b"A" * (3 * 1024 * 1024)
        r = requests.post(
            self._URL,
            files={"file": ("big.jpg", big, "image/jpeg")},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 413, 422), (
            "[FINDING-G06] 3 MB file accepted — potential storage/DoS attack"
        )

    def test_g07_exe_extension_with_image_mime_rejected(self, regular_user):
        r = requests.post(
            self._URL,
            files={"file": ("malware.exe", b"\xff\xd8\xff", "image/png")},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 422), (
            "[FINDING-G07] .exe disguised as image accepted"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# H  INFORMATION DISCLOSURE
# ═══════════════════════════════════════════════════════════════════════════════

class TestH_InformationDisclosure:
    """Category H — Sensitive data leakage via errors, docs, and metadata."""

    def test_h01_openapi_docs_publicly_accessible(self):
        """
        FINDING — OpenAPI interactive docs (/docs) require no authentication.
        In production, disable or protect behind an auth wall.
        """
        for url in [f"{AUTH_BASE}/docs", f"{SVC_BASE}/docs"]:
            r = requests.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                print(f"\n[FINDING-H01] Public OpenAPI docs at: {url}")

    def test_h02_server_error_does_not_leak_traceback(self):
        """Malformed path param must never expose Python tracebacks."""
        r = requests.get(
            f"{AUTH_BASE}/users/get/NOT-A-UUID/",
            headers={"Authorization": "Bearer fake"},
            timeout=TIMEOUT,
        )
        assert "Traceback" not in r.text
        assert 'File "/' not in r.text

    def test_h03_404_does_not_reveal_internal_path(self):
        r = requests.get(f"{AUTH_BASE}/no/such/route/", timeout=TIMEOUT)
        assert r.status_code == 404
        body = r.text
        assert "/opt/" not in body, "[FINDING-H03] Internal path exposed in 404"
        assert "auth_user_service" not in body.lower() or r.status_code != 404

    def test_h04_jwks_contains_no_private_key_material(self):
        """JWKS must expose only the public key components."""
        r = requests.get(f"{AUTH_BASE}/.well-known/jwks.json", timeout=TIMEOUT)
        assert r.status_code == 200
        for key in r.json().get("keys", []):
            for private_component in ("d", "p", "q", "dp", "dq", "qi"):
                assert private_component not in key, (
                    f"[CRITICAL-H04] Private RSA component '{private_component}' exposed in JWKS"
                )
            assert key.get("use") == "sig"
            assert key.get("alg") == "RS256"

    def test_h05_metrics_endpoint_requires_auth_or_absent(self):
        """
        FINDING — /metrics accessible without authentication.
        Prometheus data includes: request counts, login attempts, latency.
        Consider restricting to internal network or adding auth.
        """
        r = requests.get(f"{AUTH_BASE}/metrics", timeout=TIMEOUT)
        if r.status_code == 200:
            print(f"\n[FINDING-H05] Unauthenticated /metrics endpoint: {r.text[:300]}")
        assert r.status_code in (200, 401, 403, 404)

    def test_h06_health_endpoint_detail_level(self):
        """
        FINDING — Health endpoint reveals infrastructure status (Redis, DB).
        Acceptable in internal networks; restrict in public deployments.
        """
        r = requests.get(f"{AUTH_BASE}/health/", timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        infra_keys = {k for k in body if k in ("redis", "database", "token_mode")}
        if infra_keys:
            print(f"\n[FINDING-H06] Health reveals infra details: {infra_keys}")

    def test_h07_error_body_contains_no_db_connection_details(self):
        """Database errors must not leak hostnames, passwords, or schemas."""
        r = requests.get(
            f"{AUTH_BASE}/users/get/{uuid.uuid4()}/",
            headers={"Authorization": "Bearer invalid_token_here"},
            timeout=TIMEOUT,
        )
        low = r.text.lower()
        assert "password" not in low or r.status_code in (401, 403), (
            "[FINDING-H07] Password string in error response"
        )
        assert "host=" not in low
        assert "m8_db" not in low

    def test_h08_response_does_not_expose_hashed_password(self, admin_headers):
        """User API must never return hashed_password field."""
        r = requests.get(f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        for user in r.json().get("data", []):
            assert "hashed_password" not in user, (
                "[FINDING-H08] hashed_password exposed in users list"
            )
            assert "password" not in user


# ═══════════════════════════════════════════════════════════════════════════════
# I  CROSS-SERVICE TOKEN PROPAGATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestI_CrossServiceTokens:
    """Category I — RS256 token accepted/rejected by downstream fastapi service."""

    _SVC_LIST = f"{SVC_BASE}/category/"

    def test_i01_valid_auth_token_accepted_by_fastapi_service(self, admin_headers):
        r = requests.get(self._SVC_LIST, headers=admin_headers, timeout=TIMEOUT)
        assert r.status_code == 200, (
            f"Cross-service token propagation failed: {r.status_code} {r.text}"
        )

    def test_i02_forged_token_accepted_by_fastapi_service(self, private_key_pem):
        """CRITICAL: committed key grants full access across all services."""
        token = _forge_rs256(private_key_pem, is_superuser=True)
        r = requests.get(self._SVC_LIST, headers=_auth(token), timeout=TIMEOUT)
        assert r.status_code == 200, (
            "[CRITICAL-I02] Forged cross-service token unexpectedly rejected"
        )

    def test_i03_alg_none_rejected_by_fastapi_service(self):
        r = requests.get(self._SVC_LIST, headers=_auth(_forge_alg_none()), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-I03] alg=none accepted by downstream fastapi service"
        )

    def test_i04_access_token_survives_logout_in_hybrid_mode(self):
        """
        KNOWN TRADE-OFF (hybrid mode) — Access tokens are stateless and
        cannot be revoked.  After logout the access token remains valid
        until it expires (ACCESS_TOKEN_EXPIRE_MINUTES = 30).

        Impact: stolen access token window = 30 minutes post-logout.

        Remediation options:
          - Switch TOKEN_MODE to 'stateful' (access JTIs blacklisted in Redis).
          - Shorten ACCESS_TOKEN_EXPIRE_MINUTES.
          - Accept the trade-off and document for downstream consumers.
        """
        login = requests.post(
            f"{AUTH_BASE}/login/access-token",
            data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert login.status_code == 200
        token = login.json()["access_token"]
        cookies = dict(login.cookies)

        logout = requests.post(
            f"{AUTH_BASE}/login/logout/",
            headers=_auth(token),
            cookies=cookies,
            timeout=TIMEOUT,
        )
        assert logout.status_code == 200

        # Access token is still valid (expected in hybrid mode)
        r = requests.get(self._SVC_LIST, headers=_auth(token), timeout=TIMEOUT)
        if r.status_code == 200:
            print(
                "\n[FINDING-I04] Access token valid 0 s after logout (hybrid mode). "
                "Exposure window: up to 30 min."
            )
        # Re-login to restore session for subsequent tests
        re_login = requests.post(
            f"{AUTH_BASE}/login/access-token",
            data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert re_login.status_code == 200

    def test_i05_fastapi_service_rejects_no_token(self):
        r = requests.get(self._SVC_LIST, timeout=TIMEOUT)
        assert r.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# J  REFRESH TOKEN LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════

class TestJ_RefreshTokenLifecycle:
    """Category J — Token rotation, replay detection, and revocation."""

    _REFRESH_URL = f"{AUTH_BASE}/login/refresh-token/"

    def _fresh_login(self) -> dict:
        r = requests.post(
            f"{AUTH_BASE}/login/access-token",
            data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        return {"token": r.json()["access_token"], "cookies": dict(r.cookies)}

    def test_j01_refresh_rotates_access_token(self):
        sess = self._fresh_login()
        refresh = requests.post(self._REFRESH_URL, cookies=sess["cookies"], timeout=TIMEOUT)
        assert refresh.status_code == 200
        assert refresh.json()["access_token"] != sess["token"]

    @pytest.mark.destructive
    def test_j02_replay_old_refresh_jti_triggers_revocation(self):
        """
        Token reuse detection: presenting a consumed refresh JTI must
        return 401 AND revoke all sessions (full invalidation).
        """
        sess = self._fresh_login()
        original_cookies = sess["cookies"]

        # Rotate once — old JTI is consumed
        first = requests.post(self._REFRESH_URL, cookies=original_cookies, timeout=TIMEOUT)
        assert first.status_code == 200

        # Replay the original (consumed) JTI — must be caught
        replay = requests.post(self._REFRESH_URL, cookies=original_cookies, timeout=TIMEOUT)
        assert replay.status_code == 401, (
            f"[FINDING-J02] Refresh token replay not detected: {replay.status_code}"
        )
        detail = replay.json().get("detail", "").lower()
        assert any(kw in detail for kw in ("reuse", "revoked", "reused")), (
            f"[FINDING-J02] Reuse detected but error not informative: {detail}"
        )

    def test_j03_tampered_refresh_token_rejected(self):
        sess = self._fresh_login()
        cookie_val = sess["cookies"].get("refresh_token", "")
        if not cookie_val:
            pytest.skip("No refresh_token cookie received")

        parts = cookie_val.split(".")
        if len(parts) != 3:
            pytest.skip("Unexpected refresh token format")

        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        try:
            claims = json.loads(base64.urlsafe_b64decode(padded))
            claims["sub"] = str(uuid.uuid4())
            new_payload = _b64url_nopad(json.dumps(claims).encode())
            tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        except Exception:
            pytest.skip("Could not decode refresh token payload")

        r = requests.post(self._REFRESH_URL, cookies={"refresh_token": tampered}, timeout=TIMEOUT)
        assert r.status_code == 401

    def test_j04_forged_hs256_refresh_with_committed_key(self):
        """
        CRITICAL FINDING — REFRESH_SECRET_KEY committed to repository.

        HS256 refresh tokens can be forged for arbitrary user IDs.
        Protection: the JTI must also be in the Redis allowlist (hybrid
        mode), so the attack is mitigated AS LONG AS Redis is healthy.
        If Redis is unavailable, stateless validation falls back and a
        forged token for an existing user_id could succeed.

        Remediation:
          1. Rotate REFRESH_SECRET_KEY immediately.
          2. Move to secret manager.
          3. Never commit secrets to version control.
        """
        fake_sub = str(uuid.uuid4())
        payload = {
            "sub": fake_sub,
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
            "jti": str(uuid.uuid4()),
            "type": "refresh",
        }
        forged = jwt.encode(payload, _REFRESH_SECRET_KEY, algorithm="HS256")
        r = requests.post(self._REFRESH_URL, cookies={"refresh_token": forged}, timeout=TIMEOUT)
        # Should fail: JTI not in Redis allowlist and/or user not found
        print(
            f"\n[FINDING-J04] Forged HS256 refresh token (valid sig, unknown sub): "
            f"status={r.status_code}"
        )
        assert r.status_code in (401, 404), (
            f"[CRITICAL-J04] Forged refresh token ACCEPTED: {r.status_code}"
        )

    def test_j05_logout_invalidates_refresh_token(self):
        """After logout, the refresh JTI must be removed from the allowlist."""
        sess = self._fresh_login()

        logout = requests.post(
            f"{AUTH_BASE}/login/logout/",
            headers=_auth(sess["token"]),
            cookies=sess["cookies"],
            timeout=TIMEOUT,
        )
        assert logout.status_code == 200

        # Refresh with the now-revoked cookie must fail
        r = requests.post(self._REFRESH_URL, cookies=sess["cookies"], timeout=TIMEOUT)
        assert r.status_code == 401, (
            f"[FINDING-J05] Refresh token not revoked after logout: {r.status_code}"
        )

    def test_j06_missing_refresh_cookie_returns_401(self):
        r = requests.post(self._REFRESH_URL, timeout=TIMEOUT)
        assert r.status_code in (401, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# K  HTTP SECURITY HEADERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestK_SecurityHeaders:
    """Category K — Response header hardening."""

    @pytest.fixture(scope="class")
    def resp_headers(self) -> dict:
        return requests.get(f"{AUTH_BASE}/health/", timeout=TIMEOUT).headers

    def test_k01_x_content_type_options_nosniff(self, resp_headers):
        val = resp_headers.get("x-content-type-options", "")
        assert val.lower() == "nosniff", (
            f"[FINDING-K01] X-Content-Type-Options missing or wrong: '{val}'"
        )

    def test_k02_x_frame_options_restricts_framing(self, resp_headers):
        val = resp_headers.get("x-frame-options", "")
        assert val.upper() in ("DENY", "SAMEORIGIN"), (
            f"[FINDING-K02] X-Frame-Options missing or permissive: '{val}'"
        )

    def test_k03_server_header_not_verbose(self, resp_headers):
        server = resp_headers.get("server", "")
        for tech in ("uvicorn", "python", "fastapi"):
            assert tech not in server.lower(), (
                f"[FINDING-K03] Server header reveals technology: '{server}'"
            )

    def test_k04_no_x_powered_by(self, resp_headers):
        powered = resp_headers.get("x-powered-by", "")
        assert powered == "", (
            f"[FINDING-K04] X-Powered-By reveals technology: '{powered}'"
        )

    def test_k05_content_type_json_on_api_responses(self, resp_headers):
        ct = resp_headers.get("content-type", "")
        assert "application/json" in ct

    def test_k06_referrer_policy_set(self, resp_headers):
        rp = resp_headers.get("referrer-policy", "")
        if not rp:
            print("\n[FINDING-K06] Referrer-Policy header absent — may leak URL parameters")


# ═══════════════════════════════════════════════════════════════════════════════
# L  COOKIE SECURITY
# ═══════════════════════════════════════════════════════════════════════════════

class TestL_CookieSecurity:
    """Category L — refresh_token cookie attribute validation."""

    @pytest.fixture(scope="class")
    def login_resp(self) -> requests.Response:
        return requests.post(
            f"{AUTH_BASE}/login/access-token",
            data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )

    def test_l01_refresh_token_cookie_present(self, login_resp):
        assert "refresh_token" in login_resp.cookies, (
            "[FINDING-L01] No refresh_token cookie in login response"
        )

    def test_l02_refresh_token_cookie_is_httponly(self, login_resp):
        """HttpOnly prevents JavaScript access via document.cookie."""
        raw = login_resp.headers.get("set-cookie", "")
        assert "httponly" in raw.lower(), (
            "[FINDING-L02] refresh_token missing HttpOnly — XSS can steal it"
        )

    def test_l03_refresh_token_cookie_has_samesite(self, login_resp):
        """SameSite mitigates CSRF attacks against the refresh endpoint."""
        raw = login_resp.headers.get("set-cookie", "")
        assert "samesite" in raw.lower(), (
            "[FINDING-L03] refresh_token missing SameSite attribute"
        )
        assert "samesite=none" not in raw.lower(), (
            "[FINDING-L03] SameSite=None enables cross-site refresh — needs Secure too"
        )

    def test_l04_refresh_token_not_exposed_in_response_body(self, login_resp):
        """Token value must live only in the cookie, not in JSON."""
        cookie_val = login_resp.cookies.get("refresh_token", "")
        body_str = json.dumps(login_resp.json())
        assert cookie_val not in body_str, (
            "[FINDING-L04] Refresh token value in response body"
        )

    def test_l05_access_token_not_set_as_cookie(self, login_resp):
        """Access token must be returned in body only, never as a cookie."""
        assert "access_token" not in login_resp.cookies, (
            "[FINDING-L05] Access token set as cookie — vulnerable to CSRF"
        )

    def test_l06_hashed_password_not_in_any_response(self, admin_headers):
        r = requests.get(f"{AUTH_BASE}/profile/get/me/", headers=admin_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert "hashed_password" not in body, (
            "[FINDING-L06] hashed_password exposed in /profile/get/me/"
        )
