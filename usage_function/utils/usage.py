"""Utils for collecting and sending Azure usage data."""

import copy
import csv
import logging
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any, Generator, Iterable, Optional, cast

import requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.consumption.models import UsageDetail
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    BlobInfo,
    GenerateCostDetailsReportRequestDefinition,
    CostDetailsTimePeriod,
    CostDetailsMetricType,
)
from azure.storage.blob import BlobClient
from pydantic import HttpUrl
from pydantic_core import ValidationError
from rctab_models import models

from utils.auth import BearerAuth

# We should only need one set of credentials
CREDENTIALS = DefaultAzureCredential(exclude_shared_token_cache_credential=True)


def date_range(
    start_date: datetime, end_date: datetime
) -> Generator[datetime, None, None]:
    """Yield a datetime day for each day between start_date and end_date (inclusive).

    Args:
        start_date: First date included in range.
        end_date: Last date included in range.
    """
    for n in range(int((end_date - start_date).days + 1)):
        yield datetime.combine(
            start_date.date() + timedelta(n), datetime.min.time(), start_date.tzinfo
        )


def get_all_usage(
    start_date: date,
    end_date: date,
    billing_account_id: str,
    billing_profile_id: Optional[str] = None,
) -> list[str]:
    """Get Azure usage data for a subscription between start_time and end_time.

    Args:
        start_date: Start date.
        end_date: End date (inclusive).
        billing_account_id: Billing Account ID.
        billing_profile_id: Billing Profile ID.
    """
    client = CostManagementClient(CREDENTIALS)

    result = client.generate_cost_details_report.begin_create_operation(
        scope=f"providers/Microsoft.Billing/billingAccounts/{billing_account_id}/billingProfiles/{billing_profile_id}",
        parameters=GenerateCostDetailsReportRequestDefinition(
            time_period=CostDetailsTimePeriod(
                start=start_date.isoformat(), end=end_date.isoformat()
            ),
            metric=CostDetailsMetricType.AMORTIZED_COST_COST_DETAILS_METRIC_TYPE,
        ),
    ).result()

    return [b.blob_link for b in result.blobs]

    # Note that the data we get back seems to ignore the time part
    # and requesting data between 2023-01-01T00:00:00Z and 2023-01-01T00:00:00Z
    # will return data for the whole of 2023-01-01.
    # filter_from = "properties/usageEnd ge '{}'".format(
    #     start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    # )
    # filter_to = "properties/usageEnd le '{}'".format(
    #     end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    # )
    # filter_expression = "{} and {}".format(filter_from, filter_to)
    filter_expression = None

    scope_expression = ""
    # if billing_account_id:
    scope_expression = (
        f"/providers/Microsoft.Billing/billingAccounts/{billing_account_id}"
    )
    if billing_profile_id:
        scope_expression += f"/billingProfiles/{billing_profile_id}"
    # elif mgmt_group:
    #     scope_expression = (
    #         f"/providers/Microsoft.Management/managementGroups/{mgmt_group}"
    #     )

    # Actual Cost - Provides data to reconcile with your monthly bill.
    # Amortized Cost - This dataset is similar to the Actual Cost dataset except
    # that the EffectivePrice for the usage that gets reservation discount is
    # the prorated cost of the reservation (instead of being zero).
    metric_expression = "AmortizedCost"

    data = consumption_client.usage_details.list(
        scope=scope_expression, filter=filter_expression, metric=metric_expression
    )

    # Azure SDK typing here is too broad/inaccurate: list() actually iterates
    # UsageDetail items (legacy or modern), not UsageDetailsListResult wrappers.
    return cast(Iterable[UsageDetail], data)


def combine_items(item_to_update: models.Usage, other_item: models.Usage) -> None:
    """Update one Usage with the cost, etc. of another Usage."""
    item_to_update.quantity = (item_to_update.quantity or 0) + (
        other_item.quantity or 0
    )
    item_to_update.effective_price = (item_to_update.effective_price or 0) + (
        other_item.effective_price or 0
    )
    item_to_update.amortised_cost = (item_to_update.amortised_cost or 0) + (
        other_item.amortised_cost or 0
    )
    item_to_update.total_cost = (item_to_update.total_cost or 0) + (
        other_item.total_cost or 0
    )
    item_to_update.unit_price = (item_to_update.unit_price or 0) + (
        other_item.unit_price or 0
    )
    item_to_update.cost = (item_to_update.cost or 0) + (other_item.cost or 0)


def compress_items(items: list[models.Usage]) -> list[models.Usage]:
    """Compress a list of usage items into a single item by combining them.

    If two or more usage items share all the same values,
    ignoring cost, total_cost, amortised_cost, and quantity,
    combine them into one item.
    """
    combinable_fields = {
        "cost",
        "amortised_cost",
        "total_cost",
        "quantity",
    }

    ret_list: list[models.Usage] = []
    for item in items:
        curr_item_fields_dict = item.model_dump(exclude=combinable_fields)

        match_found = False
        for idx, ret_item in enumerate(ret_list):
            existing_fields_dict = ret_item.model_dump(exclude=combinable_fields)

            if existing_fields_dict == curr_item_fields_dict:
                # item can be combined.
                match_found = True
                combine_items(ret_list[idx], item)
                break

        if not match_found:
            # insert item into ret_list
            ret_list.append(copy.deepcopy(item))
    return ret_list


def usage_detail_to_usage_model(item_dict: dict[str, Any]) -> models.Usage:
    """Convert a Legacy or Modern UsageDetail to a Usage model."""
    # item_dict = dict(vars(detail))

    # Align modern naming with the legacy-shaped rctab Usage model.
    # We intentionally use billed local currency cost, not USD cost.
    # item_dict["subscription_id"] = item_dict["subscription_guid"]
    # item_dict["cost"] = item_dict["cost_in_billing_currency"]
    # item_dict["billing_currency"] = item_dict["billing_currency_code"]
    # item_dict["invoice_section"] = item_dict.get("invoice_section_name")
    #
    # # When AmortizedCost metric is being used, the cost and effective_price values
    # # for reserved instances are not zero, thus the cost value is moved to
    # # amortised_cost
    # item_dict["total_cost"] = item_dict["cost"]
    #
    # try:
    #     usage_item = models.Usage(**item_dict)
    # except ValidationError:
    #     logging.warning(
    #         "We presume that dates are midnight but date is: %s", item_dict["date"]
    #     )
    #     item_dict["date"] = item_dict["date"].replace(
    #         hour=0, minute=0, second=0, microsecond=0
    #     )
    #     item_dict["billing_period_start_date"] = item_dict[
    #         "billing_period_start_date"
    #     ].replace(hour=0, minute=0, second=0, microsecond=0)
    #     item_dict["billing_period_end_date"] = item_dict[
    #         "billing_period_end_date"
    #     ].replace(hour=0, minute=0, second=0, microsecond=0)
    #     usage_item = models.Usage(**item_dict)
    us_date_to_iso = lambda x: x[6:10] + "-" + x[0:2] + "-" + x[3:5]
    billing_currency = item_dict["billingCurrency"]
    # assert billing_currency == "GBP", f"Expected GBP but got {billing_currency}"
    # if not item_dict["billingPeriodStartDate"]:
    #     pass
    usage_item = models.Usage(
        id="",  # todo
        name=None,
        type=None,
        tags=None,
        billing_account_id=item_dict["billingAccountId"],
        billing_account_name=item_dict["billingAccountName"],
        billing_period_start_date=(
            us_date_to_iso(item_dict["billingPeriodStartDate"])
            if item_dict["billingPeriodStartDate"]
            else None
        ),
        billing_period_end_date=(
            us_date_to_iso(item_dict["billingPeriodEndDate"])
            if item_dict["billingPeriodEndDate"]
            else None
        ),
        billing_profile_id=item_dict["billingProfileId"],
        billing_profile_name=item_dict["billingProfileName"],
        account_owner_id=None,
        account_name=None,
        subscription_id=item_dict["SubscriptionId"],
        subscription_name=item_dict["subscriptionName"],
        date=us_date_to_iso(item_dict["date"]),
        product=item_dict["ProductId"] + "-" + item_dict["ProductName"],
        part_number=None,
        meter_id=item_dict["meterId"]
        + "-"
        + item_dict["meterName"]
        + "-"
        + item_dict["meterCategory"]
        + "-"
        + item_dict["meterSubCategory"]
        + "-"
        + item_dict["meterRegion"],
        quantity=item_dict["quantity"],
        effective_price=item_dict["effectivePrice"],
        cost=item_dict["costInBillingCurrency"],
        amortised_cost=None,
        total_cost=item_dict["costInBillingCurrency"],
        unit_price=item_dict["unitPrice"],
        billing_currency=billing_currency,
        resource_location=item_dict["resourceLocation"],
        consumed_service=item_dict["consumedService"],
        resource_id=item_dict["ResourceId"],
        resource_name=None,
        service_info1=item_dict["serviceInfo1"],
        service_info2=item_dict["serviceInfo2"],
        additional_info=item_dict["additionalInfo"],
        invoice_section=item_dict["invoiceSectionId"]
        + "-"
        + item_dict["invoiceSectionName"],
        cost_center=item_dict["costCenter"],
        resource_group=item_dict["resourceGroupName"],
        reservation_id=item_dict["reservationId"],
        reservation_name=item_dict["reservationName"],
        product_order_id=item_dict["productOrderId"],
        offer_id=None,
        is_azure_credit_eligible=item_dict["isAzureCreditEligible"],
        term=item_dict["term"],
        publisher_name=item_dict["publisherName"],
        publisher_type=item_dict["publisherType"],
        plan_name=None,
        charge_type=item_dict["chargeType"],
        frequency=item_dict["frequency"],
        monthly_upload=None,
    )

    if usage_item.reservation_id:
        usage_item.amortised_cost = usage_item.cost
        usage_item.cost = 0.0
    else:
        usage_item.amortised_cost = 0.0

    return usage_item


def retrieve_usage(
    usage_urls: list[str],
) -> list[models.Usage]:
    """Retrieve usage data from Azure.

    Args:
        usage_data models.UsageData: Usage data object.

    Returns:
        List[models.Usage]: List of usage data.
    """
    logging.warning("Retrieve items")

    all_items: list[models.Usage] = []
    started_processing_at = datetime.now()

    for i, url in enumerate(usage_urls):
        blob = BlobClient.from_blob_url(url)
        with open("cost_details_report.csv", "wb") as f:
            blob.download_blob().readinto(f)

        with open("cost_details_report.csv", "r", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                all_items.append(usage_detail_to_usage_model(row))

    logging.warning(
        "%d Usage objects retrieved in %s.",
        len(all_items),
        datetime.now() - started_processing_at,
    )

    return all_items


def retrieve_and_send_usage(
    hostname_or_ip: HttpUrl,
    usage_urls: list[str],
    start_date: date,
    end_date: date,
) -> None:
    """Retrieve usage data from Azure and send it to the API.

    Args:
        hostname_or_ip: Hostname or IP of the API.
        usage_urls: URLs to CSVs in blob storage.
        start_date: The start of the date range that has been collected.
        end_date: The inclusive end of the date range that has been collected.
    """
    usage_list = retrieve_usage(usage_urls)

    send_usage(hostname_or_ip, usage_list, start_date, end_date)


def send_usage(
    hostname_or_ip: HttpUrl,
    all_item_list: list[models.Usage],
    start_date: date,
    end_date: date,
    monthly_usage_upload: bool = False,
) -> None:
    """Post each item of usage_data to a route."""

    @lru_cache(1)
    def get_first_run_time() -> datetime:
        return datetime.now()

    started_processing_at = datetime.now()

    logging.warning("Upload all items")

    if monthly_usage_upload:
        path = "accounting/monthly-usage"
    else:
        path = "accounting/all-usage"

    # Note that omitting the encoding appears to work but will
    # fail server-side with some characters, such as en-dash.
    data = (
        models.AllUsage(
            usage_list=all_item_list, start_date=start_date, end_date=end_date
        )
        .model_dump_json()
        .encode("utf-8")
    )

    for _ in range(2):
        resp = requests.post(
            str(hostname_or_ip) + path,
            data=data,
            auth=BearerAuth(),
            timeout=60,
        )

        if resp.status_code == 200:
            now = datetime.now()
            logging.warning(
                "%d Usage objects processed in %s. Total Time %s",
                len(all_item_list),
                now - started_processing_at,
                now - get_first_run_time(),
            )
            return

        logging.warning(
            "Failed to send Usage. Response code: %d. Response text: %s",
            resp.status_code,
            resp.text,
        )

    raise RuntimeError("Could not POST usage data.")
