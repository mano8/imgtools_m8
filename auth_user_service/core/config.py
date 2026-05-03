"""
Configuration settings for the FastAPI application.
This module loads environment settings securely and applies best practices.
"""
from pathlib import Path
from pydantic import (
    EmailStr,
    SecretStr
)
from pydantic_settings import SettingsConfigDict
from auth_sdk_m8.utils.paths import find_dotenv
from auth_sdk_m8.core.config import CommonSettings, settings_customise_sources
# pylint: disable=invalid-name, import-outside-toplevel


class Settings(CommonSettings):
    """Settings for the auth_user_service: adds only new fields."""

    # Override env file directory if necessary
    ENV_FILE_DIR = Path(__file__).resolve().parent

    # Pydantic v2 config must be a plain class attribute (no annotation)
    model_config = SettingsConfigDict(
        env_file=find_dotenv(ENV_FILE_DIR),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="forbid",
        settings_customise_sources=settings_customise_sources,
    )

    # Extend validation lists
    required_fields = CommonSettings.required_fields
    secret_fields = CommonSettings.secret_fields + [
        "FIRST_SUPERUSER", "FIRST_SUPERUSER_PASSWORD",
        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET",
        "PRIVATE_API_SECRET", "TOKENS_ENCRYPTION_KEY",
    ]
    passwords = CommonSettings.passwords + [
        "FIRST_SUPERUSER_PASSWORD"
    ]
    secret_keys = CommonSettings.secret_keys + [
        "PRIVATE_API_SECRET", "TOKENS_ENCRYPTION_KEY",
    ]
    TABLES_PREFIX: str = "auth"
    # Declare only service-specific fields
    FIRST_SUPERUSER: EmailStr
    FIRST_SUPERUSER_PASSWORD: SecretStr
    GOOGLE_CLIENT_ID: SecretStr
    GOOGLE_CLIENT_SECRET: SecretStr
    PRIVATE_API_SECRET: SecretStr
    TOKENS_ENCRYPTION_KEY: SecretStr


try:
    settings = Settings()
except Exception as e:
    # Raise with a clear error message if validation fails.
    raise RuntimeError(
        f"Configuration validation error:\n {str(e)}") from e

if __name__ == "__main__":
    # For debugging, print out public settings without exposing secrets.
    public_settings = settings.model_dump()
    for field in settings.secret_fields:
        public_settings.pop(field, None)
    print(public_settings)
