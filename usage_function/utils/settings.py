"""Configuration for the app."""

from functools import lru_cache
from typing import Optional

from pydantic import HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """A class to load and validate settings from the environment or a .env file."""

    API_URL: HttpUrl  # e.g. https://my.rctab.host
    PRIVATE_KEY: str  # The private part of an RSA key pair
    USAGE_HISTORY_DAYS: int = 3  # The number of days' history to collect...
    USAGE_HISTORY_DAYS_OFFSET: int = 0  # ...starting from this many days ago
    LOG_LEVEL: str = "WARNING"  # The log level
    CM_MGMT_GROUP: Optional[str] = None  # The cost management function mgmt group
    BILLING_ACCOUNT_ID: str
    BILLING_PROFILE_ID: Optional[str] = (
        None  # To restrict to a particular billing profile.
    )
    CENTRAL_LOGGING_CONNECTION_STRING: Optional[str] = None

    # Settings for the settings class itself.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def correct_start_and_end(cls, v: str) -> str:  # pylint: disable=no-self-argument
        """Validate the private key.

        Args:
            v: The private key to validate.
        """
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
    """Get the global settings for the app."""
    return Settings()  # type: ignore
