"""Security regression: _client_ip() must read X-Forwarded-For from trusted proxy.

Verifies that:
- X-Forwarded-For single IP is returned directly
- X-Forwarded-For chain returns only the leftmost (real client) IP
- Fallback to request.client.host when header is absent
- Fallback to "unknown" when both header and request.client are absent
- Whitespace around IPs in the chain is stripped
- Port suffixes are stripped before IP validation (IPv4:port and [IPv6]:port)
- TRUSTED_PROXY_COUNT=0 bypasses XFF entirely
"""

from unittest.mock import MagicMock, patch

from auth_user_service.routes import login as login_mod
from auth_user_service.routes.login import _client_ip, _strip_port


def _make_request(
    xff: str | None = None, client_host: str | None = "10.0.0.1"
) -> MagicMock:
    request = MagicMock()
    request.headers.get.return_value = xff
    if client_host is None:
        request.client = None
    else:
        request.client.host = client_host
    return request


def test_xff_single_ip_returned():
    req = _make_request(xff="203.0.113.5")
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 1):
        assert _client_ip(req) == "203.0.113.5"


def test_xff_chain_returns_leftmost_ip():
    """The leftmost IP in the chain is the original client; others are proxies."""
    req = _make_request(xff="203.0.113.5, 10.0.0.1, 172.17.0.2")
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 1):
        assert _client_ip(req) == "203.0.113.5"


def test_xff_chain_strips_whitespace():
    req = _make_request(xff="  203.0.113.99  , 10.0.0.1")
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 1):
        assert _client_ip(req) == "203.0.113.99"


def test_no_xff_falls_back_to_client_host():
    req = _make_request(xff=None, client_host="192.168.1.1")
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 1):
        assert _client_ip(req) == "192.168.1.1"


def test_no_xff_no_client_returns_unknown():
    req = _make_request(xff=None, client_host=None)
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 1):
        assert _client_ip(req) == "unknown"


def test_empty_xff_falls_back_to_client_host():
    """An empty string header must not be returned — treat as absent."""
    req = _make_request(xff="", client_host="192.168.1.2")
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 1):
        assert _client_ip(req) == "192.168.1.2"


def test_xff_garbage_falls_back_to_client_host():
    """Unparseable XFF entry falls back to request.client.host."""
    req = _make_request(xff="not-an-ip", client_host="192.168.1.3")
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 1):
        assert _client_ip(req) == "192.168.1.3"


def test_xff_ipv4_with_port_stripped():
    """IPv4:port format in XFF — port is stripped before validation."""
    req = _make_request(xff="192.0.2.1:45231", client_host="fallback")
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 1):
        assert _client_ip(req) == "192.0.2.1"


def test_xff_ipv6_bracketed_port_stripped():
    """[IPv6]:port format in XFF — brackets and port stripped before validation."""
    req = _make_request(xff="[2001:db8::1]:8080", client_host="fallback")
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 1):
        assert _client_ip(req) == "2001:db8::1"


def test_trusted_proxy_count_zero_ignores_xff():
    """TRUSTED_PROXY_COUNT=0 skips XFF entirely and returns request.client.host."""
    from auth_user_service.routes import login as login_mod

    req = _make_request(xff="1.2.3.4", client_host="10.10.10.10")
    with patch.object(login_mod.settings, "TRUSTED_PROXY_COUNT", 0):
        assert _client_ip(req) == "10.10.10.10"


# ── _strip_port unit tests ────────────────────────────────────────────────────


def test_strip_port_plain_ipv4():
    assert _strip_port("192.0.2.1") == "192.0.2.1"


def test_strip_port_ipv4_with_port():
    assert _strip_port("192.0.2.1:45231") == "192.0.2.1"


def test_strip_port_bracketed_ipv6():
    assert _strip_port("[2001:db8::1]:8080") == "2001:db8::1"


def test_strip_port_pure_ipv6_unchanged():
    """Pure IPv6 (no brackets, no port) must be returned unchanged."""
    assert _strip_port("2001:db8::1") == "2001:db8::1"
