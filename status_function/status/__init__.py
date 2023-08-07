"""An Azure Function App to collect status information."""
import logging
from datetime import datetime
from functools import lru_cache

import azure.functions as func
import requests
from azure.graphrbac import GraphRbacManagementClient
from azure.graphrbac.models import ADGroup, GetObjectsParameters
from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient as AuthClient
from azure.mgmt.subscription import SubscriptionClient
from msrestazure.azure_exceptions import CloudError

from status import models, settings
from status.auth import BearerAuth
from status.logutils import set_log_handler
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


def send_status(hostname_or_ip, status_data):
    """Post each item of status_data to a route."""
    logger.warning("Sending status data.")

    for _ in range(2):
        started_sending_at = datetime.now()
        resp = requests.post(
            hostname_or_ip + "/accounting/all-status",
            models.AllSubscriptionStatus(status_list=status_data).json(),
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


def get_role_assignments_list(auth_client):
    # https://docs.microsoft.com/en-us/python/api/azure-mgmt-authorization/azure.mgmt.authorization.v2015_07_01.models.roleassignmentlistresult?view=azure-python
    return list(auth_client.role_assignments.list())


def get_role_def_dict(auth_client, subscription_id):
    role_defs = list(
        auth_client.role_definitions.list(scope="/subscriptions/" + subscription_id)
    )
    return {x.id: x.role_name for x in role_defs}


def get_auth_client(subscription):
    return AuthClient(
        credential=CREDENTIALS, subscription_id=subscription.subscription_id
    )


@lru_cache(maxsize=500)
def get_principal(principal_id, graph_client):
    """Get service principal"""
    params = GetObjectsParameters(
        include_directory_object_references=True,
        object_ids=[principal_id],
    )
    principal = list(graph_client.objects.get_objects_by_object_ids(params))
    if principal:
        return principal[0]
    return None


def get_principal_details(principal):
    """Get details of a service principal, e.g. type, display name and email"""
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


def get_ad_group_principals(group, graph_client):
    """Get the members of a given AD group and extract their principal information."""
    group_principal = list(graph_client.groups.get_group_members(group.object_id))
    group_principal_details = []
    for principal in group_principal:
        principal_details = get_principal_details(principal)
        principal_details["principal_type"] = type(group)
        group_principal_details.append(principal_details)
    return group_principal_details


def get_role_assignment_models(assignment, role_name, graph_client):
    """Populate RoleAssignment objects with principal role details."""
    principal_details = []
    principal = get_principal(assignment.properties.principal_id, graph_client)
    if principal:
        if isinstance(principal, ADGroup):
            principal_details.extend(get_ad_group_principals(principal, graph_client))
        else:
            principal_details.append(get_principal_details(principal))
    else:
        logger.warning(
            "Could not retrieve principal data for principal id %s",
            assignment.properties.principal_id,
        )
    return [
        models.RoleAssignment(
            role_definition_id=assignment.properties.role_definition_id,
            role_name=role_name,
            principal_id=assignment.properties.principal_id,
            scope=assignment.properties.scope,
            **x
        )
        for x in principal_details
    ]


def get_subscription_role_assignment_models(subscription, graph_client):
    """Get the role assignment models for each a subscription."""
    auth_client = get_auth_client(subscription)
    role_def_dict = get_role_def_dict(auth_client, subscription.subscription_id)
    assignments_list = get_role_assignments_list(auth_client)
    try:
        role_assignments_models = []
        for assignment in assignments_list:
            role_assignments_models += get_role_assignment_models(
                assignment,
                role_def_dict.get(assignment.properties.role_definition_id),
                graph_client,
            )
    except CloudError as e:
        logger.error(
            "Could not retrieve role assignments. Do we have GraphAPI permissions?"
        )
        logger.error(e)
        role_assignments_models = []
    return role_assignments_models


def get_all_status(tenant_id):
    """Get status and role assignments for all subscriptions."""

    logger.warning("Getting all status data.")
    started_at = datetime.now()

    graph_client = GraphRbacManagementClient(
        credentials=GRAPH_CREDENTIALS, tenant_id=tenant_id
    )

    client = SubscriptionClient(credential=CREDENTIALS)
    subscriptions = client.subscriptions.list()

    data = []
    for i, subscription in enumerate(subscriptions):
        if i % 10 == 0:
            logger.info("%s subscriptions processed.", i)

        role_assignments_models = get_subscription_role_assignment_models(
            subscription, graph_client
        )
        data.append(
            models.SubscriptionStatus(
                subscription_id=subscription.subscription_id,
                display_name=subscription.display_name,
                state=subscription.state,
                role_assignments=role_assignments_models,
            )
        )

    logger.warning("Status data retrieved in %s.", str(datetime.now() - started_at))
    return data


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
    logger.warning("Status function starting.")

    if mytimer.past_due:
        logger.info("The timer is past due.")

    status = get_all_status(config.AZURE_TENANT_ID)

    send_status(config.API_URL, status)
    logger.warning(
        "Credential type used was: %s",
        type(CREDENTIALS._successful_credential),  # pylint: disable=W0212
    )
