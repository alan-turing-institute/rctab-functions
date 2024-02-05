"""Configuration for the app."""
from functools import lru_cache
from typing import Optional

from pydantic import BaseSettings, HttpUrl, validator


class Settings(BaseSettings):
    """A class to load and validate settings from the environment or a .env file."""

    API_URL: HttpUrl  # e.g. https://my.rctab.host
    PRIVATE_KEY: str  # The private part of an RSA key pair
    USAGE_HISTORY_DAYS: int = 3  # The number of days' history to collect...
    USAGE_HISTORY_DAYS_OFFSET: int = 0  # ...starting from this many days ago
    LOG_LEVEL: str = "WARNING"  # The log level
    CM_MGMT_GROUP: Optional[str]  # The cost management function mgmt group
    MGMT_GROUP: Optional[str]  # Either, the usage function mgmt group...
    BILLING_ACCOUNT_ID: Optional[str]  # ...or the usage function billing account ID
    CENTRAL_LOGGING_CONNECTION_STRING: Optional[str]

    class Config:
        """Settings for the settings class itself."""

        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("PRIVATE_KEY")
    def correct_start_and_end(cls, v):  # pylint: disable=no-self-argument
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

    @validator("MGMT_GROUP", "BILLING_ACCOUNT_ID")
    def mgmt_group_or_billing_id(
        cls, value, values
    ):  # pylint: disable=no-self-argument
        """Require either a mgmt group name or a billing account ID."""
        # Assume we don't know which order things are validated in
        if "BILLING_ACCOUNT_ID" in values.keys() or "MGMT_GROUP" in values.keys():
            previous_value = values.get("BILLING_ACCOUNT_ID", values.get("MGMT_GROUP"))

            if (previous_value and value) or (not previous_value and not value):
                raise ValueError(
                    "Exactly one of MGMT_GROUP and BILLING_ACCOUNT_ID should be empty."
                )

        return value


@lru_cache()
def get_settings() -> Settings:
    """Get the global settings for the app."""
    return Settings()  # type: ignore
