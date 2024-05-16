"""An Azure function to collect cost-management information."""
import logging
from datetime import datetime, timedelta
from typing import Final

import azure.functions as func
import requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition,
    QueryGrouping,
    QueryDataset,
    TimeframeType,
    ExportType,
    QueryAggregation,
    QueryTimePeriod,
)

import utils.settings
from utils import models
from utils.auth import BearerAuth
from utils.logutils import add_log_handler_once

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(asctime)s: %(name)s - %(message)s",
    datefmt="%d/%m/%Y %I:%M:%S %p",
)
logger: Final = logging.getLogger(__name__)

RETRY_ATTEMPTS: Final = 5
# We should only need one set of credentials
CREDENTIALS: Final = DefaultAzureCredential()

# The constant parts of the Azure Cost Management API query. To be appended
# with to/from times.
QUERY_TYPE: Final = ExportType.ACTUAL_COST
QUERY_TIMEFRAME: Final = TimeframeType.CUSTOM
QUERY_DATASET: Final = QueryDataset(
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
        # TODO What's the difference between Cost and PreTaxCost,
        # and which should we use?
        "totalCost": QueryAggregation(
            name="Cost",
            function="Sum",
        )
    },
)


def _truncate_date(date_time):
    """Truncate a datetime to the same date but 00:00:00 hours."""
    return datetime(*date_time.date().timetuple()[:3])


def get_all_usage(start_datetime: datetime, end_datetime: datetime, mgmt_group: str):
    """Collect Azure cost management data.

    The dates are truncated to the day, and the ranges are inclusive, so that e.g.
    start_datetime = 2022-01-01T15, end_datetime = 2022-01-01T0 would get all usage for
    2022-01-01.

    Args:
        start_datetime: Start time.
        end_datetime: End time.
        mgmt_group: Name of the management group.

    Return:
        A dictionary with the usage data, with (subscription_id, name, currency) as keys
        and amounts as values.
    """
    logger.warning(
        "Requesting data between %s and %s",
        start_datetime,
        end_datetime,
    )
    cm_client = CostManagementClient(credential=CREDENTIALS)
    scope = f"/providers/Microsoft.Management/managementGroups/{mgmt_group}"
    # The Azure API will truncate the datetimes anyway, but it's easier for the logic of
    # the below loop if we do it explicitly here. You might think we should just use
    # date objects instead of datetime ones, but the QueryDefinition class doesn't like
    # that.
    start_datetime = _truncate_date(start_datetime)
    end_datetime = _truncate_date(end_datetime)
    # The maximum time period that Azure allows querying in one call.
    max_timeperiod = timedelta(days=364)
    # We may have to do several queries to the Azure API, if the time period we need is
    # longer than max_timeperiod. covered_to will keep track of the last day for which
    # we have data so far.
    covered_to = start_datetime - timedelta(days=1)
    data: dict[tuple, float] = {}
    while covered_to < end_datetime:
        # The time window to cover in this query, inclusive.
        window_start = covered_to + timedelta(days=1)
        window_end = min(window_start + max_timeperiod, end_datetime)
        parameters = QueryDefinition(
            time_period=QueryTimePeriod(from_property=window_start, to=window_end),
            dataset=QUERY_DATASET,
            type=QUERY_TYPE,
            timeframe=QUERY_TIMEFRAME,
        )
        new_data = cm_client.query.usage(scope=scope, parameters=parameters)
        if new_data:
            if new_data.next_link:
                # TODO How to deal with paging?
                msg = (
                    "Cost management query returned multiple pages of results. "
                    "The function app is not prepared to deal with this."
                )
                raise NotImplementedError(msg)
            if new_data.rows:
                for amount, sub_id, name, currency in new_data.rows:
                    key = (sub_id, name, currency)
                    if key in data:
                        data[key] += amount
                    else:
                        data[key] = amount
            covered_to = window_end

    # Convert data to a list of CMUsage objects.
    all_usage = models.AllCMUsage(
        cm_usage_list=[
            models.CMUsage(
                subscription_id=key[0],
                name=key[1],
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                cost=value,
                billing_currency=key[2],
            )
            for key, value in data.items()
        ]
    )
    return all_usage


def send_usage(hostname_or_ip, all_usage):
    """POST cost management data to the RCTab server.

    Args:
      hostname_or_ip: IP for the server.
      all_usage: Usage data as returned by get_all_usage.

    Return:
      None

    Raise:
      RuntimeError if the POST fails, despite retries.
    """
    started_processing_at = datetime.now()
    for _ in range(RETRY_ATTEMPTS):
        logger.warning("Uploading cost-management usage.")
        resp = requests.post(
            hostname_or_ip + "/accounting/all-cm-usage",
            all_usage.model_dump_json(),
            auth=BearerAuth(),
            timeout=60,
        )

        if resp.status_code == 200:
            now = datetime.now()
            logger.warning(
                "%d CMUsage objects POSTed in %s.",
                len(all_usage.cm_usage_list),
                now - started_processing_at,
            )
            return
        logger.warning(
            "Failed to send CMUsage. Response code: %d. Response text: %s.",
            resp.status_code,
            resp.text,
        )

    raise RuntimeError("Could not POST usage data.")


def main(mytimer: func.TimerRequest) -> None:
    """Run the cost management function.

    Get all the cost management data since the beginning of the calendar year,
    and POST it the RCTab server.
    """
    # todo remove reference to EA group
    add_log_handler_once(__name__)

    if mytimer.past_due:
        logger.warning(
            "The timer is past due. "
            "Cost management function running later than expected."
        )
    else:
        logger.warning("Cost management function starting.")

    # If incorrect settings have been given, better to find out sooner rather than
    # later.
    config = utils.settings.get_settings()

    end_datetime = datetime.now()
    # TODO What should this start date be?
    start_datetime = datetime(year=end_datetime.year, month=1, day=1)
    usage = get_all_usage(start_datetime, end_datetime, config.CM_MGMT_GROUP or "")
    send_usage(config.API_URL, usage)
