"""Service settings for fastapi_full.

Extends ConsumerServiceSettings with service-specific fields only.
ConsumerAuthMixin, ObservabilitySettingsMixin, and CommonSettings are
all inherited via the base class.
"""

from pathlib import Path

from auth_sdk_m8.core.config import settings_customise_sources
from auth_sdk_m8.utils.paths import find_dotenv
from fastapi_m8 import ConsumerServiceSettings
from pydantic_settings import SettingsConfigDict


class Settings(ConsumerServiceSettings):
    """fastapi_full settings — inherits all consumer fields from fastapi-m8."""

    ENV_FILE_DIR: Path = Path(__file__).resolve().parent.parent

    model_config = SettingsConfigDict(
        env_file=find_dotenv(Path(__file__).resolve().parent.parent),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="forbid",
        settings_customise_sources=settings_customise_sources,  # type: ignore[typeddict-unknown-key]
    )


try:
    settings = Settings()
except Exception as exc:
    raise RuntimeError(f"Configuration validation error:\n {exc}") from exc
