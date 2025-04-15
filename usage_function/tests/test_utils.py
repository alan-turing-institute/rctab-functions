"""Tests for function app utils."""

import logging
from datetime import date, datetime, timedelta
from typing import Final
from unittest import TestCase, main
from unittest.mock import MagicMock, call, patch
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import HttpUrl, TypeAdapter
from rctab_models import models

import utils.logutils
import utils.settings
import utils.usage

HTTP_ADAPTER: Final = TypeAdapter(HttpUrl)

# pylint: disable=attribute-defined-outside-init, too-many-instance-attributes


class DummyAzureUsage:
    cost: float
    quantity: int
    total_cost: float
    unit_price: float
    effective_price: float
    reservation_id: str

    def __init__(self) -> None:
        # pylint: disable=invalid-name
        self.id = "1"
        # pylint: enable=invalid-name
        self.subscription_id = str(UUID(int=0))
        self.date = date.today()
        super().__init__()


class TestUsageUtils(TestCase):
    """Tests for the utils.usage module."""

    def test_get_all_usage(self) -> None:
        # Mock usage data, for when we patch usage_details.list
        expected = [1, 2]

        with patch("utils.usage.ConsumptionManagementClient") as mock_client:
            mock_list_func = mock_client.return_value.usage_details.list
            mock_list_func.return_value = expected

            jan_tenth = datetime(2021, 1, 10, 1, 1, 1, 1)
            actual = list(
                utils.usage.get_all_usage(
                    jan_tenth - timedelta(days=5),
                    jan_tenth,
                    mgmt_group="some-mgmt-group",
                )
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

    def test_retrieve_and_send_usage(self) -> None:
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
                    with self.assertRaises(RuntimeError):
                        utils.usage.retrieve_and_send_usage(
                            HTTP_ADAPTER.validate_python("https://123.123.123.123"),
                            [example_usage_detail],  # type: ignore
                        )

                    usage = models.Usage(**usage_dict)

                    expected_data = (
                        models.AllUsage(usage_list=[usage])
                        .model_dump_json()
                        .encode("utf-8")
                    )

                    expected_call = call(
                        "https://123.123.123.123/accounting/all-usage",
                        data=expected_data,
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
                        HTTP_ADAPTER.validate_python("https://123.123.123.123"),
                        [example_usage_detail],  # type: ignore
                    )

                    usage = models.Usage(**usage_dict)

                    expected_data = (
                        models.AllUsage(usage_list=[usage])
                        .model_dump_json()
                        .encode("utf-8")
                    )

                    mock_post.assert_called_once_with(
                        "https://123.123.123.123/accounting/all-usage",
                        data=expected_data,
                        auth=mock_auth.return_value,
                        timeout=60,
                    )

    def test_retrieve_usage_1(self) -> None:
        """Check the retrieve usage function sets amortised cost to 0."""
        # pylint: disable=invalid-name
        self.maxDiff = None
        # pylint: enable=invalid-name

        datum_1 = DummyAzureUsage()
        datum_1.quantity = 1
        datum_1.cost = 1
        datum_1.unit_price = 1
        datum_1.effective_price = 1

        datum_2 = DummyAzureUsage()
        datum_2.quantity = 1
        datum_2.cost = 1
        datum_2.unit_price = 1
        datum_2.effective_price = 1

        actual = utils.usage.retrieve_usage((datum_1, datum_2))  # type: ignore
        expected = models.Usage(
            id="1",
            subscription_id=UUID(int=0),
            quantity=2,
            cost=2,
            date=date.today(),
            amortised_cost=0,
            total_cost=2,
            unit_price=2,
            effective_price=2,
        )
        self.assertListEqual([expected], actual)

    def test_retrieve_usage_2(self) -> None:
        """Check the retrieve usage function sets cost to 0."""
        # pylint: disable=invalid-name
        self.maxDiff = None
        # pylint: enable=invalid-name

        datum_1 = DummyAzureUsage()
        datum_1.reservation_id = "x"
        datum_1.quantity = 1
        datum_1.cost = 1
        datum_1.total_cost = 1
        datum_1.unit_price = 1
        datum_1.effective_price = 1

        datum_2 = DummyAzureUsage()
        datum_2.reservation_id = "x"
        datum_2.quantity = 1
        datum_2.cost = 1
        datum_2.total_cost = 1
        datum_2.unit_price = 1
        datum_2.effective_price = 1

        actual = utils.usage.retrieve_usage((datum_1, datum_2))  # type: ignore
        expected = utils.usage.models.Usage(
            reservation_id="x",
            id="1",
            subscription_id=UUID(int=0),
            quantity=2,
            cost=0,
            date=date.today(),
            amortised_cost=2,
            total_cost=2,
            unit_price=2,
            effective_price=2,
        )
        self.assertListEqual([expected], actual)

    def test_retrieve_usage_3(self) -> None:
        """Check the retrieve usage function sets cost to 0."""
        # pylint: disable=invalid-name
        self.maxDiff = None
        # pylint: enable=invalid-name

        datum_1 = DummyAzureUsage()
        datum_1.reservation_id = "x"
        datum_1.quantity = 1
        datum_1.cost = 1
        datum_1.total_cost = 1
        datum_1.unit_price = 1
        datum_1.effective_price = 1

        # an item without a reservation_id
        datum_2 = DummyAzureUsage()
        datum_2.quantity = 1
        datum_2.cost = 1
        datum_2.total_cost = 1
        datum_2.unit_price = 1
        datum_2.effective_price = 1

        actual = utils.usage.retrieve_usage((datum_1, datum_2))  # type: ignore
        expected_item_1 = utils.usage.models.Usage(
            reservation_id="x",
            id="1",
            subscription_id=UUID(int=0),
            quantity=1,
            cost=0,
            date=date.today(),
            amortised_cost=1,
            total_cost=1,
            unit_price=1,
            effective_price=1,
        )
        # without a reservation id: cost set to 1, amortise_dcost is unset.
        expected_item_2 = utils.usage.models.Usage(
            id="1",
            subscription_id=UUID(int=0),
            quantity=1,
            cost=1,
            date=date.today(),
            total_cost=1,
            unit_price=1,
            effective_price=1,
            amortised_cost=0.0,
        )

        self.assertListEqual([expected_item_1, expected_item_2], actual)

    def test_date_range(self) -> None:
        start = datetime(year=2021, month=11, day=1, hour=2)
        end = datetime(year=2021, month=11, day=2, hour=2)

        actual = list(utils.usage.date_range(start, end))
        expected = [
            datetime(year=2021, month=11, day=1),
            datetime(year=2021, month=11, day=2),
        ]
        self.assertListEqual(expected, actual)

    def test_combine_items(self) -> None:
        """Test that combine_items works as expected."""
        existing_item = models.Usage(
            id="someid",
            date=date.today(),
            cost=1,
            total_cost=1,
            subscription_id=UUID(int=0),
        )
        new_item = models.Usage(
            id="someid",
            date=date.today(),
            cost=1,
            total_cost=1,
            subscription_id=UUID(int=0),
        )

        utils.usage.combine_items(existing_item, new_item)
        expected = models.Usage(
            id="someid",
            date=date.today(),
            quantity=0,
            effective_price=0,
            cost=2,
            amortised_cost=0,
            total_cost=2,
            unit_price=0,
            subscription_id=UUID(int=0),
        )
        self.assertEqual(expected, existing_item)


class TestCompressItems(TestCase):
    """Tests for the utils.usage.compress_items function."""

    # todo: can we combine effective price?
    # todo: warnable fields (ones we presume are the same but could not be).

    def test_compress_items_1(self) -> None:
        """Check that we sum the costs."""
        # pylint: disable=invalid-name
        self.maxDiff = None
        # pylint: enable=invalid-name
        items_a = [
            models.Usage(
                id="someid",
                date=date.today(),
                cost=1,
                total_cost=1,
                subscription_id=UUID(int=0),
            ),
            models.Usage(
                id="someid",
                date=date.today(),
                cost=1,
                total_cost=1,
                subscription_id=UUID(int=0),
            ),
            models.Usage(
                id="someid",
                date=date.today(),
                amortised_cost=1,
                total_cost=1,
                subscription_id=UUID(int=0),
                reservation_id="somereservation",
            ),
            models.Usage(
                id="someid",
                date=date.today(),
                amortised_cost=1,
                total_cost=1,
                subscription_id=UUID(int=0),
                reservation_id="somereservation",
            ),
        ]

        actual = utils.usage.compress_items(items_a)

        expected = [
            models.Usage(
                id="someid",
                date=date.today(),
                cost=2,
                total_cost=2,
                subscription_id=UUID(int=0),
                amortised_cost=0.0,
                effective_price=0.0,
                unit_price=0.0,
                quantity=0,
            ),
            models.Usage(
                id="someid",
                date=date.today(),
                amortised_cost=2,
                total_cost=2,
                subscription_id=UUID(int=0),
                reservation_id="somereservation",
                cost=0.0,
                effective_price=0.0,
                unit_price=0.0,
                quantity=0,
            ),
        ]
        self.assertListEqual(expected, actual)

    def test_compress_items_2(self) -> None:
        """Check that we sum the costs."""
        items_a = [
            models.Usage(
                id="someid",
                date=date.today(),
                cost=1,
                total_cost=1,
                subscription_id=UUID(int=0),
                reservation_id="somereservation",
            ),
            models.Usage(
                id="someid",
                date=date.today(),
                cost=1,
                total_cost=1,
                subscription_id=UUID(int=0),
            ),
        ]

        actual = utils.usage.compress_items(items_a)

        expected = [
            models.Usage(
                id="someid",
                date=date.today(),
                cost=1,
                total_cost=1,
                subscription_id=UUID(int=0),
                reservation_id="somereservation",
            ),
            models.Usage(
                id="someid",
                date=date.today(),
                cost=1,
                total_cost=1,
                subscription_id=UUID(int=0),
            ),
        ]
        self.assertListEqual(expected, actual)


class TestSettings(TestCase):
    """Tests for the utils.settings module."""

    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    private_key_str = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    def test_valid_settings(self) -> None:
        """Check that we can make a Settings instance, given the right arguments."""

        utils.settings.Settings(
            PRIVATE_KEY=self.private_key_str,
            API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
            USAGE_HISTORY_DAYS=10,
            USAGE_HISTORY_DAYS_OFFSET=1,
            LOG_LEVEL="WARNING",
            MGMT_GROUP="some-mgmt-group",
            _env_file=None,
        )

    def test_default_settings(self) -> None:
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
            API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
            BILLING_ACCOUNT_ID="12345",
            _env_file=None,
        )

        self.assertEqual(settings.USAGE_HISTORY_DAYS_OFFSET, 0)
        self.assertEqual(settings.USAGE_HISTORY_DAYS, 3)
        self.assertEqual(settings.LOG_LEVEL, "WARNING")
        self.assertIsNone(settings.CM_MGMT_GROUP)
        self.assertIsNone(settings.MGMT_GROUP)

    def test_key_validation(self) -> None:
        with self.assertRaisesRegex(
            ValueError, 'Expected key to end with "-----END OPENSSH PRIVATE KEY-----".'
        ):
            utils.settings.Settings(
                API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
                PRIVATE_KEY="-----BEGIN OPENSSH PRIVATE KEY-----",
                _env_file=None,
            )

        with self.assertRaisesRegex(
            ValueError,
            'Expected key to start with "-----BEGIN OPENSSH PRIVATE KEY-----".',
        ):
            utils.settings.Settings(
                API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
                PRIVATE_KEY="-----END OPENSSH PRIVATE KEY-----",
                _env_file=None,
            )

        with self.assertRaisesRegex(
            ValueError,
            "Exactly one of MGMT_GROUP and BILLING_ACCOUNT_ID should be empty.",
        ):
            utils.settings.Settings(
                PRIVATE_KEY=self.private_key_str,
                API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
                MGMT_GROUP="x",
                BILLING_ACCOUNT_ID="y",
                _env_file=None,
            )

        with self.assertRaisesRegex(
            ValueError,
            "Exactly one of MGMT_GROUP and BILLING_ACCOUNT_ID should be empty.",
        ):
            utils.settings.Settings(
                PRIVATE_KEY=self.private_key_str,
                API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
                _env_file=None,
            )


class TestLoggingUtils(TestCase):
    def test_called_twice(self) -> None:
        """Adding multiple loggers could cause large storage bills."""
        with patch("utils.settings.get_settings") as mock_get_settings:
            mock_get_settings.return_value.CENTRAL_LOGGING_CONNECTION_STRING = "my-str"

            with patch("utils.logutils.AzureLogHandler", new=MagicMock):
                utils.logutils.add_log_handler_once("a")
                utils.logutils.add_log_handler_once("a")
        handlers = logging.getLogger("a").handlers
        self.assertEqual(1, len(handlers))


if __name__ == "__main__":
    main()
