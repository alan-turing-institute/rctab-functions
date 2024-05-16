"""Configuration for the app."""
from functools import lru_cache
from typing import Optional

from pydantic import HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class Settings(BaseSettings):
    """A class to load and validate settings from the environment or a .env file."""

    API_URL: HttpUrl
    PRIVATE_KEY: str
    LOG_LEVEL: str = "WARNING"
    CENTRAL_LOGGING_CONNECTION_STRING: Optional[str]

    # Settings for the settings class itself.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("PRIVATE_KEY")
    def correct_start_and_end(cls, v: str) -> str:  # pylint: disable=no-self-argument
        """Validate a private key."""
        if not v.startswith("-----BEGIN OPENSSH PRIVATE KEY-----"):
            raise ValueError(
                'Expected key to start with "-----BEGIN OPENSSH PRIVATE KEY-----".'
            )

        if not v.endswith("-----END OPENSSH PRIVATE KEY-----") and not v.endswith(
            "-----END OPENSSH PRIVATE KEY-----\n"
        ):
            raise ValueError(
                'Expected key to end with "-----END OPENSSH PRIVATE KEY-----".'
            )
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get the global app settings object."""
    return Settings()  # type: ignore
