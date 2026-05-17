"""Token-crafting helpers for adversarial live tests.

All functions return raw JWT strings.  Algorithm-specific helpers
(RS256, ES256) require the corresponding PEM key material.
"""

import base64
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import jwt

_ACCESS_KEY_ID = "6dbedbd549ede665"


def b64url_nopad(data: bytes) -> str:
    """Base64url-encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def access_payload(
    *,
    is_superuser: bool = False,
    is_active: bool = True,
    email: str = "forged@evil.com",
    token_type: str = "access",
) -> dict:
    """Return a minimal but plausible access token payload."""
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


def forge_alg_none(is_superuser: bool = True) -> str:
    """Craft an unsigned JWT (alg=none) claiming arbitrary privileges."""
    header = b64url_nopad(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64url_nopad(
        json.dumps(access_payload(is_superuser=is_superuser)).encode()
    )
    return f"{header}.{payload}."


def forge_hs256_with_pubkey(public_key_pem: str) -> str:
    """Algorithm-confusion attack: sign payload with public key as HS256 secret.

    PyJWT refuses this, so we hand-craft the token at the raw HMAC level —
    exactly what a real attacker would do with a custom script.
    """
    header = b64url_nopad(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64url_nopad(json.dumps(access_payload(is_superuser=True)).encode())
    signing_input = f"{header}.{payload}".encode()
    sig = hmac.new(public_key_pem.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{b64url_nopad(sig)}"


def forge_rs256(
    private_key_pem: str,
    *,
    is_superuser: bool = True,
    token_type: str = "access",
    kid: str = _ACCESS_KEY_ID,
) -> str:
    """Forge a cryptographically valid RS256 token using the given private key."""
    return jwt.encode(
        access_payload(is_superuser=is_superuser, token_type=token_type),
        private_key_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


def forge_es256(
    private_key_pem: str,
    *,
    is_superuser: bool = True,
    token_type: str = "access",
    kid: str = _ACCESS_KEY_ID,
) -> str:
    """Forge a cryptographically valid ES256 token using the given EC private key."""
    return jwt.encode(
        access_payload(is_superuser=is_superuser, token_type=token_type),
        private_key_pem,
        algorithm="ES256",
        headers={"kid": kid},
    )


def forge_hs256(secret: str, *, sub: str | None = None) -> str:
    """Forge an HS256 refresh token signed with the given secret."""
    payload = {
        "sub": sub or str(uuid.uuid4()),
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    }
    return jwt.encode(payload, secret, algorithm="HS256")
