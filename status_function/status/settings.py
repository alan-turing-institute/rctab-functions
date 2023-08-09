"""Configuration for the app."""
from functools import lru_cache
from typing import Optional
from uuid import UUID

from pydantic import BaseSettings, HttpUrl, validator


class Settings(BaseSettings):
    """A class to load and validate settings from the environment or a .env file.

    Attributes:
        API_URL: The URL of the API.
        PRIVATE_KEY: The private key used to sign the access token.
        LOG_LEVEL: The log level. Default is "WARNING".
        CENTRAL_LOGGING_CONNECTION_STRING: The connection string for the
            centralised logging workspace.

    """

    API_URL: HttpUrl
    PRIVATE_KEY: str
    AZURE_TENANT_ID: UUID  # Also used by the EnvironmentCredential
    LOG_LEVEL: str = "WARNING"
    CENTRAL_LOGGING_CONNECTION_STRING: Optional[str]

    class Config:
        """Configuration for the Settings class env file.

        Attributes:
            env_file: The name of the .env file.
            env_file_encoding: The encoding of the .env file.
        """

        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("PRIVATE_KEY")
    def correct_start_and_end(
        cls: Config, v: str
    ) -> str:  # pylint: disable=no-self-argument
        """Check that the private key is a private key.

        Args:
            cls: The class.
            v: The private key.

        Returns:
            The validated private key.
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
    """Get the settings.

    Returns:
        The settings.
    """
    return Settings()
