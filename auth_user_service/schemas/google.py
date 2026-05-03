"""Google OAuth token schemas"""
from pydantic import BaseModel


class OAuthGoogleToken(BaseModel):
    """
    Schema for Google OAuth token response data.
    """
    access_token: str
    expires_in: int
    refresh_token: str
    user_id: str
    email: str
    email_verified: bool
    name: str
    picture: str
