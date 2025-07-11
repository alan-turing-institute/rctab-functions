"""Utils for collecting and sending Azure usage data."""

import copy
import logging
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Generator, Iterable, Optional
from uuid import UUID

import requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.consumption.models import UsageDetailsListResult
from pydantic import HttpUrl
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
        yield datetime.combine(start_date.date() + timedelta(n), datetime.min.time())


def get_all_usage(
    start_time: datetime,
    end_time: datetime,
    billing_account_id: Optional[str] = None,
    mgmt_group: Optional[str] = None,
) -> Iterable[UsageDetailsListResult]:
    """Get Azure usage data for a subscription between start_time and end_time.

    Args:
        start_time: Start time.
        end_time: End time.
        billing_account_id: Billing Account ID.
        mgmt_group: The name of a management group.
    """
    # It doesn't matter which subscription ID we use for this bit.
    consumption_client = ConsumptionManagementClient(
        credential=CREDENTIALS, subscription_id=str(UUID(int=0))
    )

    # Note that the data we get back seems to ignore the time part
    # and requesting data between 2023-01-01T00:00:00Z and 2023-01-01T00:00:00Z
    # will return data for the whole of 2023-01-01.
    filter_from = "properties/usageEnd ge '{}'".format(
        start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    filter_to = "properties/usageEnd le '{}'".format(
        end_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    filter_expression = "{} and {}".format(filter_from, filter_to)

    scope_expression = ""
    if billing_account_id:
        scope_expression = (
            f"/providers/Microsoft.Billing/billingAccounts/{billing_account_id}"
        )
    elif mgmt_group:
        scope_expression = (
            f"/providers/Microsoft.Management/managementGroups/{mgmt_group}"
        )

    # Actual Cost - Provides data to reconcile with your monthly bill.
    # Amortized Cost - This dataset is similar to the Actual Cost dataset except
    # that the EffectivePrice for the usage that gets reservation discount is
    # the prorated cost of the reservation (instead of being zero).
    metric_expression = "AmortizedCost"

    data = consumption_client.usage_details.list(
        scope=scope_expression, filter=filter_expression, metric=metric_expression
    )

    return data


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


def retrieve_usage(
    usage_data: Iterable[UsageDetailsListResult],
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

    for i, item in enumerate(usage_data):
        if i % 200 == 0:
            logging.warning("Requesting item %d", i)

        item_dict = dict(vars(item))

        # When AmortizedCost metric is being used, the cost and effective_price values
        # for reserved instances are not zero, thus the cost value is moved to
        # amortised_cost
        item_dict["total_cost"] = item_dict["cost"]

        usage_item = models.Usage(**item_dict)

        if usage_item.reservation_id is not None:
            usage_item.amortised_cost = usage_item.cost
            usage_item.cost = 0.0
        else:
            usage_item.amortised_cost = 0.0

        all_items.append(usage_item)

    combined_items = compress_items(all_items)

    logging.warning(
        "%d Usage objects retrieved in %s.",
        len(combined_items),
        datetime.now() - started_processing_at,
    )

    return combined_items


def retrieve_and_send_usage(
    hostname_or_ip: HttpUrl,
    usage_data: Iterable[UsageDetailsListResult],
    start_date: date,
    end_date: date,
) -> None:
    """Retrieve usage data from Azure and send it to the API.

    Args:
        hostname_or_ip: Hostname or IP of the API.
        usage_data: Usage data object.
        start_date: The start of the date range that has been collected.
        end_date: The inclusive end of the date range that has been collected.
    """
    usage_list = retrieve_usage(usage_data)

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
