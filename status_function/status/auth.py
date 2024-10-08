"""Authentication between status package and API web app.

Attributes:
    ALGORITHM: The algorithm used to sign the access token. Value is "RS256".
    ACCESS_TOKEN_EXPIRE_MINUTES: The number of minutes before an access token.
        value is 5.
"""

from datetime import datetime, timedelta

import jwt
import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dsa
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from status.settings import get_settings

ALGORITHM = "RS256"

# Five minutes, to allow for POSTing a lot of data or a slow web server.
ACCESS_TOKEN_EXPIRE_MINUTES = 5


class BearerAuth(requests.auth.AuthBase):
    """Part of a Bearer (a.k.a. "token") authentication scheme.

    Uses pre-generated keys.
    """

    def __init__(self) -> None:
        """Initialize the BearerAuth object."""
        settings = get_settings()

        # Generate keys with ssh-keygen -t rsa
        private_key_txt = settings.PRIVATE_KEY

        private_key = serialization.load_ssh_private_key(
            private_key_txt.encode(), password=b""
        )
        assert not isinstance(
            private_key, dsa.DSAPrivateKey
        ), "DSA keys are not supported."

        # jwt.encode(), used to create the access token, doesn't support DSA keys
        allowed_type = EllipticCurvePrivateKey | RSAPrivateKey | Ed25519PrivateKey
        self.private_key: allowed_type = private_key

    def create_access_token(self) -> str:
        """Create an access token for the user to access the API.

        Returns:
            The access token.
        """
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.utcnow() + access_token_expires
        token_claims = {"sub": "status-app", "exp": expire}
        return jwt.encode(token_claims, self.private_key, algorithm=ALGORITHM)

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        """Attach Authorization Header to a request."""
        r.headers["authorization"] = "Bearer " + self.create_access_token()
        return r
