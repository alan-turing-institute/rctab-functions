"""Tests for status package."""
import logging
from datetime import datetime
from types import SimpleNamespace
from typing import Final
from unittest import TestCase, main
from unittest.mock import MagicMock, call, patch
from uuid import UUID

import jwt
from azure.graphrbac.models import ADGroup, ServicePrincipal, User
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from msrestazure.azure_exceptions import CloudError
from pydantic import HttpUrl, TypeAdapter

import status
from status.models import RoleAssignment, SubscriptionState, SubscriptionStatus

HTTP_ADAPTER: Final = TypeAdapter(HttpUrl)
VALID_URL: Final = HTTP_ADAPTER.validate_python("https://my.org")

EXPECTED_DICT = {
    "role_definition_id": str(UUID(int=10)),
    "role_name": "contributor",
    "principal_id": str(UUID(int=100)),
    "scope": "/subscription_id/",
    "display_name": "Unknown",
    "mail": None,
    "principal_type": None,
}


class TestStatus(TestCase):
    """Tests for the __init__.py file."""

    def test_main(self):
        with patch("status.get_all_status") as mock_get_all_status:
            mock_get_all_status.return_value = ["status1", "status2"]

            with patch("status.datetime") as mock_datetime:
                with patch("status.send_status") as mock_send_status:
                    test_settings = status.settings.Settings(
                        API_URL="https://my.host",
                        PRIVATE_KEY="-----BEGIN OPENSSH PRIVATE KEY-----"
                        "abcde"
                        "-----END OPENSSH PRIVATE KEY-----",
                        AZURE_TENANT_ID=UUID(int=1000),
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

    def test_send_status(self):
        example_status = SubscriptionStatus(
            subscription_id=UUID(int=1),
            display_name="sub1",
            state="Enabled",
            role_assignments=[
                RoleAssignment(
                    role_definition_id=str(UUID(int=10)),
                    role_name="Contributor",
                    principal_id=str(UUID(int=100)),
                    display_name="Joe Bloggs",
                    mail="jbloggs@mail.ac.uk",
                    scope="/",
                )
            ],
        )

        expected_json = status.models.AllSubscriptionStatus(
            status_list=[example_status]
        ).model_dump_json()

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
                        expected_json,
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
                        expected_json,
                        auth=mock_auth.return_value,
                        timeout=60,
                    )

    def test_get_principal_details_user(self):
        """test get_principal_details returns the expected dictionary of user
        information.
        """
        expected = {
            "display_name": "john doe",
            "mail": "j.doe@mail.com",
            "principal_type": User,
        }
        mock_user = MagicMock(spec=User)
        mock_user.display_name = "john doe"
        mock_user.mail = "j.doe@mail.com"
        expected["principal_type"] = type(mock_user)
        actual = status.get_principal_details(mock_user)
        self.assertDictEqual(actual, expected)

    def test_get_principal_details_service_principal(self):
        """test get_principal_details returns the expected dictionary
        of service principal information
        """
        expected = {
            "display_name": "some service",
            "mail": None,
            "principal_type": ServicePrincipal,
        }
        mock_user = MagicMock(spec=ServicePrincipal)
        mock_user.display_name = "some service"
        expected["principal_type"] = type(mock_user)
        actual = status.get_principal_details(mock_user)
        self.assertDictEqual(actual, expected)

    def test_get_ad_group_principals(self):
        """Test get_ad_group_principals populates the user details for members."""
        expected = [
            {
                "display_name": f"person_{i}",
                "mail": f"person_{i}@mail.com",
                "principal_type": ADGroup,
            }
            for i in range(2)
        ]
        mock_users = [MagicMock(spec=User) for i in range(2)]
        for index, item in enumerate(mock_users):
            item.display_name = f"person_{index}"
            item.mail = f"person_{index}@mail.com"
        mock_ad_group = MagicMock(spec=ADGroup)
        mock_ad_group.object_id = ""
        for i in range(2):
            expected[i].update({"principal_type": type(mock_ad_group)})
        with patch("status.GraphRbacManagementClient") as mgc:
            mgc.groups.get_group_members.return_value = (mu for mu in mock_users)
            actual = status.get_ad_group_principals(mock_ad_group, mgc)
            self.assertListEqual(actual, expected)

    def test_get_role_assignment_models__with_user(self):
        """test get_role_assignment_models returns the expected result when
        given a user
        """
        expected_values = {
            "display_name": "john doe",
            "mail": "j.doe@mail.com",
            "principal_type": User,
        }

        expected_dict = EXPECTED_DICT.copy()
        expected_dict.update(expected_values)

        mock_role_assignment = MagicMock()
        mock_role_assignment.properties.role_definition_id = str(UUID(int=10))
        mock_role_assignment.properties.principal_id = str(UUID(int=100))
        mock_role_assignment.properties.scope = "/subscription_id/"
        with patch("status.GraphRbacManagementClient") as mock_grmc:
            expected = RoleAssignment(**expected_dict)
            with patch("status.get_principal") as mock_get_principal:
                mock_get_principal.return_value = User()
                with patch("status.get_principal_details") as mock_gud:
                    mock_gud.return_value = expected_values
                    actual = status.get_role_assignment_models(
                        mock_role_assignment,
                        "contributor",
                        mock_grmc,
                    )
                    self.assertListEqual([expected], actual)

    def test_get_role_assignment_models__with_service_principal(self):
        """test get_role_assignment_models returns the expected result when
        given a service_principal
        """
        expected_values = {
            "display_name": "some function",
            "mail": None,
            "principal_type": ServicePrincipal,
        }
        expected_dict = EXPECTED_DICT.copy()
        mock_role_assignment = MagicMock()
        mock_role_assignment.properties.role_definition_id = str(UUID(int=10))
        mock_role_assignment.properties.principal_id = str(UUID(int=100))
        mock_role_assignment.properties.scope = "/subscription_id/"

        with patch("status.GraphRbacManagementClient") as mock_grmc:
            expected_dict.update(expected_values)
            expected = RoleAssignment(**expected_dict)
            with patch("status.get_principal") as mock_get_principal:
                mock_get_principal.return_value = ServicePrincipal()
                with patch("status.get_principal_details") as mock_spd:
                    mock_spd.return_value = expected_values
                    actual = status.get_role_assignment_models(
                        mock_role_assignment,
                        "contributor",
                        mock_grmc,
                    )
                    self.assertListEqual([expected], actual)

    def test_get_role_assignment_models__with_adgroup(self):
        """test get_role_assignment_models returns the expected result when
        given an ADGroup
        """
        expected_values = [
            {
                "display_name": f"person_{i}",
                "mail": f"person_{i}@mail.com",
                "principal_type": ADGroup,
            }
            for i in range(2)
        ]
        expected_dict_list = [EXPECTED_DICT.copy(), EXPECTED_DICT.copy()]
        for i in range(2):
            expected_dict_list[i].update(expected_values[i])

        mock_role_assignment = MagicMock()
        mock_role_assignment.properties.role_definition_id = str(UUID(int=10))
        mock_role_assignment.properties.principal_id = str(UUID(int=100))
        mock_role_assignment.properties.scope = "/subscription_id/"

        with patch("status.GraphRbacManagementClient") as mock_grmc:
            expected = [
                RoleAssignment(**expected_dict) for expected_dict in expected_dict_list
            ]
            with patch("status.get_principal") as mock_get_principal:
                mock_get_principal.return_value = ADGroup()
                with patch("status.get_ad_group_principals") as mock_adgu:
                    mock_adgu.return_value = expected_values
                    actual = status.get_role_assignment_models(
                        mock_role_assignment,
                        "contributor",
                        mock_grmc,
                    )
                    self.assertListEqual(expected, actual)

    def test_get_role_assignment_models__with_other_role_assignment(self):
        """test get_role_assignment_models returns the expected result when
        given something other than a User, ServicePrincipal or ADGroup
        """
        expected_dict = EXPECTED_DICT.copy()

        mock_role_assignment = MagicMock()
        mock_role_assignment.properties.role_definition_id = str(UUID(int=10))
        mock_role_assignment.properties.principal_id = str(UUID(int=100))
        mock_role_assignment.properties.scope = "/subscription_id/"

        with patch("status.GraphRbacManagementClient") as mock_grmc:
            expected_dict.update({"mail": None})
            expected = RoleAssignment(**expected_dict)
            with patch("status.get_principal") as mock_get_principal:
                mock_get_principal.return_value = SimpleNamespace()
                actual = status.get_role_assignment_models(
                    mock_role_assignment,
                    "contributor",
                    mock_grmc,
                )
                self.assertListEqual([expected], actual)

    def test_get_subscription_role_assignment_models__no_error(self):
        """test get_subscription_role_assignment_models returns a list of
        RoleAssignments"""
        mock_subscription = MagicMock()
        mock_subscription.subscription_id = str(UUID(int=1))
        with patch("status.GraphRbacManagementClient") as mock_grmc:
            with patch("status.get_auth_client") as mock_gac:
                mock_gac.return_value = None
                with patch("status.get_role_def_dict") as mock_grdd:
                    mock_grdd.return_value = {str(UUID(int=10)): "contributor"}
                    with patch("status.get_role_assignments_list") as mock_gral:
                        mock_gral.return_value = [
                            SimpleNamespace(
                                properties=SimpleNamespace(
                                    role_definition_id=str(UUID(int=10)),
                                    principal_id=str(UUID(int=100 + i)),
                                    scope="/",
                                )
                            )
                            for i in range(3)
                        ]
                        with patch("status.get_principal") as mock_principal:
                            mock_principal.return_value = User(display_name="Unknown")
                            actual = status.get_subscription_role_assignment_models(
                                mock_subscription, mock_grmc
                            )
                            self.assertIsInstance(actual, list)
                            self.assertEqual(len(actual), 3)
                            for item in actual:
                                self.assertIsInstance(item, RoleAssignment)

    def test_get_subscription_role_assignment_models__cloud_error_returns_empty_list(
        self,
    ):
        """test get_subscription_role_assignment_models returns an empty list when a
        CloudError occurs
        """
        mock_subscription = MagicMock()
        with patch("status.GraphRbacManagementClient") as mock_grmc:
            with patch("status.get_auth_client") as mock_gac:
                mock_gac.return_value = None
                with patch("status.get_role_def_dict") as mock_grdd:
                    mock_grdd.return_value = {str(UUID(int=10)): "contributor"}
                    with patch("status.get_role_assignments_list") as mock_gral:
                        mock_gral.assert_not_called()
                        with patch("status.get_role_assignment_models") as mock_gram:
                            mock_gram.side_effect = CloudError
                            mock_gram.return_value = None
                            actual = status.get_subscription_role_assignment_models(
                                mock_subscription, mock_grmc
                            )
                            self.assertListEqual(actual, [])

    def test_get_all_status(self):
        with patch("status.SubscriptionClient") as mock_sub_client:
            mock_list_func = mock_sub_client.return_value.subscriptions.list
            mock_list_func.return_value = [
                SimpleNamespace(
                    subscription_id=str(UUID(int=1)),
                    display_name="sub1",
                    state="Enabled",
                )
            ]

            with patch("status.AuthClient") as mock_auth_client:
                mock_assign_func = mock_auth_client.return_value.role_assignments.list
                mock_assign_func.return_value = [
                    SimpleNamespace(
                        properties=SimpleNamespace(
                            role_definition_id=str(UUID(int=10)),
                            principal_id=str(UUID(int=100)),
                            scope="/",
                        )
                    )
                ]

                mock_defs_func = mock_auth_client.return_value.role_definitions.list
                mock_defs_func.return_value = [
                    SimpleNamespace(id=str(UUID(int=10)), role_name="Contributor")
                ]

                with patch("status.GetObjectsParameters") as mock_get_object_params:
                    with patch("status.GraphRbacManagementClient") as mock_graph_client:
                        mock_get_objects = (
                            mock_graph_client.return_value.objects.get_objects_by_object_ids  # noqa pylint: disable=C0301
                        )
                        mock_get_objects.return_value = [
                            User(display_name="Joe Bloggs", mail="jbloggs@mail.ac.uk")
                        ]

                        expected = [
                            SubscriptionStatus(
                                subscription_id=UUID(int=1),
                                display_name="sub1",
                                state="Enabled",
                                role_assignments=[
                                    RoleAssignment(
                                        role_definition_id=str(UUID(int=10)),
                                        role_name="Contributor",
                                        principal_id=str(UUID(int=100)),
                                        display_name="Joe Bloggs",
                                        mail="jbloggs@mail.ac.uk",
                                        scope="/",
                                        principal_type=User,
                                    )
                                ],
                            )
                        ]

                        actual = status.get_all_status(UUID(int=1000))
                        self.assertListEqual(expected, actual)

                        mock_graph_client.assert_called_with(
                            credentials=status.GRAPH_CREDENTIALS,
                            tenant_id=str(UUID(int=1000)),
                        )

                        mock_get_object_params.assert_called_with(
                            include_directory_object_references=True,
                            object_ids=[str(UUID(int=100))],
                        )

                        mock_auth_client.assert_called_with(
                            credential=status.CREDENTIALS,
                            subscription_id=str(UUID(int=1)),
                        )
                        mock_defs_func.assert_called_with(
                            scope="/subscriptions/" + str(UUID(int=1))
                        )

                    # test service principal
                    with patch("status.GraphRbacManagementClient") as mock_graph_client:
                        mock_get_objects = (
                            mock_graph_client.return_value.objects.get_objects_by_object_ids  # noqa pylint: disable=C0301
                        )
                        mock_get_objects.return_value = [
                            ServicePrincipal(display_name="Some Service")
                        ]

                        expected = [
                            SubscriptionStatus(
                                subscription_id=UUID(int=1),
                                display_name="sub1",
                                state="Enabled",
                                role_assignments=[
                                    RoleAssignment(
                                        role_definition_id=str(UUID(int=10)),
                                        role_name="Contributor",
                                        principal_id=str(UUID(int=100)),
                                        display_name="Some Service",
                                        mail=None,
                                        scope="/",
                                        principal_type=ServicePrincipal,
                                    )
                                ],
                            )
                        ]

                        actual = status.get_all_status(UUID(int=1000))
                        self.assertListEqual(expected, actual)

                    with patch("status.GraphRbacManagementClient") as mock_graph_client:
                        mock_get_objects = (
                            mock_graph_client.return_value.objects.get_objects_by_object_ids  # noqa pylint: disable=C0301
                        )
                        mock_get_objects.return_value = [SimpleNamespace()]

                        expected = [
                            SubscriptionStatus(
                                subscription_id=UUID(int=1),
                                display_name="sub1",
                                state="Enabled",
                                role_assignments=[
                                    RoleAssignment(
                                        role_definition_id=str(UUID(int=10)),
                                        role_name="Contributor",
                                        principal_id=str(UUID(int=100)),
                                        display_name="Unknown",
                                        scope="/",
                                        mail=None,
                                        principal_type=SimpleNamespace,
                                    )
                                ],
                            )
                        ]

                        actual = status.get_all_status(UUID(int=1000))
                        self.assertListEqual(expected, actual)

    def test_get_all_status_error_handling(self):
        # ToDo Could we make a patch() that incorporates these four patches?
        with patch("status.SubscriptionClient") as mock_sub_client:
            mock_list_func = mock_sub_client.return_value.subscriptions.list
            mock_list_func.return_value = [
                SimpleNamespace(
                    subscription_id=str(UUID(int=1)),
                    display_name="sub1",
                    state="Enabled",
                )
            ]

            with patch("status.AuthClient") as mock_auth_client:
                mock_assign_func = mock_auth_client.return_value.role_assignments.list
                mock_assign_func.return_value = [
                    SimpleNamespace(
                        properties=SimpleNamespace(
                            role_definition_id=str(UUID(int=10)),
                            principal_id=str(UUID(int=100)),
                            scope="/",
                        )
                    )
                ]

                mock_defs_func = mock_auth_client.return_value.role_definitions.list
                mock_defs_func.return_value = [
                    SimpleNamespace(id=str(UUID(int=10)), role_name="Contributor")
                ]

                with patch("status.GetObjectsParameters"):
                    with patch("status.GraphRbacManagementClient") as mock_graph_client:
                        mock_objects = mock_graph_client.return_value.objects
                        mock_objects.get_objects_by_object_ids.side_effect = CloudError(
                            SimpleNamespace(status_code=403),
                            error="Forbidden for url: https://graph.windows.net/...",
                        )

                        actual = status.get_all_status(UUID(int=1000))
                        expected = [
                            SubscriptionStatus(
                                subscription_id=UUID(int=1),
                                display_name="sub1",
                                state=SubscriptionState("Enabled"),
                                role_assignments=tuple(),
                            )
                        ]

                        self.assertListEqual(expected, actual)


class TestSettings(TestCase):
    """Tests for the status.settings module."""

    def test_key_validation(self):
        self.assertRaises(
            ValueError,
            lambda: status.settings.Settings(
                API_URL="https://a.b.com",
                PRIVATE_KEY="-----BEGIN OPENSSH PRIVATE KEY-----",
            ),
        )

        self.assertRaises(
            ValueError,
            lambda: status.settings.Settings(
                API_URL="https://a.b.com",
                PRIVATE_KEY="-----END OPENSSH PRIVATE KEY-----",
            ),
        )

    def test_settings(self):
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
            AZURE_TENANT_ID=UUID(int=9),
        )


class TestAuth(TestCase):
    """Tests for the status.auth module."""

    def test_bearer_auth(self):
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
    def test_called_twice(self):
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
