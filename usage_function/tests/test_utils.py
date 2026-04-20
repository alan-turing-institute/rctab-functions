"""Tests for function app utils."""

import csv
import logging
from datetime import date, datetime, timedelta
from io import TextIOWrapper
from typing import Final
from unittest import TestCase, main
from unittest.mock import MagicMock, call, patch
from uuid import UUID

from azure.mgmt.costmanagement.models import (
    CostDetailsMetricType,
    CostDetailsTimePeriod,
    GenerateCostDetailsReportRequestDefinition,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import HttpUrl, TypeAdapter
from rctab_models import models

import utils.logutils
import utils.settings
import utils.usage
from utils.usage import usage_row_to_usage_model

HTTP_ADAPTER: Final = TypeAdapter(HttpUrl)

# pylint: disable=attribute-defined-outside-init, too-many-instance-attributes


class TestUsageUtils(TestCase):
    """Tests for the utils.usage module."""

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

    def test_get_all_usage_billing_account(self) -> None:
        with patch("utils.usage.CostManagementClient") as mock_client:
            mock_tmp = mock_client.return_value
            mock_create = mock_tmp.generate_cost_details_report.begin_create_operation
            mock_result = MagicMock()
            mock_result.blobs = [MagicMock()]
            mock_result.blobs[0].blob_link = "https://blob.url"
            mock_create.return_value.result.return_value = mock_result

            jan_tenth = date(2021, 1, 10)
            actual = list(
                utils.usage.get_all_usage(
                    jan_tenth - timedelta(days=5),
                    jan_tenth,
                    billing_account_id="1:2",
                )
            )

            mock_client.assert_called_once_with(
                utils.usage.CREDENTIALS,
            )

            mock_create.assert_called_once_with(
                scope="providers/Microsoft.Billing/billingAccounts/1:2",
                parameters=GenerateCostDetailsReportRequestDefinition(
                    time_period=CostDetailsTimePeriod(
                        start="2021-01-05", end="2021-01-10"
                    ),
                    metric=CostDetailsMetricType.AMORTIZED_COST_COST_DETAILS_METRIC_TYPE,
                ),
            )

        self.assertListEqual(["https://blob.url"], actual)

    def test_get_all_usage_billing_profile(self) -> None:
        with patch("utils.usage.CostManagementClient") as mock_client:
            mock_tmp = mock_client.return_value
            mock_create = mock_tmp.generate_cost_details_report.begin_create_operation
            mock_result = MagicMock()
            mock_result.blobs = [MagicMock()]
            mock_create.return_value.result.return_value = mock_result

            jan_tenth = date(2021, 1, 10)
            utils.usage.get_all_usage(
                jan_tenth - timedelta(days=5),
                jan_tenth,
                billing_account_id="A:B",
                billing_profile_id="C",
            )

            mock_create.assert_called_once_with(
                scope="providers/Microsoft.Billing/billingAccounts/A:B/billingProfiles/C",
                parameters=GenerateCostDetailsReportRequestDefinition(
                    time_period=CostDetailsTimePeriod(
                        start="2021-01-05", end="2021-01-10"
                    ),
                    metric=CostDetailsMetricType.AMORTIZED_COST_COST_DETAILS_METRIC_TYPE,
                ),
            )

    def test_send_usage(self) -> None:

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
                        utils.usage.send_usage(
                            HTTP_ADAPTER.validate_python("https://123.123.123.123"),
                            [],
                            sept_2021,
                            sept_2021,
                        )

                    expected_data = (
                        models.AllUsage(
                            usage_list=[],
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
                    utils.usage.send_usage(
                        HTTP_ADAPTER.validate_python("https://123.123.123.123"),
                        [],
                        sept_2021,
                        sept_2021,
                    )

                    mock_post.assert_called_once_with(
                        "https://123.123.123.123/accounting/all-usage",
                        data=expected_data,
                        auth=mock_auth.return_value,
                        timeout=60,
                    )

    def test_row_to_model_1(self) -> None:
        """Check the retrieve usage function sets amortised cost."""
        # pylint: disable=invalid-name
        self.maxDiff = None
        # pylint: enable=invalid-name

        actual = utils.usage.usage_row_to_usage_model(
            {
                **self.cost_detail,
                **{
                    "reservationId": "x",
                },
            }
        )
        self.assertEqual(actual.amortised_cost, 100)
        self.assertEqual(actual.cost, 0.0)

    def test_row_to_model_2(self) -> None:
        """Check the retrieve usage function sets cost."""
        # pylint: disable=invalid-name
        self.maxDiff = None
        # pylint: enable=invalid-name

        actual = utils.usage.usage_row_to_usage_model(
            {
                **self.cost_detail,
                **{
                    "reservationId": "",
                },
            }
        )
        self.assertEqual(actual.amortised_cost, 0.0)
        self.assertEqual(actual.cost, 100)

    def test_retrieve_usage(self) -> None:
        """Check the retrieve usage function sets cost."""
        # pylint: disable=invalid-name
        self.maxDiff = None
        # pylint: enable=invalid-name

        def mock_readinto(open_file):
            """To replace that of the StorageStreamDownloader."""
            # Open_file is already opened with mode "wb".
            text_stream = TextIOWrapper(
                open_file, encoding="utf-8", newline="", write_through=True
            )

            writer = csv.DictWriter(text_stream, fieldnames=self.cost_detail.keys())
            writer.writeheader()
            writer.writerow(self.cost_detail)

            text_stream.flush()

        with patch("utils.usage.BlobClient", autospec=True) as client:
            blob = client.from_blob_url.return_value
            blob.download_blob.return_value.readinto = mock_readinto
            actual = utils.usage.retrieve_usage(["https://blob.url"])
            client.from_blob_url.assert_called_once_with("https://blob.url")

        self.assertEqual([usage_row_to_usage_model(self.cost_detail)], actual)

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

        converted = utils.usage.usage_row_to_usage_model(self.cost_detail)
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
