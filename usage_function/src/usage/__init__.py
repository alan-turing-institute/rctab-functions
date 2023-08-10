"""An Azure Function App to collect usage information."""
import logging
import time
from datetime import datetime, timedelta

import azure.functions as func
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential

from src.utils import settings
from src.utils.logutils import set_log_handler
from src.utils.usage import date_range, get_all_usage, retrieve_and_send_usage

# We should only need one set of credentials
CREDENTIALS = DefaultAzureCredential(exclude_shared_token_cache_credential=True)


def main(mytimer: func.TimerRequest) -> None:
    # If incorrect settings have been given,
    # better to find out sooner rather than later.
    config = settings.get_settings()

    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s %(message)s",
        datefmt="%d/%m/%Y %I:%M:%S %p",
    )

    set_log_handler(__name__)
    logger = logging.getLogger(__name__)

    logger.warning("Usage function starting.")

    if mytimer.past_due:
        logger.info("The timer is past due.")

    now = datetime.now()
    start_datetime = (
        now
        - timedelta(days=config.USAGE_HISTORY_DAYS - 1)
        - timedelta(days=config.USAGE_HISTORY_DAYS_OFFSET)
    )
    end_datetime = now - timedelta(days=config.USAGE_HISTORY_DAYS_OFFSET)

    logger.warning(
        "Requesting all data between %s and %s in reverse order",
        start_datetime,
        end_datetime,
    )

    for usage_date in reversed(list(date_range(start_datetime, end_datetime))):
        # Try up to 5 times to get usage and send to the API
        for _ in range(5):
            logger.warning("Requesting all usage data for %s", usage_date)
            usage = get_all_usage(
                usage_date,
                usage_date,
                billing_account_id=config.BILLING_ACCOUNT_ID,
                mgmt_group=config.MGMT_GROUP,
            )

            try:
                retrieve_and_send_usage(config.API_URL, usage)
                break
            except HttpResponseError as e:
                logger.error("Request to azure failed. Trying again in 60 seconds")
                logger.error(e)
                time.sleep(60)
