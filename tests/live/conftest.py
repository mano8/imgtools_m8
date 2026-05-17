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
    pytest tests/live -m live_asymmetric          # asymmetric-specific tests
    pytest tests/live -m live_hs256               # HS256-specific tests
    pytest tests/live -m live_stateless           # stateless mode tests
    pytest tests/live -m live_hybrid              # hybrid mode tests
"""

import pathlib
import uuid
import warnings

import pytest
import requests
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurve

# ---------------------------------------------------------------------------
# Stack endpoints and test credentials (match compose stack defaults)
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
# Cryptographic key helpers
# ---------------------------------------------------------------------------


def _build_ec_curves() -> dict[str, EllipticCurve]:
    """Instantiate NIST curve objects.

    P-521/ES512 is uncommon in deployed stacks and has inconsistent support
    in some JWT libraries, but is included for completeness.
    secp256k1 is intentionally excluded — add only if a stack requires it.
    """
    from cryptography.hazmat.primitives.asymmetric import ec

    return {
        "P-256": ec.SECP256R1(),
        "P-384": ec.SECP384R1(),
        "P-521": ec.SECP521R1(),
    }


_EC_CURVES: dict[str, EllipticCurve] = _build_ec_curves()


def _jwk_to_public_key(jwk: dict):
    """Reconstruct a cryptography public key object from a JWK dict."""
    import base64

    from cryptography.hazmat.primitives.asymmetric import ec, rsa

    def _b64int(s: str) -> int:
        return int.from_bytes(base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)), "big")

    kty = jwk["kty"]
    if kty == "RSA":
        return rsa.RSAPublicNumbers(_b64int(jwk["e"]), _b64int(jwk["n"])).public_key()
    if kty == "EC":
        crv = jwk.get("crv", "")
        if crv not in _EC_CURVES:
            raise ValueError(
                f"Unsupported EC curve: {crv!r}. Supported: {list(_EC_CURVES)}"
            )
        return ec.EllipticCurvePublicNumbers(
            _b64int(jwk["x"]), _b64int(jwk["y"]), _EC_CURVES[crv]
        ).public_key()
    raise ValueError(f"Unsupported JWK kty: {kty!r}")


def _pub_der(key) -> bytes:
    """Return DER-encoded SubjectPublicKeyInfo bytes for canonical comparison."""
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    return key.public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)


def _find_committed_private_key(
    live_jwks: list[dict], repo_root: pathlib.Path
) -> "tuple[pathlib.Path, dict] | None":
    """Find a committed private key whose public key matches a live JWKS entry.

    Iterates every signing-capable JWK in the live JWKS set, reconstructs its
    DER public key, then scans the entire repo for private.pem/public.pem pairs
    whose public key has identical DER bytes.

    Returns (priv_path, matched_jwk) on first match, None otherwise.

    This models an attacker who: (1) fetches JWKS to identify the live signing
    key, (2) searches the git repository for committed private key material.
    It does NOT model filesystem traversal or container access.
    """
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    # Pre-compute DER for all committed key pairs once — avoids repeated PEM
    # parsing when iterating multiple JWK entries against the repo.
    committed: list[tuple[pathlib.Path, bytes]] = []
    for priv_path in repo_root.rglob("private.pem"):
        pub_path = priv_path.parent / "public.pem"
        if not pub_path.exists():
            continue
        try:
            committed.append(
                (priv_path, _pub_der(load_pem_public_key(pub_path.read_bytes())))
            )
        except Exception:
            continue  # malformed or unsupported key type — skip silently

    for jwk in live_jwks:
        if jwk.get("use", "sig") != "sig":
            continue  # skip encryption keys
        try:
            live_der = _pub_der(_jwk_to_public_key(jwk))
        except Exception:
            continue  # unsupported kty (e.g. OKP/EdDSA) — skip gracefully
        for priv_path, committed_der in committed:
            if committed_der == live_der:
                return priv_path, jwk

    return None


# ---------------------------------------------------------------------------
# Session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def stack_config() -> dict:
    """Detected algorithm and token_mode of the running compose stack."""
    return _detect_stack()


@pytest.fixture(scope="session")
def live_jwks_keys() -> list[dict]:
    """All JWKs from the running service's JWKS endpoint.

    Fetched once per session. Returns [] when JWKS is unavailable so
    downstream fixtures can emit targeted skips with context.
    """
    try:
        r = requests.get(_JWKS_URL, timeout=_DETECT_TIMEOUT)
        if r.status_code == 200:
            return r.json().get("keys", [])
    except requests.RequestException:
        pass
    return []


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


@pytest.fixture(scope="session")
def committed_key_forge(stack_config: dict, live_jwks_keys: list[dict]):
    """Callable that forges tokens using a private key committed to this
    repository that cryptographically matches the running stack's JWKS.

    Discovery flow (red-team realistic):
      1. Fetch live JWKS — public information, no auth needed
      2. For each signing-capable JWK: reconstruct public key as DER bytes
      3. Scan repo rglob for all private.pem/public.pem pairs
      4. Compare DER bytes — find the committed key matching the live key
      5. Extract kid and alg from the matched JWK (authoritative source)

    Skips when:
      - Stack uses a symmetric algorithm (HS256) — different attack surface
      - JWKS is unavailable
      - No committed key matches any live JWKS key (key was rotated or
        managed externally — this is the secure/remediated posture)

    Passes (test documents CRITICAL FINDING) when:
      - A committed private key matches the live JWKS public key
      - Forged token carries the correct kid and algorithm
    """
    from tests.live.suites.token_forge import forge_asymmetric

    detected_alg = stack_config.get("algorithm", "HS256")
    if not detected_alg.startswith(("RS", "ES")):
        pytest.skip(f"committed_key_forge: symmetric stack ({detected_alg!r})")

    if not live_jwks_keys:
        pytest.skip("committed_key_forge: JWKS unavailable or empty")

    repo_root = pathlib.Path(__file__).resolve().parents[2]
    result = _find_committed_private_key(live_jwks_keys, repo_root)
    if result is None:
        pytest.skip(
            "committed_key_forge: no committed private key matches any live JWKS key"
            " — key was rotated or this stack uses externally managed keys"
        )

    priv_path, matched_jwk = result
    live_kid = matched_jwk.get("kid")
    live_alg = matched_jwk.get("alg", detected_alg)  # JWKS is authoritative

    if live_alg != detected_alg:
        warnings.warn(
            f"Stack health reports algorithm={detected_alg!r} but matched JWKS key"
            f" has alg={live_alg!r} — using JWKS value",
            stacklevel=2,
        )

    key_pem = priv_path.read_text()

    def _forge(**kw) -> str:
        kw.setdefault("kid", live_kid)
        return forge_asymmetric(key_pem, live_alg, **kw)

    return _forge


@pytest.fixture(scope="session")
def public_key_pem(stack_config: dict, live_jwks_keys: list[dict]) -> str:
    """Public key PEM reconstructed directly from JWKS.

    Available to any network attacker — no repo access required.
    Used for algorithm-confusion (asymmetric→HS256) attacks.

    Selects the first signing-capable key whose algorithm matches the
    detected stack algorithm. The alg filter prevents nondeterministic
    key selection in mixed-algorithm JWKS sets (rollover deployments).
    """
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    alg = stack_config.get("algorithm", "HS256")
    if not alg.startswith(("RS", "ES")):
        pytest.skip(f"public_key_pem: symmetric stack ({alg!r})")
    if not live_jwks_keys:
        pytest.skip("public_key_pem: JWKS unavailable or empty")

    signing_jwk = next(
        (
            k
            for k in live_jwks_keys
            if k.get("kty") in {"RSA", "EC"}
            and k.get("use", "sig") == "sig"
            and k.get("alg", alg) == alg
        ),
        None,
    )
    if signing_jwk is None:
        pytest.skip(f"public_key_pem: no signing key with alg={alg!r} found in JWKS")

    try:
        pub = _jwk_to_public_key(signing_jwk)
        return pub.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo
        ).decode()
    except Exception as exc:
        pytest.skip(f"public_key_pem: key reconstruction failed — {exc}")


@pytest.fixture(scope="session")
def asymmetric_key_pem(
    stack_config: dict, live_jwks_keys: list[dict]
) -> "tuple[str, str, str | None]":
    """Return (private_key_pem, alg, kid_or_None) for rejection-path tests.

    Preference order:
      1. Committed key matching live JWKS — server validates the signature
         fully, so the specific flaw under test (expired, wrong type, etc.)
         is actually reached and exercised.
      2. Ephemeral freshly-generated key — server rejects at key identity
         (unknown kid) before reaching the intended flaw. The 403 assertion
         still holds but the specific flaw is not exercised. Docstrings on
         affected tests call this out explicitly.

    kid is None in the ephemeral case; tests should substitute "unknown".
    """
    alg = stack_config.get("algorithm", "HS256")
    if not alg.startswith(("RS", "ES")):
        pytest.skip(f"asymmetric_key_pem: symmetric stack ({alg!r})")

    if live_jwks_keys:
        repo_root = pathlib.Path(__file__).resolve().parents[2]
        result = _find_committed_private_key(live_jwks_keys, repo_root)
        if result is not None:
            priv_path, matched_jwk = result
            return (
                priv_path.read_text(),
                matched_jwk.get("alg", alg),
                matched_jwk.get("kid"),
            )

    # Ephemeral fallback — kid will be unknown to the server
    from cryptography.hazmat.primitives import serialization

    if alg.startswith("RS"):
        from cryptography.hazmat.primitives.asymmetric import rsa

        k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    else:
        from cryptography.hazmat.primitives.asymmetric import ec

        k = ec.generate_private_key(ec.SECP256R1())

    pem = k.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    ).decode()
    return pem, alg, None


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
                        f"Stack runs {alg!r}; test requires one of {alg_marker.args}"
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
