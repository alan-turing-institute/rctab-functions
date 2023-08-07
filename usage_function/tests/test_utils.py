"""Tests for function app utils."""
from datetime import datetime, timedelta
from unittest import TestCase, main
from unittest.mock import MagicMock, call, patch
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

import utils


class TestUsage(TestCase):
    """Tests for the utils.usage module."""

    def test_get_all_usage(self):
        # Mock usage data, for when we patch usage_details.list
        expected = [1, 2]

        with patch("utils.usage.ConsumptionManagementClient") as mock_client:
            mock_list_func = mock_client.return_value.usage_details.list
            mock_list_func.return_value = expected

            jan_tenth = datetime(2021, 1, 10, 1, 1, 1, 1)
            actual = utils.usage.get_all_usage(
                jan_tenth - timedelta(days=5),
                jan_tenth,
                mgmt_group="some-mgmt-group",
            )

            mock_client.assert_called_once_with(
                credential=utils.usage.CREDENTIALS,
                subscription_id=str(UUID(int=0)),
            )

            mock_list_func.assert_called_once_with(
                scope="/providers/Microsoft.Management"
                "/managementGroups/some-mgmt-group",
                filter="properties/usageEnd ge '2021-01-05T01:01:01Z' and "
                "properties/usageEnd le '2021-01-10T01:01:01Z'",
                metric="AmortizedCost",
            )

        self.assertListEqual(expected, actual)

    def test_retrieve_and_send_usage(self):
        usage_dict = {
            "additional_properties": {},
            "id": "some-id",
            "name": "00000000-0000-0000-0000-00000000000b",
            "type": "Microsoft.Consumption/usageDetails",
            "tags": None,
            "kind": "legacy",
            "billing_account_id": "111111",
            "billing_account_name": "My Org Name",
            "billing_period_start_date": datetime(2021, 9, 1, 0, 0),
            "billing_period_end_date": datetime(2021, 9, 30, 0, 0),
            "billing_profile_id": "111111",
            "billing_profile_name": "My Org Name",
            "account_owner_id": "me@my.org",
            "account_name": "My Acct Name",
            "subscription_id": "00000000-0000-0000-0000-000000000016",
            "subscription_name": "My Subscription",
            "date": datetime(2021, 9, 1, 0, 0),
            "product": "Azure Defender for Resource Manager - Standard",
            "part_number": "AAH-1234",
            "meter_id": "00000000-0000-0000-0000-000000000017",
            "meter_details": None,
            "quantity": 0.001,
            "effective_price": 0.0,
            "cost": 0.0,
            "amortised_cost": 0.0,
            "total_cost": 0.0,
            "unit_price": 2.1,
            "billing_currency": "GBP",
            "resource_location": "Unassigned",
            "consumed_service": "Microsoft.Security",
            "resource_id": "some-resource-id",
            "resource_name": "Arm",
            "service_info1": None,
            "service_info2": None,
            "additional_info": None,
            "invoice_section": "Invoice Section",
            "cost_center": None,
            "resource_group": None,
            "reservation_id": None,
            "reservation_name": None,
            "product_order_id": None,
            "product_order_name": None,
            "offer_id": "Offer ID",
            "is_azure_credit_eligible": True,
            "term": None,
            "publisher_name": None,
            "publisher_type": "Azure",
            "plan_name": None,
            "charge_type": "Usage",
            "frequency": "UsageBased",
        }

        # Manually mock the Usage class.
        example_usage_detail = type(
            "MyUsage",
            (object,),
            usage_dict,
        )

        with patch("utils.usage.BearerAuth") as mock_auth:
            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 300
                mock_response.text = "some-mock-text"
                mock_post.return_value = mock_response

                with patch("utils.usage.logging.warning") as mock_log:

                    def send():
                        utils.usage.retrieve_and_send_usage(
                            "https://123.234.345.456", [example_usage_detail]
                        )

                    self.assertRaises(RuntimeError, send)

                    usage = utils.usage.models.Usage(**usage_dict)

                    expected_json = utils.usage.models.AllUsage(
                        usage_list=[usage]
                    ).json()

                    expected_call = call(
                        "https://123.234.345.456/accounting/all-usage",
                        expected_json,
                        auth=mock_auth.return_value,
                        timeout=60,
                    )
                    mock_post.assert_has_calls([expected_call] * 2)

                    # Check the most recent call to logging.warning().
                    mock_log.assert_called_with(
                        "Failed to send Usage. Response code: %d. Response text: %s",
                        300,
                        "some-mock-text",
                    )

            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_post.return_value = mock_response

                with patch("usage.logging.warning"):
                    utils.usage.retrieve_and_send_usage(
                        "https://123.234.345.456", [example_usage_detail]
                    )

                    usage = utils.usage.models.Usage(**usage_dict)

                    expected_json = utils.usage.models.AllUsage(
                        usage_list=[usage]
                    ).json()

                    mock_post.assert_called_once_with(
                        "https://123.234.345.456/accounting/all-usage",
                        expected_json,
                        auth=mock_auth.return_value,
                        timeout=60,
                    )

    def test_get_subs(self):
        with patch("utils.usage.SubscriptionClient") as mock_sub_client:
            mock_sub = MagicMock()
            mock_sub.as_dict.return_value = {1: 2, 3: 4}

            mock_list_func = mock_sub_client.return_value.subscriptions.list
            mock_list_func.return_value = [mock_sub]

            actual = utils.usage.get_subs()
            expected = [{1: 2, 3: 4}]
            self.assertListEqual(expected, actual)

    def test_date_range(self):
        start = datetime(year=2021, month=11, day=1, hour=2)
        end = datetime(year=2021, month=11, day=2, hour=2)

        actual = list(utils.usage.date_range(start, end))
        expected = [
            datetime(year=2021, month=11, day=1),
            datetime(year=2021, month=11, day=2),
        ]
        self.assertListEqual(expected, actual)


class TestSettings(TestCase):
    """Tests for the utils.settings module."""

    def test_valid_settings(self):
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
        utils.settings.Settings(
            PRIVATE_KEY=private_key_str,
            API_URL="https://a.b.com",
            BILLING_ACCOUNT_ID="111111",
            USAGE_HISTORY_DAYS=10,
            USAGE_HISTORY_DAYS_OFFSET=1,
            LOG_LEVEL="WARNING",
            _env_file=None,
        )

    def test_default_settings(self):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        private_key_str = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.OpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        settings = utils.settings.Settings(
            PRIVATE_KEY=private_key_str,
            API_URL="https://a.b.com",
            BILLING_ACCOUNT_ID="111111",
            _env_file=None,
        )

        self.assertEqual(settings.USAGE_HISTORY_DAYS_OFFSET, 0)
        self.assertEqual(settings.USAGE_HISTORY_DAYS, 3)
        self.assertEqual(settings.LOG_LEVEL, "WARNING")

    def test_key_validation(self):
        self.assertRaises(
            ValueError,
            lambda: utils.settings.Settings(
                API_URL="https://a.b.com",
                PRIVATE_KEY="-----BEGIN OPENSSH PRIVATE KEY-----",
                _env_file=None,
            ),
        )

        self.assertRaises(
            ValueError,
            lambda: utils.settings.Settings(
                API_URL="https://a.b.com",
                PRIVATE_KEY="-----END OPENSSH PRIVATE KEY-----",
                _env_file=None,
            ),
        )


if __name__ == "__main__":
    main()
