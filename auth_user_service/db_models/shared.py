"""
Shared models and enums for the application.
"""

from sqlmodel import Field, SQLModel


# ---------------------------------------------------------------
# ---------------------------------------------------------------
# ------- Token
# ---------------------------------------------------------------
# ---------------------------------------------------------------
class NewPassword(SQLModel):
    """
    Model for resetting a user's password.

    Attributes:
        token (str): Reset token sent to user.
        new_password (str): New password to set.
    """

    token: str = Field(
        description="Password reset token",
    )
    new_password: str = Field(
        min_length=8,
        max_length=128,
        description="New password string",
    )
