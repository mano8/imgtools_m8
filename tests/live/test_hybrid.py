"""
Live Security Tests — Hybrid Token Mode
========================================
Target:  http://localhost:9000/user/
Config:  TOKEN_MODE=hybrid

Hybrid mode: access tokens are stateless (no Redis lookup for validation),
refresh tokens are stateful (JTIs tracked in Redis).

Documented trade-off:
  - Access tokens remain valid for up to ACCESS_TOKEN_EXPIRE_MINUTES after logout.
  - Refresh token replay is detected and triggers full session invalidation.
  - Shorter ACCESS_TOKEN_EXPIRE_MINUTES reduces the revocation gap.

Auto-skipped when the running stack uses TOKEN_MODE=stateful or stateless.

Run:
    pytest tests/live/test_hybrid.py -v --no-cov
    pytest tests/live -m live_hybrid --no-cov
"""

import base64
import json
import uuid

import pytest
import requests

from tests.live.suites.auth_flows import AUTH_BASE, TIMEOUT, fresh_login
from tests.live.suites.token_forge import forge_alg_none, forge_hs256

pytestmark = [
    pytest.mark.live,
    pytest.mark.live_hybrid,
    pytest.mark.require_token_mode("hybrid"),
]

_ME = f"{AUTH_BASE}/profile/get/me/"
_REFRESH_URL = f"{AUTH_BASE}/login/refresh-token/"

_REFRESH_SECRET_KEY = (
    "z8c1bxk4l8a9abn_bndfg454gdfg4dg54KJJHHdcnDZRZRZ87dfs-hkg21ghk84k6"
    "g54df5s4s65az6a5r46ze5r46jl_j5l4w3wx4c5c3w2v1wa6h43m32vw2sdqd21cvw65"
)


# ═══════════════════════════════════════════════════════════════════════════════
# P  HYBRID MODE CONTRACT
# ═══════════════════════════════════════════════════════════════════════════════


class TestP_HybridContract:
    """Category P — Hybrid mode: access stateless, refresh stateful."""

    def test_p01_access_token_survives_logout(self):
        """
        KNOWN TRADE-OFF (hybrid mode) — Access tokens are stateless.

        After logout the access token remains valid until it expires.
        Impact: stolen access token window = up to ACCESS_TOKEN_EXPIRE_MINUTES.

        Remediation options:
          - Switch to TOKEN_MODE=stateful to blacklist access JTIs too.
          - Shorten ACCESS_TOKEN_EXPIRE_MINUTES.
          - Accept the trade-off and document for downstream consumers.
        """
        sess = fresh_login()

        r_before = requests.get(_ME, headers=sess["headers"], timeout=TIMEOUT)
        assert r_before.status_code == 200

        requests.post(
            f"{AUTH_BASE}/login/logout/",
            headers=sess["headers"],
            cookies=sess["cookies"],
            timeout=TIMEOUT,
        )

        r_after = requests.get(_ME, headers=sess["headers"], timeout=TIMEOUT)
        if r_after.status_code == 200:
            print(
                "\n[DESIGN-P01] Access token valid 0 s after logout (hybrid mode). "
                "Exposure window: up to ACCESS_TOKEN_EXPIRE_MINUTES."
            )
        # Both outcomes are valid depending on exact mode configuration.
        assert r_after.status_code in (200, 403), (
            f"Unexpected status {r_after.status_code} after logout in hybrid mode"
        )

    def test_p02_refresh_token_revoked_after_logout(self):
        """Logout must remove the refresh JTI from the Redis allowlist."""
        sess = fresh_login()
        requests.post(
            f"{AUTH_BASE}/login/logout/",
            headers=sess["headers"],
            cookies=sess["cookies"],
            timeout=TIMEOUT,
        )
        r = requests.post(_REFRESH_URL, cookies=sess["cookies"], timeout=TIMEOUT)
        assert r.status_code == 401, (
            f"[FINDING-P02] Refresh token not revoked after logout: {r.status_code}"
        )

    def test_p03_refresh_replay_detected(self):
        """Presenting a consumed refresh JTI must return 401."""
        sess = fresh_login()
        original_cookies = sess["cookies"]

        first = requests.post(_REFRESH_URL, cookies=original_cookies, timeout=TIMEOUT)
        assert first.status_code == 200

        replay = requests.post(_REFRESH_URL, cookies=original_cookies, timeout=TIMEOUT)
        assert replay.status_code == 401, (
            f"[FINDING-P03] Refresh replay not detected in hybrid mode: "
            f"{replay.status_code}"
        )

    def test_p04_refresh_rotation_issues_new_access_token(self):
        """Each refresh call must return a fresh, different access token."""
        sess = fresh_login()
        refresh = requests.post(_REFRESH_URL, cookies=sess["cookies"], timeout=TIMEOUT)
        assert refresh.status_code == 200
        assert refresh.json()["access_token"] != sess["token"]

    def test_p05_forged_refresh_with_committed_key_rejected_by_jti_check(self):
        """
        CRITICAL FINDING — REFRESH_SECRET_KEY committed to repository.

        Even though the signature is valid, the forged JTI is not in the
        Redis allowlist, so the token must be rejected.  This is the hybrid
        mode's primary mitigation against a compromised refresh secret.
        """
        forged = forge_hs256(_REFRESH_SECRET_KEY)
        r = requests.post(
            _REFRESH_URL, cookies={"refresh_token": forged}, timeout=TIMEOUT
        )
        assert r.status_code in (401, 404), (
            f"[CRITICAL-P05] Forged refresh token ACCEPTED in hybrid mode: "
            f"{r.status_code}. JTI allowlist check is not working."
        )

    def test_p06_tampered_refresh_cookie_rejected(self):
        """Modify the refresh cookie payload without re-signing — must fail."""
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
            from tests.live.suites.token_forge import b64url_nopad

            new_payload = b64url_nopad(json.dumps(claims).encode())
            tampered = f"{parts[0]}.{new_payload}.{parts[2]}"
        except (ValueError, KeyError):
            pytest.skip("Could not decode refresh token payload")

        r = requests.post(
            _REFRESH_URL, cookies={"refresh_token": tampered}, timeout=TIMEOUT
        )
        assert r.status_code == 401

    def test_p07_alg_none_in_access_position_rejected(self):
        """CRITICAL: alg=none must be rejected in hybrid mode as in any other."""
        r = requests.get(
            _ME,
            headers={"Authorization": f"Bearer {forge_alg_none()}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 403, (
            "[CRITICAL-P07] alg=none accepted in hybrid mode!"
        )

    def test_p08_missing_refresh_cookie_returns_401_or_422(self):
        r = requests.post(_REFRESH_URL, timeout=TIMEOUT)
        assert r.status_code in (401, 422)
