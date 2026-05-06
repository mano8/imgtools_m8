"""FastAPI authentication dependencies.

Provides token validation, current-user extraction, and role-based access
helpers for service routes.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from pydantic import SecretStr
from redis import Redis

from auth_sdk_m8.core.exceptions import InvalidToken
from auth_sdk_m8.schemas.auth import TokenSecret
from auth_sdk_m8.schemas.base import RoleType
from auth_sdk_m8.schemas.user import UserModel
from auth_sdk_m8.security import TokenValidationConfig, TokenValidator

from fastapi_service.core.config import settings

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.AUTH_PREFIX}/login/access-token"
)
TokenDep = Annotated[str, Depends(reusable_oauth2)]


def get_validator() -> TokenValidator:
    """Build the access-token validator from service settings.

    Creating the validator per-request is cheap (pure in-memory object).
    For high-throughput services, cache this at module level or inject it
    via a lifespan-scoped dependency.
    """
    return TokenValidator(
        secrets=TokenSecret(
            secret_key=SecretStr(settings.ACCESS_SECRET_KEY),
            algorithm=settings.TOKEN_ALGORITHM,
        ),
        config=TokenValidationConfig(),
    )


ValidatorDep = Annotated[TokenValidator, Depends(get_validator)]


def get_current_user(token: TokenDep, validator: ValidatorDep) -> UserModel:
    """Retrieve the current user from the JWT access token.

    Args:
        token: JWT string extracted from the Authorization header.
        validator: Pre-configured ``TokenValidator`` instance.

    Returns:
        Authenticated ``UserModel``.

    Raises:
        HTTPException 403: Token invalid, expired, or user inactive.
    """
    try:
        payload = validator.validate_access_token(token)
    except InvalidToken as ex:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials.",
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


def get_templates() -> Jinja2Templates:
    """Return the Jinja2 template engine bound to the configured directory."""
    return Jinja2Templates(directory=settings.TEMPLATES_BASE_PATH)


def get_redis_client() -> Redis:
    """Create a Redis connection from service settings."""
    return Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        username=settings.REDIS_USER,
        password=settings.REDIS_PASSWORD.get_secret_value() or None,
        encoding="utf-8",
        decode_responses=True,
    )
