"""Copied from https://stackoverflow.com/a/64129363/3324095."""
from azure.core.pipeline import PipelineContext, PipelineRequest
from azure.core.pipeline.policies import BearerTokenCredentialPolicy
from azure.core.pipeline.transport import HttpRequest
from azure.identity import DefaultAzureCredential
from msrest.authentication import BasicTokenAuthentication


class CredentialWrapper(BasicTokenAuthentication):
    """Wrapper for azure-identity credentials."""

    def __init__(
        self,
        credential=None,
        resource_id="https://management.azure.com/.default",
        **kwargs
    ):
        """Wrap an azure-identity credential for SDK compatibility.

        Adapts azure-identity credentials for use with SDKs that require
        azure.common.credentials or msrestazure. The default resource is
        Azure Resource Manager (ARM) using the v2 syntax of the endpoint.

        Args:
            credential: An azure-identity credential instance.
                Default is DefaultAzureCredential.
            resource_id (str): The scope to use when obtaining the token.
                Default is 'ARM'.
        """
        super().__init__(None)
        if credential is None:
            credential = DefaultAzureCredential()
        self._policy = BearerTokenCredentialPolicy(credential, resource_id, **kwargs)

    def _make_request(self):
        return PipelineRequest(
            HttpRequest("CredentialWrapper", "https://fakeurl"), PipelineContext(None)
        )

    def set_token(self):
        """Ask the azure-core BearerTokenCredentialPolicy policy to get a token.

        Using the policy gives us for free the caching system of azure-core.
        We could make this code simpler by using private method, but by definition
        I can't assure they will be there forever, so mocking a fake call to the policy
        to extract the token, using 100% public API.
        """
        request = self._make_request()
        self._policy.on_request(request)
        # Read Authorization, and get the second part after Bearer
        token = request.http_request.headers["Authorization"].split(" ", 1)[1]
        self.token = {"access_token": token}

    def signed_session(self, session=None):
        """Get a signed session for authenticated requests.

        Args:
            session: Session object to use. Default is None.

        Returns:
            A signed session.
        """
        self.set_token()
        return super().signed_session(session)
