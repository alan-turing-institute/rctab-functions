"""Manage subscription life cycle."""
import logging
import types
from uuid import UUID

from azure.core import exceptions as azure_exceptions
from azure.identity import DefaultAzureCredential
from azure.mgmt.subscription import SubscriptionClient

# pylint: disable=too-many-arguments

CREDENTIALS = DefaultAzureCredential()

SUBSCRIPTION_CLIENT = SubscriptionClient(credential=CREDENTIALS)


def new_post(
    self,
    url,
    params=None,
    headers=None,
    content=None,
    form_content=None,
    stream_content=None,
):
    """Add IgnoreResourceCheck=True to the existing query params.

    See also https://github.com/Azure/azure-sdk-for-python/issues/10814
    """
    if url.endswith("cancel"):
        params = {**(params or {}), **{"IgnoreResourceCheck": True}}

    return self.original_post_method(
        url,
        params=params,
        headers=headers,
        content=content,
        form_content=form_content,
        stream_content=stream_content,
    )


def enable_subscription(subscription_id: UUID) -> None:
    """Enable a subscription.

    Args:
        subscription_id: Subscription id.
    """
    try:
        SUBSCRIPTION_CLIENT.subscription.enable(str(subscription_id))
    except azure_exceptions.HttpResponseError as e:
        is_enabled = "not in suspended state" in e.error.message

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
        SUBSCRIPTION_CLIENT.subscription.cancel(str(subscription_id))
    except azure_exceptions.HttpResponseError as e:
        is_disabled = (
            "Subscription is not in active state and is hence marked as read-only"
            in e.error.message
        )

        # It's fine if we can't disable it because it is already inactive.
        if is_disabled:
            logging.warning(
                "%s didn't need to be disabled as it wasn't active.", subscription_id
            )
        else:
            raise e


# Patch the original post method with our own so that we can add
# IgnoreResourceCheck=True to the query params. Without this,
# subscriptions with resources will not be disabled.
# pylint: disable=protected-access
SUBSCRIPTION_CLIENT.subscription._client.original_post_method = (
    SUBSCRIPTION_CLIENT.subscription._client.post
)
SUBSCRIPTION_CLIENT.subscription._client.post = types.MethodType(
    new_post, SUBSCRIPTION_CLIENT.subscription._client
)
# pylint: enable=protected-access
