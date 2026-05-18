"""Shared auth-flow helpers for live test modules."""

import requests

AUTH_BASE = "http://localhost:9000/user"
SVC_BASE = "http://localhost:9000/fastapi"
TIMEOUT = 10

_ADMIN_EMAIL = "admin@example.com"
_ADMIN_PASSWORD = "Ocoti123@#@"


def auth_header(bearer: str) -> dict:
    """Return an Authorization header dict for the given bearer token."""
    return {"Authorization": f"Bearer {bearer}"}


def fresh_login(
    email: str = _ADMIN_EMAIL,
    password: str = _ADMIN_PASSWORD,
) -> dict:
    """Perform a fresh login and return token + cookies."""
    r = requests.post(
        f"{AUTH_BASE}/login/access-token",
        data={"username": email, "password": password},
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"Login failed for {email}: {r.text}"
    return {
        "token": r.json()["access_token"],
        "cookies": dict(r.cookies),
        "headers": auth_header(r.json()["access_token"]),
    }
