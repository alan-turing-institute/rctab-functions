"""Authentication between status package and API web app."""
from datetime import datetime, timedelta

import jwt
import requests
from cryptography.hazmat.primitives import serialization

from status.settings import get_settings

ALGORITHM = "RS256"

# Five minutes, to allow for POSTing a lot of data or a slow web server.
ACCESS_TOKEN_EXPIRE_MINUTES = 5


class BearerAuth(requests.auth.AuthBase):
    """Part of a Bearer (a.k.a. "token") authentication scheme.

    Uses pre-generated keys.
    """

    def __init__(self) -> None:
        settings = get_settings()

        # Generate keys with ssh-keygen -t rsa
        private_key_txt = settings.PRIVATE_KEY

        self.private_key = serialization.load_ssh_private_key(
            private_key_txt.encode(), password=b""
        )

    def create_access_token(self):
        token_claims = {"sub": "status-app"}
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        expire = datetime.utcnow() + access_token_expires
        token_claims.update({"exp": expire})

        return jwt.encode(token_claims, self.private_key, algorithm="RS256")

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        r.headers["authorization"] = "Bearer " + self.create_access_token()
        return r