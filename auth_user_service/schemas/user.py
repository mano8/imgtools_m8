"""
User models
"""


from pydantic import BaseModel

from auth_user_service.db_models.users import UserPublic


class OAuthGoogleToken(BaseModel):
    """
    Public item model for API responses.

    Inherits from ResponseModelBase and adds id and owner_id fields.
    """
    access_token: str
    expires_in: int
    refresh_token: str

class ResponseUploadedAvatar(BaseModel):
    """
    Public item model for API responses.

    Inherits from ResponseModelBase and adds id and owner_id fields.
    """
    success: bool
    msg: str
    avatar: str


class ResponseUser(BaseModel):
    """
    Public item model for API responses.

    Inherits from ResponseModelBase and adds id and owner_id fields.
    """
    success: bool
    user: UserPublic
