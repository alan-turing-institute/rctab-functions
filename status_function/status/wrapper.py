"""Copied from https://stackoverflow.com/a/64129363/3324095 and slightly modified."""
from typing import Optional

from azure.core.pipeline import PipelineContext, PipelineRequest
from azure.core.pipeline.policies import BearerTokenCredentialPolicy
from azure.core.pipeline.transport import HttpRequest
from azure.identity import DefaultAzureCredential
from msrest.authentication import BasicTokenAuthentication
from requests import Session


class CredentialWrapper(BasicTokenAuthentication):
    """Wrapper for azure-identity credentials."""

    def __init__(
        self,
        credential: Optional[DefaultAzureCredential] = None,
        resource_id: str = "https://management.azure.com/.default",
        **kwargs: dict
    ):
        """Wrap any azure-identity credential to work with SDK.

        Applies to credentials that need azure.common.credentials/msrestazure.
        Default resource is ARM
        (syntax of endpoint v2).

        Args:
            credential: Any azure-identity credential (DefaultAzureCredential
                by default)
            resource_id: The scope to use to get the token (default ARM)

        Keyword Args:
            Any other parameter accepted by BasicTokenAuthentication
        """
        super().__init__({"": ""})
        if credential is None:
            credential = DefaultAzureCredential(
                exclude_visual_studio_code_credential=True
            )  # This line edited
        self._policy = BearerTokenCredentialPolicy(credential, resource_id, **kwargs)

    def _make_request(self):
        return PipelineRequest(
            HttpRequest("CredentialWrapper", "https://fakeurl"), PipelineContext(None)
        )

    def set_token(self):
        """Ask the azure-core BearerTokenCredentialPolicy policy to get a token.

        Using the policy gives us for free the caching system of azure-core.
        A private method could be used to make this code simpler, but by definition
        we can't assure they will be there forever, so we instead mock a fake call
        to the policy to extract the token, using 100% public API.

        Attributes:
            token: The token to use for authentication.
        """
        request = self._make_request()
        self._policy.on_request(request)
        # Read Authorization, and get the second part after Bearer
        token = request.http_request.headers["Authorization"].split(" ", 1)[1]
        self.token = {"access_token": token}

    def signed_session(self, session=None) -> Session:
        """Sign the session.

        Args:
            session: The session to sign. Default is None.

        Returns:
            The signed session.
        """
        self.set_token()
        return super().signed_session(session)
