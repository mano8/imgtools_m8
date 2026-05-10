"""Security regression: _client_ip() must read X-Forwarded-For from trusted proxy.

Verifies that:
- X-Forwarded-For single IP is returned directly
- X-Forwarded-For chain returns only the leftmost (real client) IP
- Fallback to request.client.host when header is absent
- Fallback to "unknown" when both header and request.client are absent
- Whitespace around IPs in the chain is stripped
"""

from unittest.mock import MagicMock

from auth_user_service.routes.login import _client_ip


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
    assert _client_ip(req) == "203.0.113.5"


def test_xff_chain_returns_leftmost_ip():
    """The leftmost IP in the chain is the original client; others are proxies."""
    req = _make_request(xff="203.0.113.5, 10.0.0.1, 172.17.0.2")
    assert _client_ip(req) == "203.0.113.5"


def test_xff_chain_strips_whitespace():
    req = _make_request(xff="  203.0.113.99  , 10.0.0.1")
    assert _client_ip(req) == "203.0.113.99"


def test_no_xff_falls_back_to_client_host():
    req = _make_request(xff=None, client_host="192.168.1.1")
    assert _client_ip(req) == "192.168.1.1"


def test_no_xff_no_client_returns_unknown():
    req = _make_request(xff=None, client_host=None)
    assert _client_ip(req) == "unknown"


def test_empty_xff_falls_back_to_client_host():
    """An empty string header must not be returned — treat as absent."""
    req = _make_request(xff="", client_host="192.168.1.2")
    assert _client_ip(req) == "192.168.1.2"
