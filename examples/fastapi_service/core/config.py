"""
Configuration settings for the FastAPI application.
This module loads environment settings securely and applies best practices.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr, model_validator
from pydantic.networks import HttpUrl
from pydantic_settings import SettingsConfigDict

from auth_sdk_m8.core.config import CommonSettings, settings_customise_sources
from auth_sdk_m8.observability.settings import ObservabilitySettingsMixin
from auth_sdk_m8.schemas.shared import ValidationConstants
from auth_sdk_m8.utils.paths import find_dotenv

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
        settings_customise_sources=settings_customise_sources,  # type: ignore[typeddict-unknown-key]
    )

    # Extend validation lists
    required_fields = CommonSettings.required_fields + ["AUTH_PREFIX"]
    secret_fields = CommonSettings.secret_fields + ["PRIVATE_API_SECRET"]

    # Declare only service-specific fields
    AUTH_PREFIX: str = Field(
        ..., pattern=ValidationConstants.URL_PATH_STR_REGEX.pattern
    )
    TABLES_PREFIX: str = "app"

    # ── Revocation introspection (stateful consumer only) ─────────────────────
    # Required when AUTH_SERVICE_ROLE=consumer and TOKEN_MODE=stateful.
    # Set to the full URL of the auth service JTI status endpoint, e.g.:
    #   http://auth_user_service:8000/user/private/v1/jti-status
    INTROSPECTION_URL: Optional[HttpUrl] = None
    PRIVATE_API_SECRET: Optional[SecretStr] = None

    @model_validator(mode="after")
    def _require_introspection_for_stateful_consumer(self) -> "Settings":
        if self.AUTH_SERVICE_ROLE == "consumer" and self.is_stateful:
            missing: list[str] = []
            if self.INTROSPECTION_URL is None:
                missing.append("INTROSPECTION_URL")
            if (
                self.PRIVATE_API_SECRET is None
                or not self.PRIVATE_API_SECRET.get_secret_value()
            ):
                missing.append("PRIVATE_API_SECRET")
            if missing:
                raise ValueError(
                    f"AUTH_SERVICE_ROLE=consumer with TOKEN_MODE=stateful "
                    f"requires: {missing}"
                )
        return self


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
