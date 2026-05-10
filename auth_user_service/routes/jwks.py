"""JWKS endpoint — exposes the current public key set for RS256/ES256."""

import json
from typing import Any

from fastapi import APIRouter

from auth_sdk_m8.schemas.auth import ASYMMETRIC_ALGORITHMS
from auth_user_service.core.config import settings
from auth_user_service.services.auth import _resolve_kid

router = APIRouter(prefix="/.well-known", tags=["well-known"])


def _build_jwk(public_key_pem: str, algorithm: str, kid: str) -> dict[str, Any]:
    """Convert a PEM public key to a JWK dict with ``use``, ``alg``, and ``kid``."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from jwt.algorithms import ECAlgorithm, RSAAlgorithm

    key_obj = load_pem_public_key(public_key_pem.encode())
    alg_cls = ECAlgorithm if algorithm.startswith("ES") else RSAAlgorithm
    jwk: dict[str, Any] = json.loads(alg_cls.to_jwk(key_obj))
    jwk["use"] = "sig"
    jwk["alg"] = algorithm
    jwk["kid"] = kid
    return jwk


@router.get("/jwks.json", include_in_schema=True)
def jwks_endpoint() -> dict[str, Any]:
    """Return the active public key set in JWK Set format.

    Only meaningful when ``ACCESS_TOKEN_ALGORITHM`` is RS256 or ES256.
    Returns an empty key set for symmetric (HS256) configurations — the
    shared secret must never be published.

    Consumer services should point ``JWKS_URI`` at this endpoint and let
    ``build_access_validator`` wire up ``JwksKeyResolver`` automatically.
    """
    algo = settings.ACCESS_TOKEN_ALGORITHM
    if algo not in ASYMMETRIC_ALGORITHMS or not settings.ACCESS_PUBLIC_KEY:
        return {"keys": []}

    kid = _resolve_kid(algo) or ""
    jwk = _build_jwk(settings.ACCESS_PUBLIC_KEY, algo, kid)
    return {"keys": [jwk]}
