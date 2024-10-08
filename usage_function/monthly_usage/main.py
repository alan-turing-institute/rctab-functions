"""Run the monthly usage function manually."""

import datetime
import logging
import time

from azure.core.exceptions import HttpResponseError

import utils.settings
from utils.usage import get_all_usage, retrieve_usage, send_usage


def main() -> None:
    """Collect usage information and send it to the API."""
    config = utils.settings.get_settings()
    # print(item.date.isoformat())
    logger = logging.getLogger(__name__)
    # Try up to 5 times to get usage and send to the API
    for attempt in range(1):
        logger.warning("Attempt %d", attempt + 1)

        try:
            usage_query = get_all_usage(
                # change these as needed
                datetime.datetime(2024, 8, 30),
                datetime.datetime(2024, 9, 1),  # 29, 23, 59, 59, 999999),
                # todo last day of July?
                billing_account_id=config.BILLING_ACCOUNT_ID,
                # mgmt_group="ea"
            )
            usage_items = retrieve_usage(usage_query)

            today = datetime.date.today()
            for usage_item in usage_items:
                usage_item.monthly_upload = today

            # logger.warning("Sending usage for %s", dates)
            try:
                send_usage(config.API_URL, usage_items, monthly_usage_upload=False)
            except Exception as e:
                raise e

            logger.warning("Monthly usage function finished.")
            return

        except HttpResponseError as e:
            if attempt == 1 - 1:
                logger.error("Could not retrieve usage data.")
                raise RuntimeError("Could not retrieve usage data.")

            logger.error("Request to azure failed. Trying again in 60 seconds")
            logger.error(e)
            time.sleep(60)


if __name__ == "__main__":
    main()
