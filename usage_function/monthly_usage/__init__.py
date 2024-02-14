"""An Azure Function App to collect usage information for the previous month."""
import logging
import time
from datetime import datetime, timedelta

import azure.functions as func
from azure.core.exceptions import HttpResponseError

import utils.settings
from utils.logutils import add_log_handler_once
from utils.usage import date_range, get_all_usage, retrieve_usage, send_usage

MAX_ATTEMPTS = 5


def main(mytimer: func.TimerRequest) -> None:
    """Collect usage information for the previous month."""
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
    logger.warning("Monthly usage function starting.")

    if mytimer.past_due:
        logger.info("The timer is past due.")

    # The end of the previous month is today minus the number of days we are
    # into the month
    now = datetime.now()
    end_of_last_month = now - timedelta(days=now.day)

    end_datetime = datetime(
        end_of_last_month.year, end_of_last_month.month, end_of_last_month.day
    )
    start_datetime = datetime(end_datetime.year, end_datetime.month, 1)

    logger.warning(
        "Requesting all data between %s and %s in reverse order",
        start_datetime,
        end_datetime,
    )

    usage = []
    for usage_date in reversed(list(date_range(start_datetime, end_datetime))):
        # Try up to 5 times to get usage and send to the API
        for cnt in range(MAX_ATTEMPTS):
            logger.warning("Requesting all usage data for %s", usage_date)
            usage_day = get_all_usage(
                usage_date,
                usage_date,
                billing_account_id=config.BILLING_ACCOUNT_ID,
                mgmt_group=config.MGMT_GROUP,
            )

            try:
                usage_day_list = retrieve_usage(usage_day)

                for usage_day in usage_day_list:
                    usage_day.monthly_upload = now.date()

                usage += usage_day_list
                break
            except HttpResponseError as e:
                logger.error("Request to azure failed. Trying again in 60 seconds")
                logger.error(e)
                time.sleep(60)

        if cnt == MAX_ATTEMPTS - 1:
            logger.error("Could not retrieve usage data.")
            raise RuntimeError("Could not retrieve usage data.")

    logger.warning(
        "Retrieved %d usage records for %s to %s",
        len(usage),
        start_datetime,
        end_datetime,
    )

    send_usage(config.API_URL, usage, monthly_usage_upload=True)

    logger.warning("Monthly usage function finished.")
