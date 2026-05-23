"""
User models
"""

from pydantic import BaseModel

from auth_user_service.db_models.users import UserPublic


class OAuthGoogleToken(BaseModel):
    """Token response for Google OAuth flow."""

    access_token: str
    expires_in: int
    refresh_token: str


class ResponseUser(BaseModel):
    """Wraps a UserPublic payload with a success flag."""

    success: bool
    user: UserPublic
