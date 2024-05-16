"""Configuration for the app."""
from functools import lru_cache
from typing import Optional

from pydantic import HttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self


class Settings(BaseSettings):
    """A class to load and validate settings from the environment or a .env file."""

    API_URL: HttpUrl  # e.g. https://my.rctab.host
    PRIVATE_KEY: str  # The private part of an RSA key pair
    USAGE_HISTORY_DAYS: int = 3  # The number of days' history to collect...
    USAGE_HISTORY_DAYS_OFFSET: int = 0  # ...starting from this many days ago
    LOG_LEVEL: str = "WARNING"  # The log level
    CM_MGMT_GROUP: Optional[str] = None  # The cost management function mgmt group
    MGMT_GROUP: Optional[str] = None  # Either, the usage function mgmt group...
    BILLING_ACCOUNT_ID: Optional[
        str
    ] = None  # ...or the usage function billing account ID
    CENTRAL_LOGGING_CONNECTION_STRING: Optional[str] = None

    # Settings for the settings class itself.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("PRIVATE_KEY")
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

    @model_validator(mode="after")
    def mgmt_group_or_billing_id(self) -> Self:
        """Require either a mgmt group name or a billing account ID."""
        if (
            not self.MGMT_GROUP
            and not self.BILLING_ACCOUNT_ID
            or (self.MGMT_GROUP and self.BILLING_ACCOUNT_ID)
        ):
            raise ValueError(
                "Exactly one of MGMT_GROUP and BILLING_ACCOUNT_ID should be empty."
            )

        return self


@lru_cache()
def get_settings() -> Settings:
    """Get the global settings for the app."""
    return Settings()  # type: ignore
