"""Tests for controller package."""

import json
import logging
from typing import Final
from unittest import TestCase, main
from unittest.mock import MagicMock, call, patch
from uuid import UUID

import jwt
from azure.core.exceptions import HttpResponseError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import HttpUrl, TypeAdapter
from rctab_models.models import DesiredState

import controller

HTTP_ADAPTER: Final = TypeAdapter(HttpUrl)
VALID_URL: Final = HTTP_ADAPTER.validate_python("https://my.org")


class TestControllerModule(TestCase):
    """Tests for the __init__.py file."""

    def test_main(self) -> None:
        with patch("controller.get_desired_states") as mock_get_desired_states:
            desired_states = [
                DesiredState(subscription_id=UUID(int=22), desired_state="Disabled"),
                DesiredState(subscription_id=UUID(int=33), desired_state="Disabled"),
                DesiredState(subscription_id=UUID(int=44), desired_state="Enabled"),
            ]

            mock_get_desired_states.return_value = desired_states

            with patch("controller.disable_subscriptions") as mock_deactivate:
                with patch("controller.enable_subscriptions") as mock_enable:
                    mock_settings = controller.settings.Settings(
                        API_URL=VALID_URL,
                        PRIVATE_KEY=(
                            "-----BEGIN OPENSSH PRIVATE KEY-----"
                            "abcde"
                            "-----END OPENSSH PRIVATE KEY-----"
                        ),
                        LOG_LEVEL="WARNING",
                        _env_file=None,
                    )
                    with patch("controller.settings.get_settings") as mock_get_settings:
                        mock_get_settings.return_value = mock_settings

                        mock_timer = MagicMock()
                        mock_timer.past_due = False

                        controller.main(mock_timer)

                        mock_deactivate.assert_called_with([UUID(int=22), UUID(int=33)])

                        mock_enable.assert_called_with([UUID(int=44)])

    def test_disable_subscriptions(self) -> None:
        with patch("controller.disable_subscription") as mock_disable:
            controller.disable_subscriptions([UUID(int=22), UUID(int=33)])

            mock_disable.assert_has_calls([call(UUID(int=22)), call(UUID(int=33))])

    def test_enable_subscriptions(self) -> None:
        with patch("controller.enable_subscription") as mock_enable:
            controller.enable_subscriptions([UUID(int=22), UUID(int=33)])

            mock_enable.assert_has_calls([call(UUID(int=22)), call(UUID(int=33))])

    def test_get_desired_states(self) -> None:
        with patch("controller.BearerAuth") as mock_auth:
            with patch("controller.get") as mock_get:
                desired_state_one = controller.models.DesiredState(
                    subscription_id=UUID(int=98),
                    desired_state=controller.models.SubscriptionState("Disabled"),
                )

                expected = [desired_state_one]

                # requests.get() will return an object with a .json() method...
                mock_get.return_value.json.return_value = [
                    json.loads(x.model_dump_json().encode("utf-8")) for x in expected
                ]

                # ...and a status_code.
                mock_get.return_value.status_code = 200

                actual = controller.get_desired_states(VALID_URL)
                mock_get.assert_called_with(
                    url="https://my.org/accounting/desired-states",
                    auth=mock_auth.return_value,
                    timeout=120,
                )

                self.assertEqual(expected, actual)

    def test_get_desired_states_raises(self) -> None:
        with patch("controller.BearerAuth"):
            with patch("controller.logger.error") as mock_error:  # TODO: fix this
                with patch("controller.get") as mock_get:
                    mock_get.return_value.status_code = 500

                    host = "https://internal.error.host"
                    host_url = HTTP_ADAPTER.validate_python(host)
                    with self.assertRaises(RuntimeError):
                        controller.get_desired_states(host_url)

                    expected_str = (
                        "Could not get desired states. %s returned %s status."
                    )
                    mock_error.assert_called_with(
                        expected_str, host + "/accounting/desired-states", str(500)
                    )

    def test_disable_subscriptions_handles(self) -> None:
        with patch("controller.disable_subscription") as mock_disable:
            mock_disable.side_effect = HttpResponseError("Wrong permissions!")
            controller.disable_subscriptions([UUID(int=8637)])


class TestSettings(TestCase):
    """Tests for the controller.settings module."""

    def test_key_validation(self) -> None:
        self.assertRaises(
            ValueError,
            lambda: controller.settings.Settings(
                API_URL="https://a.b.com",
                PRIVATE_KEY="-----BEGIN OPENSSH PRIVATE KEY-----",
                _env_file=None,
            ),
        )

        self.assertRaises(
            ValueError,
            lambda: controller.settings.Settings(
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
        controller.settings.Settings(
            PRIVATE_KEY=private_key_str,
            API_URL="https://a.b.com",
            LOG_LEVEL="WARNING",
            _env_file=None,
        )


class TestAuth(TestCase):
    """Test the controller.auth module."""

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

        with patch("controller.settings.get_settings") as mock_get_settings:
            mock_get_settings.return_value.PRIVATE_KEY = private_key_str

            bearer = controller.auth.BearerAuth()
            token = bearer.create_access_token()

            payload = jwt.decode(
                token,
                public_key_str,
                algorithms=["RS256"],
                options={"require": ["exp", "sub"]},
            )
            username = payload.get("sub")
            self.assertEqual("controller-app", username)


class TestLoggingUtils(TestCase):
    """Tests for the logutils.py file."""

    def setUp(self) -> None:
        """Forget that Azure Monitor was configured by an earlier test."""
        controller.logutils.configure_telemetry.cache_clear()

    def test_called_twice(self) -> None:
        """configure_azure_monitor() sets up process-wide state.

        Calling it more than once would duplicate the exporting machinery.
        """
        with patch("controller.settings.get_settings") as mock_get_settings:
            mock_get_settings.return_value.APPLICATIONINSIGHTS_CONNECTION_STRING = (
                "my-str"
            )

            with patch("controller.logutils.configure_azure_monitor") as mock_configure:
                controller.logutils.add_log_handler_once("a")
                controller.logutils.add_log_handler_once("a")

        mock_configure.assert_called_once()

    def test_no_connection_string(self) -> None:
        """Without a connection string we should not configure anything."""
        with patch("controller.settings.get_settings") as mock_get_settings:
            mock_get_settings.return_value.APPLICATIONINSIGHTS_CONNECTION_STRING = None

            with patch("controller.logutils.configure_azure_monitor") as mock_configure:
                controller.logutils.add_log_handler_once("c")

        mock_configure.assert_not_called()

    def test_live_metrics_disabled(self) -> None:
        """Continuous streams do not suit a timer-triggered function."""
        with patch("controller.settings.get_settings") as mock_get_settings:
            mock_get_settings.return_value.APPLICATIONINSIGHTS_CONNECTION_STRING = (
                "my-str"
            )

            with patch("controller.logutils.configure_azure_monitor") as mock_configure:
                controller.logutils.add_log_handler_once("d")

        kwargs = mock_configure.call_args.kwargs
        self.assertFalse(kwargs["enable_live_metrics"])
        self.assertFalse(kwargs["enable_performance_counters"])
        self.assertEqual("d", kwargs["logger_name"])

    def test_code_attributes_added(self) -> None:
        """Source location should survive as custom dimensions."""
        record = logging.LogRecord(
            name="e",
            level=logging.WARNING,
            pathname="/somewhere/mymodule.py",
            lineno=42,
            msg="a message",
            args=(),
            exc_info=None,
        )
        record.funcName = "my_function"

        self.assertTrue(controller.logutils.CodeAttributesFilter().filter(record))
        attributes = vars(record)
        self.assertEqual("/somewhere/mymodule.py", attributes["code.file.path"])
        self.assertEqual("my_function", attributes["code.function.name"])
        self.assertEqual(42, attributes["code.line.number"])


if __name__ == "__main__":
    main()
