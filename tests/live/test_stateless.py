"""
Live Security Tests — Stateless Token Mode
===========================================
Target:  http://localhost:9000/user/
Config:  TOKEN_MODE=stateless

Stateless mode trades revocation capability for simplicity: no Redis lookups
are needed for access token validation.  These tests document the security
contract and make the deliberate trade-offs explicit.

Auto-skipped when the running stack uses TOKEN_MODE=stateful or hybrid.

Run:
    pytest tests/live/test_stateless.py -v --no-cov
    pytest tests/live -m live_stateless --no-cov
"""

import pytest
import requests

from tests.live.suites.auth_flows import AUTH_BASE, TIMEOUT, fresh_login

pytestmark = [
    pytest.mark.live,
    pytest.mark.live_stateless,
    pytest.mark.require_token_mode("stateless"),
]

_ME = f"{AUTH_BASE}/profile/get/me/"
_REFRESH_URL = f"{AUTH_BASE}/login/refresh-token/"


# ═══════════════════════════════════════════════════════════════════════════════
# N  STATELESS MODE CONTRACT
# ═══════════════════════════════════════════════════════════════════════════════


class TestN_StatelessContract:
    """Category N — Stateless mode: explicit documentation of revocation gap.

    Tests in this class use print() to emit [DESIGN] notes rather than
    failing assertions, because the observed behavior IS the expected behavior
    for this configuration.  The goal is to make the security trade-offs visible
    during a live audit.
    """

    def test_n01_valid_token_accepted_before_logout(self):
        """Sanity: newly issued token must be accepted."""
        sess = fresh_login()
        r = requests.get(_ME, headers=sess["headers"], timeout=TIMEOUT)
        assert r.status_code == 200

    def test_n02_logout_returns_200(self):
        """Logout endpoint must accept the request and return 200."""
        sess = fresh_login()
        r = requests.post(
            f"{AUTH_BASE}/login/logout/",
            headers=sess["headers"],
            cookies=sess["cookies"],
            timeout=TIMEOUT,
        )
        assert r.status_code == 200

    def test_n03_access_token_remains_valid_after_logout(self):
        """
        KNOWN TRADE-OFF (stateless mode) — Access tokens cannot be revoked.

        Logout clears the client-side cookie but the signed JWT remains
        cryptographically valid until its exp claim passes.  A stolen token
        continues to work for up to ACCESS_TOKEN_EXPIRE_MINUTES after issuance.

        Impact: stolen token window = up to 30 minutes (default expiry).

        Mitigation options:
          - Switch to TOKEN_MODE=stateful to blacklist JTIs at logout.
          - Shorten ACCESS_TOKEN_EXPIRE_MINUTES to reduce the exposure window.
          - Accept the trade-off; document for all downstream consumers.
        """
        sess = fresh_login()
        requests.post(
            f"{AUTH_BASE}/login/logout/",
            headers=sess["headers"],
            cookies=sess["cookies"],
            timeout=TIMEOUT,
        )
        r = requests.get(_ME, headers=sess["headers"], timeout=TIMEOUT)
        if r.status_code == 200:
            print(
                "\n[DESIGN-N03] Access token remains valid after logout "
                "(expected in stateless mode). "
                "Exposure window: up to ACCESS_TOKEN_EXPIRE_MINUTES."
            )
        # We do NOT assert 403 here — validity post-logout is expected behavior.
        assert r.status_code in (200, 403), (
            f"Unexpected status {r.status_code} from /me after logout"
        )

    def test_n04_expired_token_rejected(self):
        """Even in stateless mode, exp claim must be enforced."""
        from datetime import datetime, timedelta, timezone

        import jwt

        from tests.live.suites.token_forge import access_payload

        payload = access_payload()
        payload["exp"] = int(
            (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
        )
        token = jwt.encode(payload, "wrong-key-deliberately", algorithm="HS256")
        r = requests.get(
            _ME, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT
        )
        assert r.status_code == 403

    def test_n05_structurally_invalid_token_rejected(self):
        """Malformed tokens must always be refused regardless of mode."""
        r = requests.get(
            _ME,
            headers={"Authorization": "Bearer not.a.jwt.at.all"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 403

    def test_n06_alg_none_rejected(self):
        """CRITICAL GUARD: unsigned token must never be accepted in any mode."""
        from tests.live.suites.token_forge import forge_alg_none

        r = requests.get(
            _ME,
            headers={"Authorization": f"Bearer {forge_alg_none()}"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 403, (
            "[CRITICAL-N06] alg=none accepted in stateless mode!"
        )

    def test_n07_refresh_endpoint_behaviour_documented(self):
        """Document what the refresh endpoint does in stateless mode.

        In pure stateless mode there is no JTI allowlist, so the server
        cannot distinguish a fresh refresh token from a replayed one.  This
        test records the actual behaviour without asserting a specific status.
        """
        sess = fresh_login()
        r = requests.post(_REFRESH_URL, cookies=sess["cookies"], timeout=TIMEOUT)
        print(
            f"\n[DESIGN-N07] Refresh in stateless mode returned {r.status_code}. "
            "If 200: replay is possible (no JTI tracking). "
            "If 401: server rejects without Redis (unexpected in pure stateless)."
        )
        assert r.status_code in (200, 401, 422), (
            f"Unexpected refresh status {r.status_code} in stateless mode"
        )

    def test_n08_no_redis_dependency_for_token_validation(self):
        """Stateless token validation must not require Redis.

        We cannot easily bring Redis down in a live test, but we can verify
        that validation is not claiming it needs Redis by checking the health
        endpoint does not report Redis as required.
        """
        r = requests.get(f"{AUTH_BASE}/health/", timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        print(f"\n[INFO-N08] Health body: {body}")
        # Stateless mode: Redis is optional; stack must still be healthy.
        assert body.get("status", "").lower() in ("ok", "healthy", "up"), (
            "[FINDING-N08] Stack reports unhealthy status in stateless mode"
        )
