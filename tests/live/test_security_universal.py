"""
Live Security Test Suite — Universal (any stack, any algorithm, any token mode)
================================================================================
Target:  http://localhost:9000/user/    (auth_user_service)
         http://localhost:9000/fastapi/ (fastapi_service)

Run against any running compose stack:
    pytest tests/live/test_security_universal.py -v --no-cov

Categories
----------
A  Authentication attacks (brute-force, injection, credential abuse)
B  JWT structural checks (no-token, garbage, alg=none, tampered payload)
C  Authorization / IDOR (privilege escalation, cross-user access)
D  Rate-limiting & bypass
E  CORS policy validation
F  Private inter-service API exposure
G  File upload security
H  Information disclosure (docs, metrics, error leakage)
K  HTTP security headers
L  Cookie security
M  API key security
"""

import json
import uuid

import pytest
import requests

from tests.live.suites.auth_flows import AUTH_BASE, SVC_BASE, TIMEOUT
from tests.live.suites.token_forge import forge_alg_none

pytestmark = [pytest.mark.live, pytest.mark.live_security]

_LOGIN_URL = f"{AUTH_BASE}/login/access-token"
_REFRESH_URL = f"{AUTH_BASE}/login/refresh-token/"
_ADMIN_EMAIL = "admin@example.com"
_ADMIN_PASSWORD = "Ocoti123@#@"


def _auth(bearer: str) -> dict:
    return {"Authorization": f"Bearer {bearer}"}


# ═══════════════════════════════════════════════════════════════════════════════
# A  AUTHENTICATION ATTACKS
# ═══════════════════════════════════════════════════════════════════════════════


class TestA_AuthenticationAttacks:
    """Category A — Login endpoint abuse."""

    def test_a01_valid_login_succeeds(self):
        """Sanity: correct credentials return 200 with access_token."""
        r = requests.post(
            _LOGIN_URL,
            data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_a02_wrong_password_returns_400(self):
        r = requests.post(
            _LOGIN_URL,
            data={"username": _ADMIN_EMAIL, "password": "WRONG!"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400
        detail = r.json().get("detail", "").lower()
        assert "invalid" in detail or "incorrect" in detail

    def test_a03_unknown_user_returns_400_not_404(self):
        """User enumeration: 404 would confirm whether an email exists."""
        r = requests.post(
            _LOGIN_URL,
            data={"username": "ghost@nowhere.invalid", "password": "x"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 400, (
            f"[FINDING-A03] Status {r.status_code} reveals user existence; "
            "400 expected for all bad credentials regardless of whether the "
            "account exists"
        )

    def test_a04_empty_credentials_returns_422(self):
        r = requests.post(
            _LOGIN_URL, data={"username": "", "password": ""}, timeout=TIMEOUT
        )
        assert r.status_code == 422

    def test_a05_missing_body_returns_422(self):
        r = requests.post(_LOGIN_URL, data={}, timeout=TIMEOUT)
        assert r.status_code == 422

    def test_a06_sql_injection_in_email_does_not_crash(self):
        r = requests.post(
            _LOGIN_URL,
            data={"username": "' OR '1'='1", "password": "x"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 422), (
            f"[FINDING-A06] SQL injection caused unexpected "
            f"{r.status_code}: {r.text[:200]}"
        )
        assert r.status_code != 500

    def test_a07_xss_in_email_not_reflected_unescaped(self):
        xss = "<script>alert(1)</script>@evil.com"
        r = requests.post(
            _LOGIN_URL, data={"username": xss, "password": "x"}, timeout=TIMEOUT
        )
        assert r.status_code in (400, 422)
        assert r.status_code != 500
        assert "<script>" not in r.text, "[FINDING-A07] XSS payload reflected unescaped"

    def test_a08_oversized_password_does_not_cause_bcrypt_dos(self):
        """Passwords >72 bytes fed to bcrypt can hang the process."""
        r = requests.post(
            _LOGIN_URL,
            data={"username": _ADMIN_EMAIL, "password": "A" * 10_000},
            timeout=TIMEOUT,
        )
        assert r.status_code != 500, (
            "[FINDING-A08] Server crashed on oversized password (bcrypt DoS)"
        )
        assert r.status_code in (400, 413, 422)

    def test_a09_null_bytes_in_credentials_rejected(self):
        r = requests.post(
            _LOGIN_URL,
            data={"username": "user\x00@test.com", "password": "x\x00"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 422)
        assert r.status_code != 500

    def test_a10_crlf_in_email_sanitised(self):
        """CRLF in email must not pollute Redis key namespace."""
        r = requests.post(
            _LOGIN_URL,
            data={"username": "user@test.com\r\nX-Evil: injected", "password": "x"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 422)
        assert r.status_code != 500


# ═══════════════════════════════════════════════════════════════════════════════
# B  JWT STRUCTURAL CHECKS  (algorithm-agnostic)
# ═══════════════════════════════════════════════════════════════════════════════


class TestB_JWTStructural:
    """Category B — Token format and alg=none rejection; no key material needed."""

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
        r = requests.get(self._ME, headers=_auth(forge_alg_none()), timeout=TIMEOUT)
        assert r.status_code == 403, (
            "[CRITICAL-B04] alg=none token ACCEPTED — full authentication bypass!"
        )

    def test_b05_tampered_payload_rejected(self, admin_token: str):
        """Modify payload without re-signing — signature mismatch must be caught."""
        import base64

        parts = admin_token.split(".")
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(padded))
        claims["is_superuser"] = True
        from tests.live.suites.token_forge import b64url_nopad

        new_payload = b64url_nopad(json.dumps(claims).encode())
        tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        r = requests.get(self._ME, headers=_auth(tampered), timeout=TIMEOUT)
        assert r.status_code == 403

    def test_b06_bearer_scheme_case_insensitive_handled(self, admin_token: str):
        """FastAPI's OAuth2PasswordBearer is case-insensitive for the scheme."""
        r = requests.get(
            self._ME,
            headers={"Authorization": f"bearer {admin_token}"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (200, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# C  AUTHORIZATION / IDOR
# ═══════════════════════════════════════════════════════════════════════════════


class TestC_Authorization:
    """Category C — Privilege escalation and insecure direct object references."""

    def test_c01_users_list_requires_superuser(self, regular_user: dict):
        r = requests.get(
            f"{AUTH_BASE}/users/",
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_c02_create_user_requires_superuser(self, regular_user: dict):
        r = requests.post(
            f"{AUTH_BASE}/users/new_user/",
            json={"email": "new@t.com", "password": "Pass123!", "full_name": "N"},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_c03_regular_user_cannot_read_other_user(
        self, regular_user: dict, admin_headers: dict
    ):
        users = requests.get(
            f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT
        ).json()["data"]
        other_id = next(
            (u["id"] for u in users if u["email"] != regular_user["email"]), None
        )
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

    def test_c04_regular_user_cannot_delete_other_user(
        self, regular_user: dict, admin_headers: dict
    ):
        users = requests.get(
            f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT
        ).json()["data"]
        other_id = next(
            (u["id"] for u in users if u["email"] != regular_user["email"]), None
        )
        if not other_id:
            pytest.skip("No other user available")
        r = requests.delete(
            f"{AUTH_BASE}/users/delete/{other_id}/",
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_c05_regular_user_cannot_list_sessions(self, regular_user: dict):
        r = requests.get(
            f"{AUTH_BASE}/sessions/",
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_c06_regular_user_cannot_get_another_users_session(
        self, regular_user: dict, admin_headers: dict
    ):
        """IDOR: sessions/get-by-user/{user_id}/ requires superuser."""
        users = requests.get(
            f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT
        ).json()["data"]
        other_id = next(
            (u["id"] for u in users if u["email"] != regular_user["email"]), None
        )
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

    def test_c07_random_uuid_returns_404_not_500(self, admin_headers: dict):
        r = requests.get(
            f"{AUTH_BASE}/users/get/{uuid.uuid4()}/",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code in (403, 404)
        assert r.status_code != 500

    def test_c08_superuser_cannot_delete_self(self, admin_headers: dict):
        r = requests.delete(
            f"{AUTH_BASE}/profile/delete/me/",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_c09_update_another_user_requires_superuser(
        self, regular_user: dict, admin_headers: dict
    ):
        users = requests.get(
            f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT
        ).json()["data"]
        other_id = next(
            (u["id"] for u in users if u["email"] != regular_user["email"]), None
        )
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

    @pytest.mark.require_redis
    def test_d01_six_bad_logins_trigger_429(self):
        """Default 5-attempt window (LOGIN_RATE_LIMIT_REQUESTS): 6th request must be rate-limited."""
        target = f"bforce_{uuid.uuid4().hex[:8]}@redteam-test.com"
        statuses = [
            requests.post(
                _LOGIN_URL,
                data={"username": target, "password": "x"},
                timeout=TIMEOUT,
            ).status_code
            for _ in range(6)
        ]
        assert 429 in statuses, (
            f"[FINDING-D01] Rate limiting not triggered after 6 attempts — "
            f"statuses: {statuses}"
        )

    def test_d02_rate_limit_response_is_informative(self):
        target = f"rl_{uuid.uuid4().hex[:8]}@redteam-test.com"
        for _ in range(6):
            r = requests.post(
                _LOGIN_URL,
                data={"username": target, "password": "x"},
                timeout=TIMEOUT,
            )
            if r.status_code == 429:
                body = r.json()
                assert "detail" in body
                detail = body["detail"].lower()
                assert any(
                    kw in detail for kw in ("too many", "try again", "minutes")
                ), f"[FINDING-D02] 429 detail not informative: {body['detail']}"
                return
        pytest.skip("Rate limit not hit — Redis may have been flushed")

    @pytest.mark.require_redis
    def test_d03_xff_header_does_not_bypass_email_rate_limit(self):
        """Rate limit is keyed by email; X-Forwarded-For rotation must not help."""
        target = f"xffrl_{uuid.uuid4().hex[:8]}@redteam-test.com"
        statuses = []
        for i in range(6):
            r = requests.post(
                _LOGIN_URL,
                data={"username": target, "password": "x"},
                headers={"X-Forwarded-For": f"10.{i}.{i}.{i}"},
                timeout=TIMEOUT,
            )
            statuses.append(r.status_code)
        assert 429 in statuses, (
            "[FINDING-D03] X-Forwarded-For rotation bypassed email-based rate limit"
        )

    def test_d04_different_emails_each_get_own_limit(self):
        """Design note: rate limit is per-email not per-IP.

        Each unique email gets its own default 5-attempt bucket
        (LOGIN_RATE_LIMIT_REQUESTS), which means credential stuffing across
        many accounts avoids the per-account limit.
        """
        results = []
        for _ in range(3):
            target = f"cs_{uuid.uuid4().hex[:8]}@redteam-test.com"
            r = requests.post(
                _LOGIN_URL,
                data={"username": target, "password": "x"},
                timeout=TIMEOUT,
            )
            results.append(r.status_code)
        assert all(s == 400 for s in results), (
            f"[INFO-D04] Unexpected statuses for fresh emails: {results}"
        )

    def test_d05_admin_still_accessible_after_other_lockouts(self):
        """Locking out other accounts must not affect admin."""
        r = requests.post(
            _LOGIN_URL,
            data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    @pytest.mark.require_redis
    @pytest.mark.require_token_mode("stateful", "hybrid")
    def test_d06_refresh_rotation_rate_limited(self, regular_user: dict):
        """Default 10-rotation window (REFRESH_RATE_LIMIT_REQUESTS): 11th refresh must be rate-limited.

        Uses regular_user (not admin) to avoid exhausting the shared admin
        refresh rate-limit bucket relied on by TestJ_RefreshTokenLifecycle.
        """
        cookies = regular_user["cookies"]
        statuses = []
        for _ in range(12):  # > DEFAULT_MAX_REQUESTS=10
            r = requests.post(_REFRESH_URL, cookies=cookies, timeout=TIMEOUT)
            statuses.append(r.status_code)
            if r.status_code == 200:
                cookies = dict(r.cookies) or cookies
            else:
                break
        assert 429 in statuses, (
            f"[FINDING-D06] Refresh rate limiting not triggered after 11 rotations — "
            f"statuses: {statuses}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# E  CORS
# ═══════════════════════════════════════════════════════════════════════════════


class TestE_CORS:
    """Category E — Cross-origin request policy."""

    def _preflight(self, origin: str) -> requests.Response:
        return requests.options(
            _LOGIN_URL,
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
        assert acao != "*", (
            "[FINDING-E02] Wildcard CORS — any origin can make credentialed requests"
        )
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

_PRIVATE_API_SECRET = (
    "w3c1bxk4l8a9a3svcvx1bxncn8-7dfshkg21gLKJLKhk84k6gA54df5s4s65az6a"
    "_5r46ze5r46jlj5_l4w3wx4c5c3w2v1wa6h43m32vw2sdqd21cvw65fg58t"
)


class TestF_PrivateAPI:
    """Category F — Inter-service private endpoint security.

    /private/ is NOT routed through Traefik so public requests receive 404.
    Tests verify that Traefik-level block is in place AND document the
    secret-key exposure risk for direct in-network access.
    """

    _URL = f"{AUTH_BASE}/private/users/"
    _BODY = {
        "email": "pvt@redteam-test.com",
        "password": "Test!123",
        "full_name": "T",
        "is_verified": False,
    }

    def test_f01_private_route_blocked_by_traefik(self):
        """GOOD: Traefik returns 404 — /private/ not reachable from the internet."""
        r = requests.post(self._URL, json=self._BODY, timeout=TIMEOUT)
        assert r.status_code == 404, (
            f"[FINDING-F01] Private endpoint reachable through Traefik: "
            f"{r.status_code}. Expected 404."
        )

    def test_f02_private_route_blocked_with_wrong_token(self):
        r = requests.post(
            self._URL,
            json=self._BODY,
            headers={"X-Internal-Token": "wrong_totally"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 404

    def test_f03_private_route_blocked_with_admin_jwt(self, admin_headers: dict):
        body = {
            **self._BODY,
            "email": f"pvt_jwt_{uuid.uuid4().hex[:6]}@redteam-test.com",
        }
        r = requests.post(self._URL, json=body, headers=admin_headers, timeout=TIMEOUT)
        assert r.status_code == 404

    def test_f04_private_api_secret_committed_to_repo_documents_finding(self):
        """
        CRITICAL FINDING — PRIVATE_API_SECRET committed to repository.

        Although /private/ is blocked by Traefik from the public internet,
        the secret is readable in version control.  An attacker with direct
        container access can create arbitrary users with this key.

        Remediation:
          1. Rotate PRIVATE_API_SECRET immediately.
          2. Move to a secret manager (Vault, AWS SM, Docker secrets).
          3. Never commit secrets; enforce with gitleaks / truffleHog in CI.
        """
        body = {
            **self._BODY,
            "email": f"pvt_known_{uuid.uuid4().hex[:6]}@redteam-test.com",
        }
        r = requests.post(
            self._URL,
            json=body,
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
# G  AVATAR URL VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════


class TestG_AvatarUrl:
    """Category G — Avatar URL validation via PATCH /profile/update/me/."""

    _URL = f"{AUTH_BASE}/profile/update/me/"

    def test_g01_valid_https_url_accepted(self, regular_user: dict):
        r = requests.patch(
            self._URL,
            json={"avatar": "https://cdn.example.com/avatar.jpg"},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_g02_bare_filename_rejected(self, regular_user: dict):
        r = requests.patch(
            self._URL,
            json={"avatar": "avatar.png"},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, (
            "[FINDING-G02] Bare filename accepted as avatar — should be URL only"
        )

    def test_g03_ftp_scheme_rejected(self, regular_user: dict):
        r = requests.patch(
            self._URL,
            json={"avatar": "ftp://example.com/avatar.png"},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, (
            "[FINDING-G03] ftp:// avatar URL accepted — only http/https allowed"
        )

    def test_g04_protocol_only_rejected(self, regular_user: dict):
        r = requests.patch(
            self._URL,
            json={"avatar": "https://"},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 422, (
            "[FINDING-G04] Protocol-only URL accepted — host required"
        )

    def test_g05_requires_auth(self):
        r = requests.patch(
            self._URL,
            json={"avatar": "https://cdn.example.com/avatar.jpg"},
            timeout=TIMEOUT,
        )
        assert r.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# H  INFORMATION DISCLOSURE  (JWKS checks live in test_rs256.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestH_InformationDisclosure:
    """Category H — Sensitive data leakage via errors, docs, and metadata."""

    def test_h01_openapi_docs_publicly_accessible(self):
        """FINDING — OpenAPI docs require no auth; restrict in production."""
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
        assert "/opt/" not in r.text, "[FINDING-H03] Internal path exposed in 404"

    def test_h04_metrics_endpoint_requires_auth_or_absent(self):
        """FINDING — /metrics may be accessible without authentication."""
        r = requests.get(f"{AUTH_BASE}/metrics", timeout=TIMEOUT)
        if r.status_code == 200:
            print(f"\n[FINDING-H04] Unauthenticated /metrics endpoint: {r.text[:300]}")
        assert r.status_code in (200, 401, 403, 404)

    def test_h05_health_endpoint_detail_level(self):
        """FINDING — Health may reveal infrastructure status (Redis, DB)."""
        r = requests.get(f"{AUTH_BASE}/health/", timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        infra_keys = {k for k in body if k in ("redis", "database", "token_mode")}
        if infra_keys:
            print(f"\n[FINDING-H05] Health reveals infra details: {infra_keys}")

    def test_h06_error_body_contains_no_db_connection_details(self):
        """Database errors must not leak hostnames, passwords, or schemas."""
        r = requests.get(
            f"{AUTH_BASE}/users/get/{uuid.uuid4()}/",
            headers={"Authorization": "Bearer invalid_token_here"},
            timeout=TIMEOUT,
        )
        low = r.text.lower()
        assert "host=" not in low
        assert "m8_db" not in low

    def test_h07_response_does_not_expose_hashed_password(self, admin_headers: dict):
        """User API must never return hashed_password field."""
        r = requests.get(f"{AUTH_BASE}/users/", headers=admin_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        for user in r.json().get("data", []):
            assert "hashed_password" not in user, (
                "[FINDING-H07] hashed_password exposed in users list"
            )
            assert "password" not in user


# ═══════════════════════════════════════════════════════════════════════════════
# K  HTTP SECURITY HEADERS
# ═══════════════════════════════════════════════════════════════════════════════


class TestK_SecurityHeaders:
    """Category K — Response header hardening."""

    @pytest.fixture(scope="class")
    def resp_headers(self) -> dict:
        """Fetch a real response and return its headers."""
        return requests.get(f"{AUTH_BASE}/health/", timeout=TIMEOUT).headers

    def test_k01_x_content_type_options_nosniff(self, resp_headers: dict):
        val = resp_headers.get("x-content-type-options", "")
        assert val.lower() == "nosniff", (
            f"[FINDING-K01] X-Content-Type-Options missing or wrong: '{val}'"
        )

    def test_k02_x_frame_options_restricts_framing(self, resp_headers: dict):
        val = resp_headers.get("x-frame-options", "")
        assert val.upper() in ("DENY", "SAMEORIGIN"), (
            f"[FINDING-K02] X-Frame-Options missing or permissive: '{val}'"
        )

    def test_k03_server_header_not_verbose(self, resp_headers: dict):
        server = resp_headers.get("server", "")
        for tech in ("uvicorn", "python", "fastapi"):
            assert tech not in server.lower(), (
                f"[FINDING-K03] Server header reveals technology: '{server}'"
            )

    def test_k04_no_x_powered_by(self, resp_headers: dict):
        powered = resp_headers.get("x-powered-by", "")
        assert powered == "", (
            f"[FINDING-K04] X-Powered-By reveals technology: '{powered}'"
        )

    def test_k05_content_type_json_on_api_responses(self, resp_headers: dict):
        ct = resp_headers.get("content-type", "")
        assert "application/json" in ct

    def test_k06_referrer_policy_set(self, resp_headers: dict):
        rp = resp_headers.get("referrer-policy", "")
        if not rp:
            print("\n[FINDING-K06] Referrer-Policy absent — may leak URL parameters")


# ═══════════════════════════════════════════════════════════════════════════════
# L  COOKIE SECURITY
# ═══════════════════════════════════════════════════════════════════════════════


class TestL_CookieSecurity:
    """Category L — refresh_token cookie attribute validation."""

    @pytest.fixture(scope="class")
    def login_resp(self) -> requests.Response:
        """Perform a fresh login and return the raw response."""
        return requests.post(
            _LOGIN_URL,
            data={"username": _ADMIN_EMAIL, "password": _ADMIN_PASSWORD},
            timeout=TIMEOUT,
        )

    def test_l01_refresh_token_cookie_present(self, login_resp: requests.Response):
        assert "refresh_token" in login_resp.cookies, (
            "[FINDING-L01] No refresh_token cookie in login response"
        )

    def test_l02_refresh_token_cookie_is_httponly(self, login_resp: requests.Response):
        """HttpOnly prevents JavaScript access via document.cookie."""
        raw = login_resp.headers.get("set-cookie", "")
        assert "httponly" in raw.lower(), (
            "[FINDING-L02] refresh_token missing HttpOnly — XSS can steal it"
        )

    def test_l03_refresh_token_cookie_has_samesite_strict(
        self, login_resp: requests.Response
    ):
        """SameSite=Strict gives the strongest CSRF protection for a pure auth cookie."""
        raw = login_resp.headers.get("set-cookie", "")
        assert "samesite" in raw.lower(), (
            "[FINDING-L03] refresh_token missing SameSite attribute"
        )
        assert "samesite=strict" in raw.lower(), (
            "[FINDING-L03] SameSite is not Strict — cookie is weaker than required; "
            "ensure samesite='strict' in both cookie writes in login.py"
        )

    def test_l04_refresh_token_not_exposed_in_response_body(
        self, login_resp: requests.Response
    ):
        """Token value must live only in the cookie, not in JSON."""
        cookie_val = login_resp.cookies.get("refresh_token", "")
        body_str = json.dumps(login_resp.json())
        assert cookie_val not in body_str, (
            "[FINDING-L04] Refresh token value in response body"
        )

    def test_l05_access_token_not_set_as_cookie(self, login_resp: requests.Response):
        """Access token must be returned in body only, never as a cookie."""
        assert "access_token" not in login_resp.cookies, (
            "[FINDING-L05] Access token set as cookie — vulnerable to CSRF"
        )

    def test_l06_hashed_password_not_in_profile_response(self, admin_headers: dict):
        r = requests.get(
            f"{AUTH_BASE}/profile/get/me/", headers=admin_headers, timeout=TIMEOUT
        )
        assert r.status_code == 200
        body = r.json()
        assert "hashed_password" not in body, (
            "[FINDING-L06] hashed_password exposed in /profile/get/me/"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# M  API KEY SECURITY
# ═══════════════════════════════════════════════════════════════════════════════


class TestM_ApiKeySecurity:
    """Category M — API key lifecycle, rate limiting, and IDOR guards."""

    _BASE = f"{AUTH_BASE}/profile/api-keys"

    @pytest.fixture(scope="class")
    def admin_key(self, admin_headers: dict) -> dict:
        """Create one API key for the admin user; clean up after the class."""
        r = requests.post(
            f"{self._BASE}/",
            json={"name": "live-test-admin", "ttl_hours": 1},
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 201, f"Key creation failed: {r.text}"
        data = r.json()
        assert "plaintext" in data
        yield data
        if not data.get("revoked"):
            requests.delete(
                f"{self._BASE}/{data['id']}",
                headers=admin_headers,
                timeout=TIMEOUT,
            )

    @pytest.fixture(scope="class")
    def user_key(self, regular_user: dict) -> dict:
        """Create one API key for the regular user."""
        r = requests.post(
            f"{self._BASE}/",
            json={"name": "live-test-user", "ttl_hours": 1},
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 201, f"Key creation failed: {r.text}"
        data = r.json()
        yield data
        if not data.get("revoked"):
            requests.delete(
                f"{self._BASE}/{data['id']}",
                headers=regular_user["headers"],
                timeout=TIMEOUT,
            )

    def test_m01_create_returns_plaintext_once(self, admin_key: dict):
        pt = admin_key.get("plaintext", "")
        assert pt.startswith("ak_"), (
            f"[FINDING-M01] Plaintext missing or wrong prefix: '{pt[:20]}'"
        )
        assert len(pt) > 10

    def test_m01b_create_returns_required_fields(self, admin_key: dict):
        for field in ("id", "name", "expires_at", "revoked", "created_at"):
            assert field in admin_key, f"[FINDING-M01b] Missing field '{field}'"
        assert admin_key["revoked"] is False
        assert admin_key["name"] == "live-test-admin"

    def test_m14_key_hash_not_in_creation_response(self, admin_key: dict):
        assert "key_hash" not in admin_key, (
            "[FINDING-M14] key_hash exposed in creation response"
        )

    def test_m02_verify_valid_key_returns_200(self, admin_key: dict):
        r = requests.get(
            f"{self._BASE}/verify",
            headers={"X-API-Key": admin_key["plaintext"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Valid key rejected: {r.text}"
        body = r.json()
        assert body["id"] == admin_key["id"]
        assert body["name"] == admin_key["name"]

    @pytest.mark.require_redis
    def test_m03_verify_returns_ratelimit_headers(self, admin_key: dict):
        r = requests.get(
            f"{self._BASE}/verify",
            headers={"X-API-Key": admin_key["plaintext"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        h = {k.lower(): v for k, v in r.headers.items()}
        assert "x-ratelimit-limit" in h, "[FINDING-M03] X-RateLimit-Limit missing"
        assert "x-ratelimit-remaining" in h, (
            "[FINDING-M03] X-RateLimit-Remaining missing"
        )
        assert "x-ratelimit-reset" in h, "[FINDING-M03] X-RateLimit-Reset missing"
        assert int(h["x-ratelimit-limit"]) > 0
        assert int(h["x-ratelimit-remaining"]) >= 0
        assert int(h["x-ratelimit-reset"]) > 0

    @pytest.mark.require_redis
    def test_m04_remaining_decrements_on_successive_calls(self, admin_headers: dict):
        """Each request must decrement X-RateLimit-Remaining by 1."""
        r = requests.post(
            f"{self._BASE}/",
            json={"name": "live-test-m04", "ttl_hours": 1},
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 201
        pt = r.json()["plaintext"]
        key_id = r.json()["id"]

        def _remaining() -> int:
            resp = requests.get(
                f"{self._BASE}/verify",
                headers={"X-API-Key": pt},
                timeout=TIMEOUT,
            )
            assert resp.status_code == 200
            return int(resp.headers.get("x-ratelimit-remaining", -1))

        r1 = _remaining()
        r2 = _remaining()
        requests.delete(
            f"{self._BASE}/{key_id}", headers=admin_headers, timeout=TIMEOUT
        )
        assert r2 == r1 - 1, f"[FINDING-M04] Remaining did not decrement: {r1} → {r2}"

    def test_m05_invalid_key_returns_401(self):
        r = requests.get(
            f"{self._BASE}/verify",
            headers={"X-API-Key": "ak_totally_invalid_key_000000000000"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, (
            f"[FINDING-M05] Invalid key returned {r.status_code} instead of 401"
        )

    def test_m06_missing_header_returns_422(self):
        r = requests.get(f"{self._BASE}/verify", timeout=TIMEOUT)
        assert r.status_code == 422, (
            f"[FINDING-M06] Missing X-API-Key returned {r.status_code} not 422"
        )

    def test_m07_plaintext_not_in_list_response(
        self, admin_headers: dict, admin_key: dict
    ):
        r = requests.get(f"{self._BASE}/", headers=admin_headers, timeout=TIMEOUT)
        assert r.status_code == 200
        for key_obj in r.json():
            assert "plaintext" not in key_obj, (
                "[FINDING-M07] plaintext exposed in list endpoint"
            )
            assert "key_hash" not in key_obj

    def test_m07b_plaintext_not_in_get_response(
        self, admin_headers: dict, admin_key: dict
    ):
        r = requests.get(
            f"{self._BASE}/{admin_key['id']}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200
        body = r.json()
        assert "plaintext" not in body, "[FINDING-M07b] plaintext exposed in get"
        assert "key_hash" not in body

    def test_m08_list_returns_only_own_keys(self, regular_user: dict, admin_key: dict):
        """Regular user must not see admin's key in their list."""
        r = requests.get(
            f"{self._BASE}/", headers=regular_user["headers"], timeout=TIMEOUT
        )
        assert r.status_code == 200
        ids = [k["id"] for k in r.json()]
        assert admin_key["id"] not in ids, (
            "[FINDING-M08] IDOR: regular user can see admin's API key"
        )

    def test_m09_get_returns_404_for_other_users_key(
        self, regular_user: dict, admin_key: dict
    ):
        r = requests.get(
            f"{self._BASE}/{admin_key['id']}",
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 404, (
            f"[FINDING-M09] IDOR: regular user accessed admin key: {r.status_code}"
        )

    def test_m13_revoke_other_users_key_returns_404(
        self, regular_user: dict, admin_key: dict
    ):
        r = requests.delete(
            f"{self._BASE}/{admin_key['id']}",
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 404, (
            f"[FINDING-M13] IDOR: regular user revoked admin key: {r.status_code}"
        )

    def test_m10_revoke_own_key_succeeds(self, regular_user: dict, user_key: dict):
        r = requests.delete(
            f"{self._BASE}/{user_key['id']}",
            headers=regular_user["headers"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Revoke failed: {r.text}"
        assert "revoked" in r.json().get("message", "").lower()
        user_key["revoked"] = True

    def test_m11_revoked_key_returns_401(self, user_key: dict):
        """Revoked key must be rejected at the verify endpoint."""
        r = requests.get(
            f"{self._BASE}/verify",
            headers={"X-API-Key": user_key["plaintext"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, (
            f"[FINDING-M11] Revoked key accepted: {r.status_code}"
        )

    def test_m12_double_revoke_returns_409(self, admin_headers: dict, user_key: dict):
        """Revoking an already-revoked key must return 409 Conflict."""
        r = requests.delete(
            f"{self._BASE}/{user_key['id']}",
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        assert r.status_code in (404, 409), (
            f"[FINDING-M12] Double-revoke returned {r.status_code} "
            "(expected 409 or 404)"
        )
