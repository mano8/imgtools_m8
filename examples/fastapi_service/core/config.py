"""
Configuration settings for the FastAPI application.
This module loads environment settings securely and applies best practices.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import SettingsConfigDict
from auth_sdk_m8.core.config import CommonSettings, settings_customise_sources
from auth_sdk_m8.schemas.shared import ValidationConstants
from auth_sdk_m8.utils.paths import find_dotenv
from auth_sdk_m8.observability.settings import ObservabilitySettingsMixin
# pylint: disable=invalid-name


class Settings(ObservabilitySettingsMixin, CommonSettings):
    """Settings for the fastapi_service: adds only new fields."""

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
    required_fields = CommonSettings.required_fields + ["AUTH_PREFIX"]
    secret_fields = CommonSettings.secret_fields
    # Declare only service-specific fields
    AUTH_PREFIX: str = Field(
        ..., pattern=ValidationConstants.URL_PATH_STR_REGEX.pattern
    )
    TABLES_PREFIX: str = "app"


try:
    settings = Settings()
except Exception as e:
    # Raise with a clear error message if validation fails.
    raise RuntimeError(f"Configuration validation error:\n {str(e)}") from e

if __name__ == "__main__":
    # For debugging, print out public settings without exposing secrets.
    public_settings = settings.model_dump()
    for field in settings.secret_fields:
        public_settings.pop(field, None)
    print(public_settings)
