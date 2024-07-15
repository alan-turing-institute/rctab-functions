"""Utils for collecting and sending Azure usage data."""
import logging
from datetime import datetime, timedelta, date
from functools import lru_cache
from typing import Dict, Optional, Iterable, Generator
from uuid import UUID

import requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.consumption import ConsumptionManagementClient
from azure.mgmt.consumption.models import UsageDetailsListResult
from pydantic_core import Url

from utils import models
from utils.auth import BearerAuth

# We should only need one set of credentials
CREDENTIALS = DefaultAzureCredential(exclude_shared_token_cache_credential=True)


def date_range(start_date: date, end_date: date) -> Generator[date, None, None]:
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

    item_to_update.cost += other_item.cost


def retrieve_usage(usage_data: Iterable[UsageDetailsListResult]) -> list[models.Usage]:
    """Retrieve usage data from Azure.

    Args:
        usage_data models.UsageData: Usage data object.

    Returns:
        List[models.Usage]: List of usage data.
    """
    logging.warning("Retrieve items")

    all_items: Dict[str, models.Usage] = {}
    started_processing_at = datetime.now()

    for i, item in enumerate(usage_data):
        if i % 200 == 0:
            logging.warning("Requesting item %d", i)

        usage_item = models.Usage(**vars(item))

        # When AmortizedCost metric is being used, the cost and effective_price values
        # for reserved instances are not zero, thus the cost value is moved to
        # amortised_cost
        usage_item.total_cost = usage_item.cost

        if usage_item.reservation_id is not None:
            usage_item.amortised_cost = usage_item.cost
            usage_item.cost = 0.0
        else:
            usage_item.amortised_cost = 0.0

        if usage_item.id in all_items:
            existing_item = all_items[usage_item.id]
            # Add to the existing item
            combine_items(existing_item, usage_item)

            # Update the dict entry
            all_items[usage_item.id] = existing_item

        else:
            all_items[usage_item.id] = usage_item

    all_item_list = list(all_items.values())

    logging.warning(
        "%d Usage objects retrieved in %s.",
        len(all_item_list),
        datetime.now() - started_processing_at,
    )

    return list(all_items.values())


def retrieve_and_send_usage(hostname_or_ip: Url, usage_data):
    """Retrieve usage data from Azure and send it to the API.

    Args:
        hostname_or_ip: Hostname or IP of the API.
        usage_data: Usage data object.
    """
    usage_list = retrieve_usage(usage_data)

    send_usage(hostname_or_ip, usage_list)


def send_usage(hostname_or_ip: Url, all_item_list: list[models.Usage], monthly_usage_upload: bool=False):
    """Post each item of usage_data to a route."""

    @lru_cache(1)
    def get_first_run_time():
        return datetime.now()

    started_processing_at = datetime.now()

    logging.warning("Upload all items")

    if monthly_usage_upload:
        path = "accounting/monthly-usage"
    else:
        path = "accounting/all-usage"

    # Note that omitting the encoding appears to work but will
    # fail server-side with some characters, such as en-dash.
    data = models.AllUsage(usage_list=all_item_list).model_dump_json().encode("utf-8")

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
