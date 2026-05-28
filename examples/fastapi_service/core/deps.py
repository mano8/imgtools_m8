"""FastAPI authentication dependencies.

Provides token validation, current-user extraction, and role-based access
helpers for service routes.
"""

import logging
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.schemas.base import RoleType
from auth_sdk_m8.schemas.user import UserModel
from auth_sdk_m8.security import ValidationHooks, build_access_validator

from fastapi_service.core.config import settings
from fastapi_service.core.revocation import RemoteRevocationClient, RevocationCheckError

_logger = logging.getLogger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.AUTH_PREFIX}/login/access-token"
)
TokenDep = Annotated[str, Depends(reusable_oauth2)]


class _LoggingHooks:
    """Emit structured log lines for every token validation outcome."""

    def on_success(self, *, jti: str, sub: str, token_type: str) -> None:
        _logger.debug("token.valid type=%s sub=%s jti=%s", token_type, sub, jti)

    def on_failure(self, *, reason: str, token_type: str) -> None:
        _logger.warning("token.invalid type=%s reason=%s", token_type, reason)


_hooks: ValidationHooks = _LoggingHooks()

# Module-level validator — created once at startup, not per-request.
_validator = build_access_validator(settings, _hooks)

# Revocation client — created only for stateful consumers.
# INTROSPECTION_URL and PRIVATE_API_SECRET are guaranteed non-None by the
# _require_introspection_for_stateful_consumer validator when this branch runs.
_revocation_client: Optional[RemoteRevocationClient] = None
if settings.is_stateful and settings.AUTH_SERVICE_ROLE == "consumer":
    _revocation_client = RemoteRevocationClient(
        introspection_url=str(settings.INTROSPECTION_URL),  # type: ignore[arg-type]
        private_api_secret=settings.PRIVATE_API_SECRET.get_secret_value(),  # type: ignore[union-attr]
    )


async def get_current_user(token: TokenDep) -> UserModel:
    """Retrieve the current user from the JWT access token.

    Args:
        token: JWT string extracted from the Authorization header.

    Returns:
        Authenticated ``UserModel``.

    Raises:
        HTTPException 403: Token invalid, expired, revoked, or user inactive.
        HTTPException 503: Revocation check unavailable (fail-closed mode only).
    """
    try:
        payload = _validator.validate_access_token(token)
    except InvalidToken as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials.",
        ) from ex

    if _revocation_client is not None:
        try:
            if await _revocation_client.is_revoked(payload.jti):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token has been revoked.",
                )
        except RevocationCheckError as ex:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Token revocation check unavailable.",
            ) from ex

    payload_dict = payload.model_dump(exclude={"exp", "jti", "type", "sub"})
    payload_dict["id"] = payload.sub
    user = UserModel(**payload_dict)

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


CurrentUser = Annotated[UserModel, Depends(get_current_user)]


class UserRoleHelper:
    """Role-based access guard helpers."""

    @staticmethod
    def get_current_active_superuser(current_user: CurrentUser) -> UserModel:
        """Verify the current user holds SUPERADMIN role.

        Raises:
            HTTPException 403: Insufficient privileges.
        """
        if not current_user.is_superuser or not RoleType.is_valid_role_auth(
            current_role=current_user.role,
            role_limit=RoleType.SUPERADMIN,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges",
            )
        return current_user

    @staticmethod
    def get_current_active_admin(current_user: CurrentUser) -> UserModel:
        """Verify the current user holds at least ADMIN role.

        Raises:
            HTTPException 403: Insufficient privileges.
        """
        if not RoleType.is_valid_role_auth(
            current_role=current_user.role,
            role_limit=RoleType.ADMIN,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges",
            )
        return current_user
