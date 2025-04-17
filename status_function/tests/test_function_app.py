"""Tests for status package."""

import logging
from datetime import datetime
from importlib import import_module
from types import SimpleNamespace
from typing import Final
from unittest import TestCase, main
from unittest.mock import AsyncMock, MagicMock, call, patch
from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from msgraph import GraphServiceClient
from msgraph.generated.models.service_principal import ServicePrincipal
from msgraph.generated.models.user import User
from pydantic import HttpUrl, TypeAdapter
from rctab_models.models import RoleAssignment, SubscriptionState, SubscriptionStatus

import status

HTTP_ADAPTER: Final = TypeAdapter(HttpUrl)
VALID_URL: Final = HTTP_ADAPTER.validate_python("https://my.org")

EXPECTED_DICT: Final = {
    "role_definition_id": str(UUID(int=10)),
    "role_name": "contributor",
    "principal_id": str(UUID(int=100)),
    "scope": "/subscription_id/",
    "display_name": "Unknown",
    "mail": None,
    "principal_type": None,
}

API_VERSION: Final = "2022-04-01"
# e.g. v2022_04_01
API_VERSION_PACKAGE: Final = "v" + API_VERSION.replace("-", "_")
OPERATIONS_MODULE: Final = import_module(
    f"azure.mgmt.authorization.{API_VERSION_PACKAGE}.operations"
)
MODELS_MODULE: Final = import_module(
    f"azure.mgmt.authorization.{API_VERSION_PACKAGE}.models"
)


class TestStatus(TestCase):
    """Tests for the __init__.py file."""

    def test_main(self) -> None:
        with patch("status.get_all_status") as mock_get_all_status:
            mock_get_all_status.return_value = ["status1", "status2"]

            with patch("status.datetime") as mock_datetime:
                with patch("status.send_status") as mock_send_status:
                    test_settings = status.settings.Settings(
                        API_URL="https://my.host",
                        PRIVATE_KEY="-----BEGIN OPENSSH PRIVATE KEY-----"
                        "abcde"
                        "-----END OPENSSH PRIVATE KEY-----",
                        _env_file=None,
                    )
                    with patch("status.settings.get_settings") as mock_get_settings:
                        mock_get_settings.return_value = test_settings

                        mock_timer = MagicMock()
                        mock_timer.past_due = True

                        now = datetime.now()
                        mock_datetime.now.return_value = now

                        status.main(mock_timer)

                        mock_get_all_status.assert_called_once()
                        mock_send_status.assert_has_calls(
                            [
                                call(
                                    HTTP_ADAPTER.validate_python("https://my.host"),
                                    ["status1", "status2"],
                                ),
                            ]
                        )

    def test_send_status(self) -> None:
        example_status = SubscriptionStatus(
            subscription_id=UUID(int=1),
            display_name="sub1",
            state="Enabled",
            role_assignments=(
                RoleAssignment(
                    role_definition_id=str(UUID(int=10)),
                    role_name="Contributor",
                    principal_id=str(UUID(int=100)),
                    display_name="Joe Bloggs",
                    mail="jbloggs@mail.ac.uk",
                    scope="/",
                ),
            ),
        )

        expected_data = (
            status.models.AllSubscriptionStatus(status_list=[example_status])
            .model_dump_json()
            .encode("utf-8")
        )

        with patch("status.BearerAuth") as mock_auth:
            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 300
                mock_response.text = "some-mock-text"
                mock_post.return_value = mock_response

                with patch("status.logger.warning") as mock_warning:
                    with self.assertRaises(RuntimeError):
                        status.send_status(VALID_URL, [example_status])

                    expected_call = call(
                        "https://my.org/accounting/all-status",
                        data=expected_data,
                        auth=mock_auth.return_value,
                        timeout=60,
                    )
                    mock_post.assert_has_calls([expected_call] * 2)

                    # Check the most recent call to logging.warning().
                    mock_warning.assert_called_with(
                        "Failed to send status data. Response code: %d. "
                        "Response text: %s",
                        300,
                        "some-mock-text",
                    )

            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_post.return_value = mock_response

                with patch("logging.warning") as _:
                    status.send_status(VALID_URL, [example_status])

                    mock_post.assert_called_once_with(
                        "https://my.org/accounting/all-status",
                        data=expected_data,
                        auth=mock_auth.return_value,
                        timeout=60,
                    )

    def test_get_principal_details_user(self) -> None:
        """test get_principal_details returns the expected dictionary of user
        information.
        """
        expected = {
            "display_name": "john doe",
            "mail": "j.doe@mail.com",
        }
        mock_user = MagicMock(spec=User)
        mock_user.display_name = "john doe"
        mock_user.mail = "j.doe@mail.com"
        actual = status.get_principal_details(mock_user)
        self.assertDictEqual(actual, expected)

    def test_get_principal_details_service_principal(self) -> None:
        """test get_principal_details returns the expected dictionary
        of service principal information
        """
        expected = {
            "display_name": "some service",
            "mail": None,
        }
        mock_user = MagicMock(spec=ServicePrincipal)
        mock_user.display_name = "some service"
        actual = status.get_principal_details(mock_user)
        self.assertDictEqual(actual, expected)

    def test_get_graph_group_members(self) -> None:
        """todo"""

    def test_get_graph_user(self) -> None:
        """todo"""

    def test_get_graph_service_principal(self) -> None:
        """todo"""

    def test_get_role_assignment_models__no_principal(self) -> None:
        """test get_role_assignment_models can handle not finding a principal"""
        with patch("status.logger") as mock_logger:
            principal_type = "Blah"
            role_assignment = MODELS_MODULE.RoleAssignment(
                role_definition_id=str(UUID(int=10)),
                role_name="Contributor",
                principal_id=str(UUID(int=100)),
                principal_type="Blah",
            )
            role_assignment.scope = "/"
            status.get_role_assignment_models(
                role_assignment, "somerole", MagicMock(spec=GraphServiceClient)
            )
        mock_logger.warning.assert_called_with(
            "Did not recognise principal type %s", principal_type
        )

    def test_get_all_status(self) -> None:
        """Check get_all_status() works as intended."""
        with patch("status.SubscriptionClient") as mock_sub_client:
            mock_list_func = mock_sub_client.return_value.subscriptions.list
            mock_list_func.return_value = [
                SimpleNamespace(
                    subscription_id=str(UUID(int=1)),
                    display_name="sub1",
                    state="Enabled",
                )
            ]

            # Import the role assignments class from the specific API version.
            mock_role_assignments = MagicMock(
                spec=OPERATIONS_MODULE.RoleAssignmentsOperations
            )
            with patch("status.AuthClient") as mock_auth_client:
                mock_auth_client.return_value.role_assignments = mock_role_assignments
                mock_assign_func = mock_role_assignments.list_for_subscription
                user_assignment = MODELS_MODULE.RoleAssignment(
                    role_definition_id=str(UUID(int=10)),
                    principal_id=str(UUID(int=100)),
                )
                user_assignment.scope = "/"
                user_assignment.principal_type = "User"
                sp_assignment = MODELS_MODULE.RoleAssignment(
                    role_definition_id=str(UUID(int=10)),
                    principal_id=str(UUID(int=100)),
                )
                sp_assignment.scope = "/"
                sp_assignment.principal_type = "ServicePrincipal"
                group_assignment = MODELS_MODULE.RoleAssignment(
                    role_definition_id=str(UUID(int=10)),
                    principal_id=str(UUID(int=100)),
                )
                group_assignment.scope = "/"
                group_assignment.principal_type = "Group"
                mock_assign_func.return_value = [
                    user_assignment,
                    sp_assignment,
                    group_assignment,
                ]

                mock_defs_func = mock_auth_client.return_value.role_definitions.list
                mock_defs_func.return_value = [
                    SimpleNamespace(id=str(UUID(int=10)), role_name="Contributor")
                ]

                with patch("status.GraphServiceClient") as mock_graph_client:
                    mock_get_user = mock_graph_client.return_value.users.by_user_id()
                    mock_get_user.get = AsyncMock()
                    mock_get_user.get.return_value = User(
                        display_name="Joe Bloggs", mail="jbloggs@mail.ac.uk"
                    )

                    mock_sps = mock_graph_client.return_value.service_principals
                    mock_get_sp = mock_sps.by_service_principal_id()
                    mock_get_sp.get = AsyncMock()
                    mock_get_sp.get.return_value = ServicePrincipal(
                        display_name="SomeService",
                    )

                    mock_groups = mock_graph_client.return_value.groups
                    mock_get_group_membs = mock_groups.by_group_id.return_value.members
                    mock_get_group_membs.get = AsyncMock()
                    mock_get_group_membs.get.return_value.value = [
                        User(display_name="Joe Frogs", mail="jfrogs@mail.ac.uk")
                    ]

                    expected = [
                        SubscriptionStatus(
                            subscription_id=UUID(int=1),
                            display_name="sub1",
                            state=SubscriptionState.ENABLED,
                            role_assignments=(
                                RoleAssignment(
                                    role_definition_id=str(UUID(int=10)),
                                    role_name="Contributor",
                                    principal_id=str(UUID(int=100)),
                                    display_name="Joe Bloggs",
                                    mail="jbloggs@mail.ac.uk",
                                    scope="/",
                                ),
                                RoleAssignment(
                                    role_definition_id=str(UUID(int=10)),
                                    role_name="Contributor",
                                    principal_id=str(UUID(int=100)),
                                    display_name="SomeService",
                                    mail=None,
                                    scope="/",
                                ),
                                RoleAssignment(
                                    role_definition_id=str(UUID(int=10)),
                                    role_name="Contributor",
                                    principal_id=str(UUID(int=100)),
                                    display_name="Joe Frogs",
                                    mail="jfrogs@mail.ac.uk",
                                    scope="/",
                                ),
                            ),
                        )
                    ]

                    actual = status.get_all_status()
                    self.assertListEqual(expected, actual)

                    mock_graph_client.assert_called_with(
                        credentials=status.CREDENTIALS,
                        scopes=["https://graph.microsoft.com/.default"],
                    )

                    mock_auth_client.assert_called_with(
                        credential=status.CREDENTIALS,
                        subscription_id=str(UUID(int=1)),
                        api_version=API_VERSION,
                    )
                    mock_defs_func.assert_called_with(
                        scope="/subscriptions/" + str(UUID(int=1))
                    )


class TestSettings(TestCase):
    """Tests for the status.settings module."""

    def test_key_validation(self) -> None:
        self.assertRaises(
            ValueError,
            lambda: status.settings.Settings(
                API_URL="https://a.b.com",
                PRIVATE_KEY="-----BEGIN OPENSSH PRIVATE KEY-----",
                _env_file=None,
            ),
        )

        self.assertRaises(
            ValueError,
            lambda: status.settings.Settings(
                API_URL="https://a.b.com",
                PRIVATE_KEY="-----END OPENSSH PRIVATE KEY-----",
                _env_file=None,
            ),
        )

    def test_settings(self) -> None:
        """Check that we can make a Settings instance, given the right arguments."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        private_key_str = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        status.settings.Settings(
            PRIVATE_KEY=private_key_str,
            API_URL="https://a.b.com",
            LOG_LEVEL="WARNING",
            _env_file=None,
        )


class TestAuth(TestCase):
    """Tests for the status.auth module."""

    def test_bearer_auth(self) -> None:
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        private_key_str = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        public_key = private_key.public_key()
        public_key_str = public_key.public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        ).decode("utf-8")

        with patch("status.auth.get_settings") as mock_get_settings:
            mock_get_settings.return_value.PRIVATE_KEY = private_key_str

            bearer = status.auth.BearerAuth()
            token = bearer.create_access_token()

            payload = jwt.decode(
                token,
                public_key_str,
                algorithms=["RS256"],
                options={"require": ["exp", "sub"]},
            )
            username = payload.get("sub")
            self.assertEqual("status-app", username)


class TestLoggingUtils(TestCase):
    def test_called_twice(self) -> None:
        """Adding multiple loggers could cause large storage bills."""
        with patch("status.settings.get_settings") as mock_get_settings:
            mock_get_settings.return_value.CENTRAL_LOGGING_CONNECTION_STRING = "my-str"

            with patch("status.logutils.AzureLogHandler", new=MagicMock):
                status.logutils.add_log_handler_once("a")
                status.logutils.add_log_handler_once("a")
        handlers = logging.getLogger("a").handlers
        self.assertEqual(1, len(handlers))


if __name__ == "__main__":
    main()
