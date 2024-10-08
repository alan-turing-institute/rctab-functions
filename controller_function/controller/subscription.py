"""Manage subscription life cycle."""

import logging
from uuid import UUID

from azure.core import exceptions as azure_exceptions
from azure.identity import DefaultAzureCredential
from azure.mgmt.subscription import SubscriptionClient

CREDENTIALS = DefaultAzureCredential()

SUBSCRIPTION_CLIENT = SubscriptionClient(credential=CREDENTIALS)


def enable_subscription(subscription_id: UUID) -> None:
    """Enable a subscription.

    Args:
        subscription_id: Subscription id.
    """
    try:
        SUBSCRIPTION_CLIENT.subscription.enable(str(subscription_id))
    except azure_exceptions.HttpResponseError as e:
        is_enabled = (
            ("not in suspended state" in e.error.message)
            if (e.error and e.error.message)
            else False
        )

        # It's fine if we can't enable it because it is already active.
        if is_enabled:
            logging.warning(
                "%s didn't need to be enabled as it was already active.",
                subscription_id,
            )
        else:
            raise e


def disable_subscription(subscription_id: UUID) -> None:
    """Disable a subscription.

    Args:
        subscription_id: Subscription id.
    """
    try:
        # IgnoreResourceCheck=True is required to disable a subscription
        # that has resources.
        # See https://github.com/Azure/azure-sdk-for-python/issues/10814
        SUBSCRIPTION_CLIENT.subscription.cancel(
            str(subscription_id),
            params={"IgnoreResourceCheck": True},
        )
    except azure_exceptions.HttpResponseError as e:
        is_disabled = (
            ("Subscription is not in active state" in e.error.message)
            if (e.error and e.error.message)
            else False
        )

        # It's fine if we can't disable it because it is already inactive.
        if is_disabled:
            logging.warning(
                "%s didn't need to be disabled as it wasn't active.", subscription_id
            )
        else:
            raise e
