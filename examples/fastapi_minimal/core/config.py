"""Service settings for the minimal example."""

from pathlib import Path

from pydantic_settings import SettingsConfigDict

from auth_sdk_m8.utils.paths import find_dotenv
from fastapi_m8 import ConsumerServiceSettings


class Settings(ConsumerServiceSettings):
    """Minimal consumer settings — no extra fields beyond the base class."""

    ENV_FILE_DIR: Path = Path(__file__).resolve().parent.parent

    model_config = SettingsConfigDict(
        env_file=find_dotenv(Path(__file__).resolve().parent.parent),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )


settings = Settings()
