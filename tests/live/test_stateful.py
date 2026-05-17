"""
Live Security Tests — Stateful & Hybrid Token Mode
====================================================
Target:  http://localhost:9000/user/
Config:  TOKEN_MODE=stateful OR TOKEN_MODE=hybrid

Tests the refresh token lifecycle: rotation, replay detection, and revocation.
Both stateful and hybrid modes track refresh JTIs in Redis, so all tests here
apply equally to both modes.

For hybrid-mode-specific behavior (access tokens surviving logout) see
test_hybrid.py.

Auto-skipped when the running stack uses TOKEN_MODE=stateless.

Run:
    pytest tests/live/test_stateful.py -v --no-cov
    pytest tests/live -m live_stateful --no-cov
"""

import base64
import json
import uuid

import pytest
import requests

from tests.live.suites.auth_flows import AUTH_BASE, TIMEOUT, fresh_login
from tests.live.suites.token_forge import forge_hs256

pytestmark = [
    pytest.mark.live,
    pytest.mark.live_stateful,
    pytest.mark.require_token_mode("stateful", "hybrid"),
]

_REFRESH_URL = f"{AUTH_BASE}/login/refresh-token/"
_ADMIN_EMAIL = "admin@example.com"
_ADMIN_PASSWORD = "Ocoti123@#@"

_REFRESH_SECRET_KEY = (
    "z8c1bxk4l8a9abn_bndfg454gdfg4dg54KJJHHdcnDZRZRZ87dfs-hkg21ghk84k6"
    "g54df5s4s65az6a5r46ze5r46jl_j5l4w3wx4c5c3w2v1wa6h43m32vw2sdqd21cvw65"
)


def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


# ═══════════════════════════════════════════════════════════════════════════════
# J  REFRESH TOKEN LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════


class TestJ_RefreshTokenLifecycle:
    """Category J — Token rotation, replay detection, and revocation."""

    def test_j01_refresh_rotates_access_token(self):
        """Each refresh call must return a new access token."""
        sess = fresh_login()
        refresh = requests.post(
            _REFRESH_URL, cookies=sess["cookies"], timeout=TIMEOUT
        )
        assert refresh.status_code == 200
        assert refresh.json()["access_token"] != sess["token"]

    @pytest.mark.destructive
    def test_j02_replay_old_refresh_jti_triggers_revocation(self):
        """
        Token reuse detection: presenting a consumed refresh JTI must
        return 401 AND revoke all sessions (full chain invalidation).
        """
        sess = fresh_login()
        original_cookies = sess["cookies"]

        first = requests.post(
            _REFRESH_URL, cookies=original_cookies, timeout=TIMEOUT
        )
        assert first.status_code == 200

        replay = requests.post(
            _REFRESH_URL, cookies=original_cookies, timeout=TIMEOUT
        )
        assert replay.status_code == 401, (
            f"[FINDING-J02] Refresh token replay not detected: {replay.status_code}"
        )
        detail = replay.json().get("detail", "").lower()
        assert any(kw in detail for kw in ("reuse", "revoked", "reused")), (
            f"[FINDING-J02] Replay detected but error not informative: {detail}"
        )

    def test_j03_tampered_refresh_token_rejected(self):
        """Modified refresh token payload (without re-signing) must be refused."""
        sess = fresh_login()
        cookie_val = sess["cookies"].get("refresh_token", "")
        if not cookie_val:
            pytest.skip("No refresh_token cookie received")

        parts = cookie_val.split(".")
        if len(parts) != 3:
            pytest.skip("Unexpected refresh token format")

        try:
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(padded))
            claims["sub"] = str(uuid.uuid4())
            new_payload = _b64url_nopad(json.dumps(claims).encode())
            tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        except (ValueError, KeyError):
            pytest.skip("Could not decode refresh token payload")

        r = requests.post(
            _REFRESH_URL, cookies={"refresh_token": tampered}, timeout=TIMEOUT
        )
        assert r.status_code == 401

    def test_j04_forged_hs256_refresh_with_committed_key(self):
        """
        CRITICAL FINDING — REFRESH_SECRET_KEY committed to repository.

        HS256 refresh tokens can be forged for arbitrary user IDs.
        Protection: the JTI must also be in the Redis allowlist (stateful/
        hybrid mode), so the attack is mitigated AS LONG AS Redis is healthy.

        Remediation:
          1. Rotate REFRESH_SECRET_KEY immediately.
          2. Move to secret manager.
          3. Never commit secrets to version control.
        """
        forged = forge_hs256(_REFRESH_SECRET_KEY)
        r = requests.post(
            _REFRESH_URL, cookies={"refresh_token": forged}, timeout=TIMEOUT
        )
        print(
            f"\n[FINDING-J04] Forged HS256 refresh (valid sig, unknown sub): "
            f"status={r.status_code}"
        )
        # Must fail: JTI not in Redis allowlist and/or user not found
        assert r.status_code in (401, 404), (
            f"[CRITICAL-J04] Forged refresh token ACCEPTED: {r.status_code}"
        )

    def test_j05_logout_invalidates_refresh_token(self):
        """After logout, the refresh JTI must be removed from the allowlist."""
        sess = fresh_login()

        logout = requests.post(
            f"{AUTH_BASE}/login/logout/",
            headers=sess["headers"],
            cookies=sess["cookies"],
            timeout=TIMEOUT,
        )
        assert logout.status_code == 200

        r = requests.post(_REFRESH_URL, cookies=sess["cookies"], timeout=TIMEOUT)
        assert r.status_code == 401, (
            f"[FINDING-J05] Refresh token not revoked after logout: {r.status_code}"
        )

    def test_j06_missing_refresh_cookie_returns_401_or_422(self):
        r = requests.post(_REFRESH_URL, timeout=TIMEOUT)
        assert r.status_code in (401, 422)

    def test_j07_refresh_endpoint_rejects_access_token_in_cookie(self):
        """An access token placed in the refresh_token cookie must be refused."""
        sess = fresh_login()
        r = requests.post(
            _REFRESH_URL,
            cookies={"refresh_token": sess["token"]},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401, (
            f"[FINDING-J07] Access token accepted at refresh endpoint: "
            f"{r.status_code}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# S  SESSION / REVOCATION  (stateful-only)
# ═══════════════════════════════════════════════════════════════════════════════


class TestS_StatefulRevocation:
    """Category S — Access token revocation at logout (stateful mode only)."""

    pytestmark = [
        pytest.mark.live,
        pytest.mark.live_stateful,
        pytest.mark.require_token_mode("stateful"),
    ]

    _ME = f"{AUTH_BASE}/profile/get/me/"

    def test_s01_logout_revokes_access_token_immediately(self):
        """
        In stateful mode access tokens are blacklisted on logout.
        The token must be rejected with 403 immediately after logout.
        """
        sess = fresh_login()

        r_before = requests.get(
            self._ME, headers=sess["headers"], timeout=TIMEOUT
        )
        assert r_before.status_code == 200

        requests.post(
            f"{AUTH_BASE}/login/logout/",
            headers=sess["headers"],
            cookies=sess["cookies"],
            timeout=TIMEOUT,
        )

        r_after = requests.get(
            self._ME, headers=sess["headers"], timeout=TIMEOUT
        )
        assert r_after.status_code in (401, 403), (
            f"[FINDING-S01] Access token still valid after logout in stateful mode: "
            f"{r_after.status_code}"
        )

    def test_s02_new_login_after_revocation_works(self):
        """Revocation of one session must not block future logins."""
        sess = fresh_login()
        requests.post(
            f"{AUTH_BASE}/login/logout/",
            headers=sess["headers"],
            cookies=sess["cookies"],
            timeout=TIMEOUT,
        )
        new_sess = fresh_login()
        r = requests.get(self._ME, headers=new_sess["headers"], timeout=TIMEOUT)
        assert r.status_code == 200
