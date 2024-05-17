"""An Azure Function App to collect usage information for the previous month."""
import logging
import time
from datetime import date, datetime, timedelta
from typing import Tuple, Union

import azure.functions as func
from azure.core.exceptions import HttpResponseError

import utils.settings
from utils.logutils import add_log_handler_once
from utils.usage import get_all_usage, retrieve_usage, send_usage

MAX_ATTEMPTS = 5


def get_dates() -> Union[None, Tuple[date], Tuple[date, date]]:
    """Get up to two dates to process.

    Assuming we are called bi-hourly on the 7th and 8th of the month,
    return up to two days from the previous month to process.
    """
    now = datetime.now()

    # Map our day (7 or 8) and hour (0-22) to a day.
    day_of_month = ((now.day - 7) * 24) + now.hour + 1

    end_of_last_month = now - timedelta(days=now.day)
    try:
        day1 = date(
            year=end_of_last_month.year, month=end_of_last_month.month, day=day_of_month
        )
    except ValueError:
        return None

    try:
        day2 = date(
            year=end_of_last_month.year,
            month=end_of_last_month.month,
            day=day_of_month + 1,
        )
    except ValueError:
        return (day1,)
    return day1, day2


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

    dates = get_dates()
    if not dates:
        logger.warning("No dates to process.")
        return

    logger.warning(
        "Requesting all data for %s",
        dates,
    )

    # Try up to 5 times to get usage and send to the API
    for attempt in range(MAX_ATTEMPTS):
        logger.warning("Attempt %d", attempt + 1)

        date_from = datetime(dates[0].year, dates[0].month, dates[0].day)
        date_to = (
            datetime(dates[1].year, dates[1].month, dates[1].day)
            if len(dates) == 2
            else date_from
        )
        usage_query = get_all_usage(
            date_from,
            date_to,
            billing_account_id=config.BILLING_ACCOUNT_ID,
            mgmt_group=config.MGMT_GROUP,
        )

        try:
            usage_items = retrieve_usage(usage_query)

            today = date.today()
            for usage_item in usage_items:
                usage_item.monthly_upload = today

            logger.warning("Sending usage for %s", dates)
            send_usage(config.API_URL, usage_items, monthly_usage_upload=True)

            logger.warning("Monthly usage function finished.")
            return

        except HttpResponseError as e:
            if attempt == MAX_ATTEMPTS - 1:
                logger.error("Could not retrieve usage data.")
                raise RuntimeError("Could not retrieve usage data.")

            logger.error("Request to azure failed. Trying again in 60 seconds")
            logger.error(e)
            time.sleep(60)
