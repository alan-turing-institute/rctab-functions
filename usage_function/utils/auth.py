"""Authentication between usage package and API web app."""
from datetime import datetime, timedelta

import jwt
import requests
from cryptography.hazmat.primitives import serialization

from utils.settings import get_settings

ALGORITHM = "RS256"

# Five minutes, to allow for POSTing a lot of data or a slow web server.
ACCESS_TOKEN_EXPIRE_MINUTES = 5


class BearerAuth(requests.auth.AuthBase):
    """A Bearer (a.k.a. "token") authentication scheme.

    Uses pre-shared keys.
    """

    def __init__(self) -> None:
        """Initialise the BearerAuth class."""
        settings = get_settings()

        # Generate keys with ssh-keygen -t rsa
        private_key_txt = settings.PRIVATE_KEY

        self.private_key = serialization.load_ssh_private_key(
            private_key_txt.encode(), password=b""
        )

    def create_access_token(self):
        """Create an access token."""
        token_claims = {"sub": "usage-app"}
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

        expire = datetime.utcnow() + access_token_expires
        token_claims.update({"exp": str(expire)})

        return jwt.encode(token_claims, self.private_key, algorithm="RS256")  # type: ignore

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        """Add the bearer token to the request."""
        r.headers["authorization"] = "Bearer " + self.create_access_token()
        return r
