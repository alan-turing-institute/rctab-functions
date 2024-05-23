"""Authentication between status package and API web app."""

from datetime import datetime, timedelta

import jwt
import requests
from cryptography.hazmat.primitives import serialization

from controller import settings

ALGORITHM = "RS256"

# Five minutes, to allow for POSTing a lot of data or a slow web server.
ACCESS_TOKEN_EXPIRE_MINUTES = 5


class BearerAuth(requests.auth.AuthBase):
    """Part of a Bearer (a.k.a. "token") authentication scheme.

    Uses pre-generated keys.
    """

    def __init__(self) -> None:
        """Initialize the BearerAuth object."""
        auth_settings = settings.get_settings()

        # Generate keys with ssh-keygen -t rsa
        private_key_txt = auth_settings.PRIVATE_KEY

        self.private_key = serialization.load_ssh_private_key(
            private_key_txt.encode(), password=b""
        )

    def create_access_token(self) -> str:
        """Create an access token."""
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.utcnow() + access_token_expires
        token_claims = {"sub": "controller-app", "exp": expire}

        return jwt.encode(
            token_claims, self.private_key, algorithm=ALGORITHM  # type: ignore
        )

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        """Attach Authorization Header to a request."""
        r.headers["authorization"] = "Bearer " + self.create_access_token()
        return r
