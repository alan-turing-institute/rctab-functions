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

    def test_get_all_usage_billing_account(self) -> None:
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
                    billing_account_id="1:2",
                )
            )

            mock_client.assert_called_once_with(
                credential=utils.usage.CREDENTIALS,
                subscription_id=str(UUID(int=0)),
            )

            mock_list_func.assert_called_once_with(
                scope="/providers/Microsoft.Billing/billingAccounts/1:2",
                filter="properties/usageEnd ge '2021-01-05T01:01:01Z' and "
                "properties/usageEnd le '2021-01-10T01:01:01Z'",
                metric="AmortizedCost",
            )

        self.assertListEqual(expected, actual)

    def test_get_all_usage_billing_profile(self) -> None:
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
                    billing_account_id="1:2",
                    billing_profile_id="3",
                )
            )

            mock_client.assert_called_once_with(
                credential=utils.usage.CREDENTIALS,
                subscription_id=str(UUID(int=0)),
            )

            mock_list_func.assert_called_once_with(
                scope="/providers/Microsoft.Billing/billingAccounts/1:2/billingProfiles/3",
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
            # Patch POST so that it returns an error (300 status code).
            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 300
                mock_response.text = "some-mock-text"
                mock_post.return_value = mock_response

                sept_2021 = date(2021, 9, 1)

                with patch("utils.usage.logging.warning") as mock_log:
                    with self.assertRaises(RuntimeError):
                        utils.usage.retrieve_and_send_usage(
                            HTTP_ADAPTER.validate_python("https://123.123.123.123"),
                            [example_usage_detail],  # type: ignore
                            sept_2021,
                            sept_2021,
                        )

                    usage = models.Usage(**usage_dict)

                    expected_data = (
                        models.AllUsage(
                            usage_list=[usage],
                            start_date=sept_2021,
                            end_date=sept_2021,
                        )
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

            # Patch POST so that it returns a success (200 status code).
            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_post.return_value = mock_response

                with patch("usage.logging.warning"):
                    utils.usage.retrieve_and_send_usage(
                        HTTP_ADAPTER.validate_python("https://123.123.123.123"),
                        [example_usage_detail],  # type: ignore
                        sept_2021,
                        sept_2021,
                    )

                    usage = models.Usage(**usage_dict)

                    expected_data = (
                        models.AllUsage(
                            usage_list=[usage],
                            start_date=sept_2021,
                            end_date=sept_2021,
                        )
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

    def test_usage_detail_to_usage_model(self) -> None:
        cost_detail = {
            "\ufeffinvoiceId": "H123",
            "previousInvoiceId": "",
            "billingAccountId": "00000000-0000-0000-0000-000000000058",
            "billingAccountName": "",
            "billingProfileId": "O1O1-AAAA-BBB-CCC",
            "billingProfileName": "My Billing Profile",
            "invoiceSectionId": "00000000-0000-0000-0000-000000000059",
            "invoiceSectionName": "My Invoice Section",
            "resellerName": "",
            "resellerMpnId": "",
            "costCenter": "AB  ",
            "billingPeriodEndDate": "01/13/2026",
            "billingPeriodStartDate": "01/13/2026",
            "servicePeriodEndDate": "01/22/2026",
            "servicePeriodStartDate": "01/22/2026",
            "date": "01/25/2026",
            "serviceFamily": "SaaS",
            "productOrderId": "00000000-0000-0000-0000-00000000005a",
            "productOrderName": "Some Product Order",
            "consumedService": "",
            "meterId": "",
            "meterName": "",
            "meterCategory": "SaaS",
            "meterSubCategory": "My Sub Category",
            "meterRegion": "",
            "ProductId": "ABC123",
            "ProductName": "Some Product Name",
            "SubscriptionId": "00000000-0000-0000-0000-00000000005b",
            "subscriptionName": "My Subscription Name",
            "publisherType": "Marketplace",
            "publisherId": "21212121",
            "publisherName": "Some Publisher Name",
            "resourceGroupName": "my-resource-group",
            "ResourceId": (
                "/subscriptions/00000000-0000-0000-0000-00000000005b/"
                "resourceGroups/my-resource-group/providers/"
                "Microsoft.something/resources/my-resource"
            ),
            "resourceLocation": "",
            "location": "",
            "effectivePrice": "100",
            "quantity": "1",
            "unitOfMeasure": "",
            "chargeType": "Purchase",
            "billingCurrency": "GBP",
            "pricingCurrency": "GBP",
            "costInBillingCurrency": "100",
            "costInPricingCurrency": "100",
            "costInUsd": "120",
            "paygCostInBillingCurrency": "100",
            "paygCostInUsd": "120",
            "exchangeRatePricingToBilling": "1",
            "exchangeRateDate": "",
            "isAzureCreditEligible": "False",
            "serviceInfo1": "",
            "serviceInfo2": "",
            "additionalInfo": "",
            "tags": "",
            "PayGPrice": "100",
            "frequency": "Some frequency",
            "term": "",
            "reservationId": "",
            "reservationName": "",
            "pricingModel": "Some pricing",
            "unitPrice": "100",
            "costAllocationRuleName": "",
            "benefitId": "",
            "benefitName": "",
            "provider": "Azure",
        }

        converted = utils.usage.usage_row_to_usage_model(cost_detail)
        self.assertEqual(
            models.Usage(
                id="",
                subscription_id=UUID(int=91),
                date=date(year=2026, month=1, day=25),
                billing_account_id="00000000-0000-0000-0000-000000000058",
                billing_account_name="",
                billing_profile_id="O1O1-AAAA-BBB-CCC",
                billing_profile_name="My Billing Profile",
                billing_period_start_date=datetime(year=2026, month=1, day=13),
                billing_period_end_date=datetime(year=2026, month=1, day=13),
                subscription_name="My Subscription Name",
                product="ABC123-Some Product Name",
                meter_id="--SaaS-My Sub Category-",
                total_cost=100,
                cost=100,
                amortised_cost=0,
                unit_price=100,
                quantity=1,
                effective_price=100,
                billing_currency="GBP",
                resource_location="",
                consumed_service="",
                resource_id=(
                    "/subscriptions/00000000-0000-0000-0000-00000000005b/"
                    "resourceGroups/my-resource-group/providers/"
                    "Microsoft.something/resources/my-resource"
                ),
                service_info1="",
                service_info2="",
                additional_info="",
                invoice_section="00000000-0000-0000-0000-000000000059-My Invoice Section",
                cost_center="AB  ",
                resource_group="my-resource-group",
                reservation_id="",
                reservation_name="",
                product_order_id="00000000-0000-0000-0000-00000000005a",
                offer_id=None,
                is_azure_credit_eligible=False,
                term="",
                publisher_name="Some Publisher Name",
                publisher_type="Marketplace",
                plan_name=None,
                charge_type="Purchase",
                frequency="Some frequency",
                monthly_upload=None,
            ),
            converted,
        )

    def test_us_to_iso_date(self) -> None:
        self.assertEqual("2021-12-24", utils.usage.us_date_to_iso("12/24/2021"))


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

    def test_maximal_settings(self) -> None:
        """Check that we can make a Settings instance, given the right arguments."""
        utils.settings.Settings(
            API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
            PRIVATE_KEY=self.private_key_str,
            USAGE_HISTORY_DAYS=10,
            USAGE_HISTORY_DAYS_OFFSET=1,
            LOG_LEVEL="WARNING",
            CM_MGMT_GROUP="somegroup",
            BILLING_ACCOUNT_ID="someid",
            BILLING_PROFILE_ID="someotherid",
            CENTRAL_LOGGING_CONNECTION_STRING="someconnectionstring",
            _env_file=None,
        )

    def test_default_settings(self) -> None:
        settings = utils.settings.Settings(
            PRIVATE_KEY=self.private_key_str,
            API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
            BILLING_ACCOUNT_ID="12345",
            _env_file=None,
        )

        self.assertEqual(settings.USAGE_HISTORY_DAYS_OFFSET, 0)
        self.assertEqual(settings.USAGE_HISTORY_DAYS, 3)
        self.assertEqual(settings.LOG_LEVEL, "WARNING")
        self.assertIsNone(settings.CM_MGMT_GROUP)

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
