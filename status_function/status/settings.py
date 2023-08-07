"""Configuration for the app."""
from functools import lru_cache
from typing import Optional
from uuid import UUID

from pydantic import BaseSettings, HttpUrl, validator


class Settings(BaseSettings):
    """A class to load and validate settings from the environment or a .env file."""

    API_URL: HttpUrl
    PRIVATE_KEY: str
    AZURE_TENANT_ID: UUID  # Also used by the EnvironmentCredential
    LOG_LEVEL: str = "WARNING"
    CENTRAL_LOGGING_CONNECTION_STRING: Optional[str]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("PRIVATE_KEY")
    def correct_start_and_end(cls, v):  # pylint: disable=no-self-argument
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
    return Settings()
