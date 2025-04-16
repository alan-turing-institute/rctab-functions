"""An Azure Function App to collect status information.

Attributes:
    CREDENTIALS: A set of credentials to use for authentication.
"""

import asyncio
import logging
from datetime import datetime
from functools import lru_cache
from typing import Any
from uuid import UUID

import azure.functions as func
import requests
from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient as AuthClient
from azure.mgmt.subscription import SubscriptionClient
from kiota_abstractions.api_error import APIError
from msgraph.generated.models.directory_object_collection_response import (
    DirectoryObjectCollectionResponse,
)
from msgraph.generated.models.service_principal import ServicePrincipal
from msgraph.generated.models.user import User
from msrestazure.azure_exceptions import CloudError  # todo
from pydantic import HttpUrl
from rctab_models import models

from msgraph import GraphServiceClient
from status import settings
from status.auth import BearerAuth
from status.logutils import add_log_handler_once
from status.wrapper import CredentialWrapper

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(message)s",
    datefmt="%d/%m/%Y %I:%M:%S %p",
)
logger = logging.getLogger(__name__)

# We should only need one set of credentials.
CREDENTIALS = DefaultAzureCredential()


def send_status(hostname_or_ip: HttpUrl, status_data: list) -> None:
    """Post each item of status_data to a route.

    Args:
        hostname_or_ip: The hostname or IP address of the API.
        status_data: A list of status objects.

    Raises:
        RuntimeError: If the POST fails twice.

    Returns:
        None.
    """
    logger.warning("Sending status data.")

    # Note that omitting the encoding appears to work but will
    # fail server-side with some characters, such as en-dash.
    data = (
        models.AllSubscriptionStatus(status_list=status_data)
        .model_dump_json()
        .encode("utf-8")
    )

    for _ in range(2):
        started_sending_at = datetime.now()
        # Note that we need to
        resp = requests.post(
            str(hostname_or_ip) + "accounting/all-status",
            data=data,
            auth=BearerAuth(),
            timeout=60,
        )

        if resp.status_code == 200:
            logger.warning(
                "%d Status objects sent in %s.",
                len(status_data),
                datetime.now() - started_sending_at,
            )
            return

        logger.warning(
            "Failed to send status data. Response code: %d. Response text: %s",
            resp.status_code,
            resp.text,
        )

    raise RuntimeError("Could not POST status data.")


def get_role_assignments_list(auth_client: AuthClient) -> list:
    """Return a list of role assignments from an auth client.

    Args:
        auth_client: An auth client.

    Returns:
        A list of role assignments.
    """
    return list(auth_client.role_assignments.list_for_subscription())


def get_role_def_dict(auth_client: AuthClient, subscription_id: str) -> dict:
    """Return a dictionary of role definitions from an auth client.

    See https://docs.microsoft.com/en-us/python/api/azure-mgmt-authorization/azure.mgmt.authorization.v2015_07_01.models.roledefinition?view=azure-python # noqa pylint: disable=C0301

    Args:
        auth_client: An auth client.
        subscription_id: The subscription id.

    Returns:
        A dictionary of role definitions. id is the key and role name is the value.
    """
    role_defs = list(
        auth_client.role_definitions.list(scope="/subscriptions/" + subscription_id)
    )
    return {x.id: x.role_name for x in role_defs}


def get_auth_client(
    subscription: Any,
) -> AuthClient:
    """Get an auth client for a given subscription.

    See https://docs.microsoft.com/en-us/python/api/azure-mgmt-authorization/azure.mgmt.authorization.authorizationmanagementclient?view=azure-python # noqa pylint: disable=C0301

    Args:
        subscription: A subscription to retrieve te authorisation client for.

    Returns:
        An authorisation client for the given subscription.
    """
    return AuthClient(
        credential=CREDENTIALS,
        subscription_id=subscription.subscription_id,
        api_version="2022-04-01",
    )


def get_principal_details(principal: Any) -> dict[str, Any]:
    """Get details of a service principal.

    Args:
        principal: The principal to get details for.

    Returns:
        A dictionary of principal details including type, display name and email.
    """
    mail = None
    display_name = "Unknown"

    if hasattr(principal, "display_name"):
        display_name = principal.display_name
    if hasattr(principal, "mail"):
        mail = principal.mail
    return {
        "display_name": display_name,
        "mail": mail,
    }


@lru_cache(maxsize=500)
def get_graph_user(user_id: str, client: GraphServiceClient) -> User | None:
    """Get a user from the graph client.

    Args:
        user_id: The user UUID id to get.
        client: The graph client to use.

    Returns:
        The user object.
    """
    try:
        return asyncio.get_event_loop().run_until_complete(
            client.users.by_user_id(user_id).get()
        )
    except APIError as e:
        logger.warning(e)
        return None


@lru_cache(maxsize=500)
def get_graph_group_members(
    group_id: str, client: GraphServiceClient
) -> DirectoryObjectCollectionResponse | None:
    """Get the members list for a group.

    Args:
        group_id: The UUID of the group.
        client: The graph client to use.

    Returns:
        An object containing the members of the group in its value attribute.
    """
    try:
        # Note that this is a paginated response and will only return the first 100 results.
        return asyncio.get_event_loop().run_until_complete(
            client.groups.by_group_id(group_id).members.get()
        )
    except APIError as e:
        logger.warning(e)
        return None


@lru_cache(maxsize=500)
def get_graph_service_principal(
    service_principal_id: str, client: GraphServiceClient
) -> ServicePrincipal | None:
    """Get a user from the graph client.

    Args:
        service_principal_id: The UUID of the service principal.
        client: The graph client to use.

    Returns:
        The service principal object.
    """
    try:
        return asyncio.get_event_loop().run_until_complete(
            client.service_principals.by_service_principal_id(
                service_principal_id
            ).get()
        )
    except APIError as e:
        print("logger type:", type(logger), flush=True)
        logger.warning(e)
        return None


def get_role_assignment_models(
    assignment: Any, role_name: str, graph_client: GraphServiceClient
) -> list[models.RoleAssignment]:
    """Populate RoleAssignment objects with principal role details.

    Args:
        assignment: The role assignment to get details for.
        role_name: The name of the role.
        graph_client: The graph client to check the principal.

    Returns:
        A list of RoleAssignment objects.
    """
    user_details = []
    if assignment.principal_type == "User":
        user = get_graph_user(assignment.principal_id, graph_client)
        user_details.append(get_principal_details(user))
    elif assignment.principal_type == "Group":
        group_members = get_graph_group_members(assignment.principal_id, graph_client)
        if group_members is not None:
            user_details.extend([get_principal_details(x) for x in group_members.value])
    elif assignment.principal_type == "ServicePrincipal":
        service_principal = get_graph_service_principal(
            assignment.principal_id, graph_client
        )
        user_details.append(get_principal_details(service_principal))
    else:
        logger.warning(
            "Did not recognise principal type %s",
            assignment.principal_type,
        )
    return [
        models.RoleAssignment(
            role_definition_id=assignment.role_definition_id,
            role_name=role_name,
            principal_id=assignment.principal_id,
            scope=assignment.scope,
            display_name=x["display_name"],
            mail=x["mail"],
        )
        for x in user_details
    ]


def get_subscription_role_assignment_models(
    subscription: Any,
    graph_client: GraphServiceClient,
) -> list[models.RoleAssignment]:
    """Get the role assignment models for each a subscription.

    Args:
        subscription: The subscription to get role assignments for.
        graph_client: The graph client to check the principal.

    Returns:
        A list of RoleAssignment objects.
    """
    auth_client = get_auth_client(subscription)
    role_def_dict = get_role_def_dict(auth_client, subscription.subscription_id)
    assignments_list = get_role_assignments_list(auth_client)
    role_assignments_models = []
    for assignment in assignments_list:
        role_assignments_models += get_role_assignment_models(
            assignment,
            role_def_dict.get(assignment.role_definition_id, "Unknown"),
            graph_client,
        )
    return role_assignments_models


def get_all_status(tenant_id: UUID) -> list[models.SubscriptionStatus]:
    """Get status and role assignments for all subscriptions.

    Args:
        tenant_id: The tenant id to get status for.

    Returns:
        A list of SubscriptionStatus objects.
    """
    logger.warning("Getting all status data.")
    started_at = datetime.now()

    scopes = ["https://graph.microsoft.com/.default"]
    graph_client = GraphServiceClient(credentials=CREDENTIALS, scopes=scopes)

    client = SubscriptionClient(credential=CREDENTIALS)
    subscriptions = client.subscriptions.list()

    data: list[models.SubscriptionStatus] = []
    for i, subscription in enumerate(subscriptions):
        if i % 10 == 0:
            logger.info("%s subscriptions processed.", i)

        if (
            subscription.subscription_id is not None
            and subscription.display_name is not None
            and subscription.state is not None
        ):
            role_assignments_models = get_subscription_role_assignment_models(
                subscription, graph_client
            )

            data.append(
                models.SubscriptionStatus(
                    subscription_id=subscription.subscription_id,
                    display_name=subscription.display_name,
                    state=subscription.state,
                    role_assignments=tuple(role_assignments_models),
                )
            )

    logger.warning("Status data retrieved in %s.", str(datetime.now() - started_at))
    return data


def main(mytimer: func.TimerRequest) -> None:
    """Run status app.

    Args:
        mytimer: A timer.

    Returns:
        None.
    """
    # If incorrect settings have been given,
    # better to find out sooner rather than later.
    config = settings.get_settings()

    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s %(message)s",
        datefmt="%d/%m/%Y %I:%M:%S %p",
    )
    add_log_handler_once(__name__)
    logger.warning("Status function starting.")

    if mytimer.past_due:
        logger.info("The timer is past due.")

    status = get_all_status(config.AZURE_TENANT_ID)

    # send_status(config.API_URL, status)
    logger.warning(
        "Credential type used was: %s",
        type(CREDENTIALS._successful_credential),  # pylint: disable=W0212
    )
