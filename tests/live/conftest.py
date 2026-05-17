"""
Conftest for live integration tests.

Probes the running stack's health and JWKS endpoints to detect the active
algorithm and token_mode.  Tests decorated with @pytest.mark.require_algorithm
or @pytest.mark.require_token_mode are auto-skipped when the detected config
does not match, so users can run the full live suite against their own stack
and only the relevant tests execute.

Usage examples
--------------
    pytest tests/live -m live_security            # universal tests, any stack
    pytest tests/live -m live_rs256               # RS256-specific tests
    pytest tests/live -m "live_rs256 or live_stateful or live_security"
    pytest tests/live -m live_hs256               # HS256-specific tests
    pytest tests/live -m live_stateless           # stateless mode tests
    pytest tests/live -m live_hybrid              # hybrid mode tests
"""

import uuid

import pytest
import requests

# ---------------------------------------------------------------------------
# Stack endpoints and test credentials (match RS256_m8 / stateful_m8 defaults)
# ---------------------------------------------------------------------------

AUTH_BASE = "http://localhost:9000/user"
SVC_BASE = "http://localhost:9000/fastapi"
TIMEOUT = 10

_ADMIN_EMAIL = "admin@example.com"
_ADMIN_PASSWORD = "Ocoti123@#@"

_HEALTH_URL = f"{AUTH_BASE}/health/"
_JWKS_URL = f"{AUTH_BASE}/.well-known/jwks.json"
_DETECT_TIMEOUT = 5


# ---------------------------------------------------------------------------
# Stack detection
# ---------------------------------------------------------------------------


def _detect_stack() -> dict:
    """Return detected stack config, or empty dict when stack is unreachable."""
    try:
        r = requests.get(_HEALTH_URL, timeout=_DETECT_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException:
        return {}

    cfg: dict = {
        "reachable": True,
        "algorithm": "HS256",
        "token_mode": "stateful",
        "has_jwks": False,
    }

    try:
        body = r.json()
        if "token_mode" in body:
            cfg["token_mode"] = body["token_mode"]
    except (ValueError, KeyError):
        pass

    try:
        jwks = requests.get(_JWKS_URL, timeout=_DETECT_TIMEOUT)
        if jwks.status_code == 200:
            keys = jwks.json().get("keys", [])
            if keys:
                cfg["algorithm"] = keys[0].get("alg", "RS256")
                cfg["has_jwks"] = True
    except (requests.RequestException, ValueError, KeyError):
        pass

    return cfg


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def stack_config() -> dict:
    """Detected algorithm and token_mode of the running compose stack."""
    return _detect_stack()


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
def admin_headers(admin_token: str) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def admin_login() -> dict:
    """Full login response — access token + cookies."""
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
        "headers": {"Authorization": f"Bearer {body['access_token']}"},
    }


@pytest.fixture(scope="session")
def regular_user(admin_headers: dict) -> dict:
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
        "headers": {"Authorization": f"Bearer {token}"},
    }


# Asymmetric key fixtures — only requested by tests that need them, so
# they won't fail when running against an HS256 stack.

_RS256_STACK_DIRS = [
    "examples/docker_compose/vault_rs256_postgres_m8/keys",
    "examples/docker_compose/RS256_m8/keys",
    "examples/docker_compose/lite_rs256_m8/keys",
]
_ES256_STACK_DIRS = [
    "examples/docker_compose/lite_es256_m8/keys",
    "examples/docker_compose/lite_hybrid_m8/keys",
]


def _find_key(filename: str) -> "Path":
    """Return the first existing RSA key file across known RS256 compose stacks."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    for rel in _RS256_STACK_DIRS:
        p = repo_root / rel / filename
        if p.exists():
            return p
    raise AssertionError(
        f"RSA key '{filename}' not found in any known RS256 stack directory.\n"
        "Generate keys by running: bash init.sh  (from the stack directory)"
    )


def _find_key_for_algorithm(filename: str, algorithm: str) -> "Path":
    """Return the first existing key file for the given algorithm family."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    dirs = _RS256_STACK_DIRS if algorithm.startswith("RS") else _ES256_STACK_DIRS
    for rel in dirs:
        p = repo_root / rel / filename
        if p.exists():
            return p
    raise AssertionError(
        f"{algorithm} key '{filename}' not found in any known stack directory.\n"
        "Generate keys by running: bash init.sh  (from the stack directory)"
    )


@pytest.fixture(scope="session")
def private_key_pem() -> str:
    return _find_key("private.pem").read_text()


@pytest.fixture(scope="session")
def public_key_pem() -> str:
    return _find_key("public.pem").read_text()


@pytest.fixture(scope="session")
def committed_key_forge(stack_config: dict):
    """Callable that forges tokens with the key committed to the repo for the
    running stack's algorithm — simulates an attacker who read the repo.

    Fetches the live kid from JWKS so the token header matches what the stack
    expects, making the forgery cryptographically indistinguishable from a
    legitimately issued token (if the key is the correct one).
    """
    from tests.live.suites.token_forge import forge_es256, forge_rs256

    alg = stack_config.get("algorithm", "RS256")
    if alg.startswith("RS"):
        forge_fn = forge_rs256
    elif alg.startswith("ES"):
        forge_fn = forge_es256
    else:
        pytest.skip(f"No committed-key forge for symmetric algorithm {alg}")

    try:
        key_pem = _find_key_for_algorithm("private.pem", alg).read_text()
    except AssertionError as exc:
        pytest.skip(str(exc))

    kid: str | None = None
    try:
        jwks = requests.get(_JWKS_URL, timeout=_DETECT_TIMEOUT)
        kid = jwks.json()["keys"][0]["kid"]
    except Exception:
        pass

    def _forge(**kw) -> str:
        if kid:
            kw.setdefault("kid", kid)
        return forge_fn(key_pem, **kw)

    return _forge


# ---------------------------------------------------------------------------
# Collection hook — skip tests whose requirements don't match the live stack
# ---------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items: list) -> None:  # noqa: ARG001
    """Skip live tests whose algorithm/mode requirements don't match the stack."""
    detected = _detect_stack()

    if not detected.get("reachable"):
        skip = pytest.mark.skip(
            reason="Live stack not reachable — start a compose stack first"
        )
        for item in items:
            if "live" in item.keywords:
                item.add_marker(skip)
        return

    alg = detected.get("algorithm", "HS256")
    mode = detected.get("token_mode", "stateful")

    for item in items:
        alg_marker = item.get_closest_marker("require_algorithm")
        if alg_marker and alg not in alg_marker.args:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        f"Stack runs {alg!r}; "
                        f"test requires one of {alg_marker.args}"
                    )
                )
            )
            continue

        mode_marker = item.get_closest_marker("require_token_mode")
        if mode_marker and mode not in mode_marker.args:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        f"Stack token_mode is {mode!r}; "
                        f"test requires one of {mode_marker.args}"
                    )
                )
            )
