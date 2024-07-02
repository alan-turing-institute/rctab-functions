"""An Azure Function App to collect status information.

Attributes:
    CREDENTIALS: A set of credentials to use for authentication.
    GRAPH_CREDENTIALS: A set of credentials to use for authentication with the
        Azure AD graph. See https://docs.microsoft.com/en-us/graph/auth-v2-service#4-get-an-access-token # noqa pylint: disable=C0301

"""
import logging
from datetime import datetime
from functools import lru_cache
from typing import Any, Optional
from uuid import UUID

import azure.functions as func
import requests
from azure.graphrbac import GraphRbacManagementClient
from azure.graphrbac.models import ADGroup, GetObjectsParameters
from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient as AuthClient
from azure.mgmt.subscription import SubscriptionClient
from msrestazure.azure_exceptions import CloudError
from pydantic import HttpUrl

from status import models, settings
from status.auth import BearerAuth
from status.logutils import add_log_handler_once
from status.models import RoleAssignment
from status.wrapper import CredentialWrapper

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(message)s",
    datefmt="%d/%m/%Y %I:%M:%S %p",
)
logger = logging.getLogger(__name__)

# We should only need one set of credentials.
CREDENTIALS = DefaultAzureCredential()

# See
# https://docs.microsoft.com/en-us/graph/auth-v2-service#4-get-an-access-token
# for information about the URL to use here. graph.windows.net is for the Azure
# AD graph, graph.microsoft.com would be for the Microsoft graph.
GRAPH_CREDENTIALS = CredentialWrapper(
    resource_id="https://graph.windows.net/.default",
)


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

    # Note that omitting the encoding appears to work but will fail server-side with some characters, such as en-dash.
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


@lru_cache(maxsize=500)
def get_principal(
    principal_id: str, graph_client: GraphRbacManagementClient
) -> Optional[list]:
    """Get the service principal.

    Args:
        principal_id: The principal id.
        graph_client: The graph client to check the principal.

    Returns:
        The principal if it exists, otherwise None.
    """
    params = GetObjectsParameters(
        include_directory_object_references=True,
        object_ids=[principal_id],
    )
    principal = list(graph_client.objects.get_objects_by_object_ids(params))
    if principal:
        return principal[0]
    return None


def get_principal_details(principal: Any) -> dict[str, Any]:
    """Get details of a service principal.

    Args:
        principal: The principal to get details for.

    Returns:
        A dictionary of principal details including type, display name and email.
    """
    principal_type = type(principal)
    mail = None
    display_name = "Unknown"
    if hasattr(principal, "display_name"):
        display_name = principal.display_name
    if hasattr(principal, "mail"):
        mail = principal.mail
    return {
        "principal_type": principal_type,
        "display_name": display_name,
        "mail": mail,
    }


def get_ad_group_principals(
    group: Any, graph_client: GraphRbacManagementClient
) -> list:
    """Get the members of a given AD group and extract their principal information.

    Args:
        group: The AD group to get members for.
        graph_client: The graph client to check the principal.

    Returns:
        A list of principal details.
    """
    group_principal = list(graph_client.groups.get_group_members(group.object_id))
    group_principal_details = []
    for principal in group_principal:
        principal_details = get_principal_details(principal)
        principal_details["principal_type"] = type(group)
        group_principal_details.append(principal_details)
    return group_principal_details


def get_role_assignment_models(
    assignment: Any, role_name: str, graph_client: GraphRbacManagementClient
) -> list[models.RoleAssignment]:
    """Populate RoleAssignment objects with principal role details.

    Args:
        assignment: The role assignment to get details for.
        role_name: The name of the role.
        graph_client: The graph client to check the principal.

    Returns:
        A list of RoleAssignment objects.
    """
    principal_details = []
    principal = get_principal(assignment.principal_id, graph_client)
    if principal:
        if isinstance(principal, ADGroup):
            principal_details.extend(get_ad_group_principals(principal, graph_client))
        else:
            principal_details.append(get_principal_details(principal))
    else:
        logger.warning(
            "Could not retrieve principal data for principal id %s",
            assignment.principal_id,
        )
    return [
        models.RoleAssignment(
            role_definition_id=assignment.role_definition_id,
            role_name=role_name,
            principal_id=assignment.principal_id,
            scope=assignment.scope,
            **x
        )
        for x in principal_details
    ]


def get_subscription_role_assignment_models(
    subscription: Any,
    graph_client: GraphRbacManagementClient,
) -> list[RoleAssignment]:
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
    try:
        role_assignments_models = []
        for assignment in assignments_list:
            role_assignments_models += get_role_assignment_models(
                assignment,
                role_def_dict.get(assignment.role_definition_id, "Unknown"),
                graph_client,
            )
    except CloudError as e:
        logger.error(
            "Could not retrieve role assignments. Do we have GraphAPI permissions?"
        )
        logger.error(e)
        role_assignments_models = []
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

    graph_client = GraphRbacManagementClient(
        credentials=GRAPH_CREDENTIALS, tenant_id=str(tenant_id)
    )

    client = SubscriptionClient(credential=CREDENTIALS)
    subscriptions = client.subscriptions.list()

    data: list[models.SubscriptionStatus] = []
    for i, subscription in enumerate(subscriptions):
        if i % 10 == 0:
            logger.info("%s subscriptions processed.", i)

        role_assignments_models = get_subscription_role_assignment_models(
            subscription, graph_client
        )
        if (
            subscription.subscription_id is not None
            and subscription.display_name is not None
            and subscription.state is not None
        ):
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

    send_status(config.API_URL, status)
    logger.warning(
        "Credential type used was: %s",
        type(CREDENTIALS._successful_credential),  # pylint: disable=W0212
    )
