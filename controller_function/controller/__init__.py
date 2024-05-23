"""An Azure Function App to disable subscriptions."""
import logging
from datetime import datetime
from typing import Iterable
from uuid import UUID

import azure.functions as func
from azure.core.exceptions import HttpResponseError
from pydantic import HttpUrl
from requests import get

from controller import models, settings
from controller.auth import BearerAuth
from controller.logutils import add_log_handler_once
from controller.subscription import disable_subscription, enable_subscription

logger = logging.getLogger(__name__)


def get_desired_states(api_url: HttpUrl) -> list[models.DesiredState]:
    """Get a list of subscriptions and their desired states."""
    started_at = datetime.now()

    endpoint = str(api_url) + "accounting/desired-states"
    logger.info(endpoint)
    response = get(url=endpoint, auth=BearerAuth(), timeout=120)

    if response.status_code != 200:
        logger.error(
            "Could not get desired states. %s returned %s status.",
            endpoint,
            str(response.status_code),
        )
        raise RuntimeError("Could not get desired states.")

    # Use DesiredStateList to validate the response payload...
    response_json = response.json()
    logger.info(response)
    desired_states = [models.DesiredState(**x) for x in response_json]

    logger.info("Getting desired states took %s.", str(datetime.now() - started_at))

    # ...but return a normal List of DesiredStates
    return desired_states


def disable_subscriptions(subs_to_deactivate: Iterable[UUID]) -> None:
    """Disable Azure subscriptions, which will stop all spending."""
    logger.info("Disabling subscriptions: %s", subs_to_deactivate)

    started_at = datetime.now()

    for subscription_id in subs_to_deactivate:
        logger.warning("Disabling %s", subscription_id)

        try:
            disable_subscription(subscription_id)
        except HttpResponseError as e:
            logger.warning(str(e))

    logger.info("Disabling subscriptions took %s.", str(datetime.now() - started_at))


def enable_subscriptions(subs_to_enable: Iterable[UUID]) -> None:
    """Enable Azure subscriptions."""
    logger.info("Enabling subscriptions %s.", subs_to_enable)

    started_at = datetime.now()

    for subscription_id in subs_to_enable:
        logger.warning("Enabling %s", subscription_id)

        try:
            enable_subscription(subscription_id)
        except HttpResponseError as e:
            logger.warning(str(e))

    logger.info("Enabling subscriptions took %s.", str(datetime.now() - started_at))


def main(mytimer: func.TimerRequest) -> None:
    """Disable or enable subscriptions as directed by the API."""
    # If incorrect settings have been given,
    # better to find out sooner rather than later.
    config = settings.get_settings()

    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s %(message)s",
        datefmt="%d/%m/%Y %I:%M:%S %p",
    )
    add_log_handler_once(__name__)

    logger.warning("Controller function starting.")

    if mytimer.past_due:
        logger.info("The timer is past due.")

    subscriptions = get_desired_states(config.API_URL)

    subs_to_deactivate = [
        x.subscription_id for x in subscriptions if x.desired_state == "Disabled"
    ]
    disable_subscriptions(subs_to_deactivate)

    subs_to_enable = [
        x.subscription_id for x in subscriptions if x.desired_state == "Enabled"
    ]
    enable_subscriptions(subs_to_enable)
