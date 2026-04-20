"""An Azure Function App to collect usage information."""

import logging
import time
from datetime import datetime, timedelta, timezone

import azure.functions as func
from azure.core.exceptions import HttpResponseError

import utils.settings
from utils.logutils import add_log_handler_once
from utils.usage import date_range, get_all_usage, retrieve_and_send_usage


def main(mytimer: func.TimerRequest) -> None:
    """Collect usage information and send it to the API."""
    # If incorrect settings have been given,
    # better to find out sooner rather than later.
    config = utils.settings.get_settings()

    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s %(message)s",
        datefmt="%d/%m/%Y %I:%M:%S %p",
    )

    add_log_handler_once(__name__)
    logger = logging.getLogger(__name__)

    logger.warning("Usage function starting.")

    if mytimer.past_due:
        logger.info("The timer is past due.")

    now = datetime.now(timezone.utc).replace(hour=0, microsecond=0, second=0, minute=0)
    start_date = (
        now
        - timedelta(days=config.USAGE_HISTORY_DAYS - 1)
        - timedelta(days=config.USAGE_HISTORY_DAYS_OFFSET)
    )
    end_date = now - timedelta(days=config.USAGE_HISTORY_DAYS_OFFSET)

    # for usage_date in reversed(list(date_range(start_datetime, end_datetime))):
    # Try up to 5 times to get usage and send to the API
    for _ in range(5):
        logger.warning(
            "Requesting all usage data between %s and %s", start_date, end_date
        )
        # usage_urls = [1]
        usage_urls = get_all_usage(
            start_date,
            end_date,
            billing_account_id=config.BILLING_ACCOUNT_ID,
            billing_profile_id=config.BILLING_PROFILE_ID,
            # mgmt_group=config.MGMT_GROUP,
        )

        try:
            retrieve_and_send_usage(
                config.API_URL,
                usage_urls,
                start_date,
                end_date,
            )
            return
        except HttpResponseError as e:
            logger.error("Request to azure failed. Trying again in 60 seconds")
            logger.error(e)
            time.sleep(60)

    raise RuntimeError("Could not collect and send usage information.")


#
