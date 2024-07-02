"""Tests for Azure functions."""
from datetime import date, datetime, timedelta
from typing import Final
from unittest import TestCase, main
from unittest.mock import MagicMock, call, patch
from uuid import UUID

from azure.mgmt.costmanagement.models import (
    ExportType,
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
    TimeframeType,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import HttpUrl, TypeAdapter

import costmanagement
import monthly_usage
import usage
import utils

HTTP_ADAPTER: Final = TypeAdapter(HttpUrl)


class TestUsage(TestCase):
    """Tests for the usage/__init__.py file."""

    def test_main(self) -> None:
        with patch("usage.get_all_usage") as mock_get_all_usage:
            mock_get_all_usage.return_value = ["usage1", "usage2"]

            with patch("usage.datetime") as mock_datetime:
                now = datetime.now()
                mock_datetime.now.return_value = now

                with patch(
                    "usage.retrieve_and_send_usage"
                ) as mock_retrieve_and_send_usage:
                    with patch("utils.settings.get_settings") as mock_get_settings:
                        mock_get_settings.return_value = utils.settings.Settings(
                            API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
                            PRIVATE_KEY="-----BEGIN OPENSSH "
                            "PRIVATE KEY-----"
                            "abcde"
                            "-----END OPENSSH PRIVATE KEY-----",
                            USAGE_HISTORY_DAYS=2,
                            USAGE_HISTORY_DAYS_OFFSET=1,
                            MGMT_GROUP="mgmt-group",
                            _env_file=None,
                        )

                        with patch("usage.date_range") as mock_date_range:
                            mock_date_range.return_value = [33, 44]

                            mock_timer = MagicMock()
                            mock_timer.past_due = True

                            usage.main(mock_timer)

                            mock_date_range.assert_called_once_with(
                                now - timedelta(days=2), now - timedelta(days=1)
                            )

                        mock_get_all_usage.assert_has_calls(
                            [
                                call(
                                    44,
                                    44,
                                    billing_account_id=None,
                                    mgmt_group="mgmt-group",
                                ),
                                call(
                                    33,
                                    33,
                                    billing_account_id=None,
                                    mgmt_group="mgmt-group",
                                ),
                            ]
                        )
                        mock_retrieve_and_send_usage.assert_has_calls(
                            [
                                call(
                                    HTTP_ADAPTER.validate_python("https://my.host"),
                                    ["usage1", "usage2"],
                                ),
                            ]
                        )


class TestMonthlyUsage(TestCase):
    """Tests for the monthly_usage/__init__.py file."""

    def test_main(self) -> None:
        mock_timer = MagicMock()
        mock_timer.past_due = True

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
            BILLING_ACCOUNT_ID="88111111",
            _env_file=None,
        )

        with patch("monthly_usage.get_all_usage") as mock_get_all, patch(
            "monthly_usage.retrieve_usage"
        ) as mock_retrieve, patch("monthly_usage.date_range") as mock_date_range, patch(
            "monthly_usage.send_usage"
        ) as mock_send, patch(
            "utils.settings.get_settings"
        ) as mock_get_settings:
            mock_date_range.return_value = [0]
            mock_get_settings.return_value = settings
            monthly_usage.main(mock_timer)

            mock_get_all.assert_called_once()
            mock_retrieve.assert_called_once()
            mock_send.assert_called_once()


class TestCostManagement(TestCase):
    """Tests for the costmanagement/__init__.py file."""

    def test_main(self) -> None:
        """Call costmanagement.main, with mock versions of all the functions that it
        calls. Check that each gets called with expected arguments.
        """
        now = datetime(year=2022, month=7, day=11)
        with patch("costmanagement.get_all_usage") as mock_get_all_usage, patch(
            "costmanagement.datetime", autospec=True
        ) as mock_datetime, patch(
            "costmanagement.send_usage"
        ) as mock_send_usage, patch(
            "utils.settings.get_settings"
        ) as mock_get_settings:
            mock_get_all_usage.return_value = ["sub1", "sub2"]
            mock_datetime.now.return_value = now
            mock_get_settings.return_value = utils.settings.Settings(
                API_URL=HTTP_ADAPTER.validate_python("https://my.host"),
                PRIVATE_KEY="-----BEGIN OPENSSH PRIVATE KEY-----"
                "abcde"
                "-----END OPENSSH PRIVATE KEY-----",
                USAGE_HISTORY_DAYS=2,
                USAGE_HISTORY_DAYS_OFFSET=1,
                BILLING_ACCOUNT_ID="789123",
                CM_MGMT_GROUP="my-mgmt-group",
                _env_file=None,
            )
            mock_timer = MagicMock()
            mock_timer.past_due = True

            costmanagement.main(mock_timer)

            mock_datetime.assert_called_once_with(
                year=2022,
                month=1,
                day=1,
            )
            mock_get_all_usage.assert_called_once_with(
                mock_datetime.return_value,
                now,
                "my-mgmt-group",
            )
            mock_send_usage.assert_called_once_with(
                HTTP_ADAPTER.validate_python("https://my.host"),
                ["sub1", "sub2"],
            )

    def test_get_all_usage(self) -> None:
        """Call costmanagement.get_all_usage while mocking the Azure API, check that the
        API gets called as expected.
        """
        # Choose a time period that's a bit more than a year, to cause two calls to the
        # API.
        end_datetime = datetime(year=2022, month=1, day=1)
        start_datetime = end_datetime - timedelta(366)
        # The values we mock the API query to return.
        query_return = [
            (1.0, UUID(int=1), "name1", "currency1"),
            (2.0, UUID(int=2), "name2", "currency2"),
        ]
        # The corresponding return value of get_all_usage.
        expected_total = costmanagement.models.AllCMUsage(
            cm_usage_list=[
                costmanagement.models.CMUsage(
                    subscription_id=i[1],
                    name=i[2],
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    # The total usage should be double that returned by an individual
                    # query, because of the two queries caused by the time range.
                    cost=2 * i[0],
                    billing_currency=i[3],
                )
                for i in query_return
            ]
        )

        with patch("costmanagement.CostManagementClient") as mock_consumption_client:
            mock_list_func = mock_consumption_client.return_value.query.usage
            mock_data = mock_list_func.return_value
            mock_data.rows = query_return
            mock_data.next_link = None

            actual_total = costmanagement.get_all_usage(
                start_datetime, end_datetime, "ea"
            )

            mock_consumption_client.assert_called_once_with(
                credential=costmanagement.CREDENTIALS,
            )
            query_type = ExportType.ACTUAL_COST
            query_timeframe = TimeframeType.CUSTOM
            query_dataset = QueryDataset(
                granularity=None,
                grouping=[
                    QueryGrouping(
                        type="Dimension",
                        name="SubscriptionId",
                    ),
                    QueryGrouping(
                        type="Dimension",
                        name="SubscriptionName",
                    ),
                ],
                aggregation={
                    "totalCost": QueryAggregation(
                        name="Cost",
                        function="Sum",
                    )
                },
            )

            parameters1 = QueryDefinition(
                time_period=QueryTimePeriod(
                    from_property=start_datetime,
                    to=start_datetime + timedelta(364),
                ),
                dataset=query_dataset,
                type=query_type,
                timeframe=query_timeframe,
            )
            parameters2 = QueryDefinition(
                time_period=QueryTimePeriod(
                    from_property=start_datetime + timedelta(365),
                    to=end_datetime,
                ),
                dataset=query_dataset,
                type=query_type,
                timeframe=query_timeframe,
            )
            scope = "/providers/Microsoft.Management/managementGroups/ea"
            self.assertEqual(mock_list_func.call_args_list[0].kwargs["scope"], scope)
            self.assertEqual(
                mock_list_func.call_args_list[0].kwargs["parameters"].serialize(),
                parameters1.serialize(),
            )
            self.assertEqual(mock_list_func.call_args_list[1].kwargs["scope"], scope)
            self.assertEqual(
                mock_list_func.call_args_list[1].kwargs["parameters"].serialize(),
                parameters2.serialize(),
            )
            self.assertEqual(mock_list_func.call_count, 2)

        self.assertEqual(expected_total, actual_total)

    def test_send_usage(self) -> None:
        """Call costmanagement.send_usage, while mocking the RCTab POST end point.
        Check that both an error response and a success response are processed
        correctly.
        """
        end_datetime = date.today()
        start_datetime = end_datetime - timedelta(days=364)
        # Example usage in the final, processed format
        local_usage = costmanagement.models.AllCMUsage(
            cm_usage_list=[
                costmanagement.models.CMUsage(
                    subscription_id=UUID(int=1),
                    name="sub1",
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    cost=12.0,
                    billing_currency="GBP",
                ),
                costmanagement.models.CMUsage(
                    subscription_id=UUID(int=2),
                    name="sub2",
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    cost=144.0,
                    billing_currency="GBP",
                ),
            ]
        )
        expected_data = local_usage.model_dump_json().encode("utf-8")

        with patch("costmanagement.BearerAuth") as mock_auth:
            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 300
                mock_response.text = "some-mock-text"
                mock_post.return_value = mock_response

                with patch("costmanagement.logger.warning") as mock_log:

                    def send():
                        costmanagement.send_usage(
                            "https://123.234.345.456",
                            local_usage,
                        )

                    self.assertRaises(RuntimeError, send)

                    expected_call = call(
                        "https://123.234.345.456/accounting/all-cm-usage",
                        data=expected_data,
                        auth=mock_auth.return_value,
                        timeout=60,
                    )
                    self.assertEqual(costmanagement.RETRY_ATTEMPTS, 5)
                    mock_post.assert_has_calls(
                        [expected_call] * costmanagement.RETRY_ATTEMPTS
                    )

                    # Check the most recent call to logging.warning().
                    mock_log.assert_called_with(
                        "Failed to send CMUsage. Response code: %d. "
                        "Response text: %s.",
                        300,
                        "some-mock-text",
                    )

            with patch("requests.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_post.return_value = mock_response

                with patch("costmanagement.logger.warning"):
                    costmanagement.send_usage(
                        "https://123.234.345.456",
                        local_usage,
                    )

                    mock_post.assert_called_once_with(
                        "https://123.234.345.456/accounting/all-cm-usage",
                        data=expected_data,
                        auth=mock_auth.return_value,
                        timeout=60,
                    )


if __name__ == "__main__":
    main()
