"""Pydantic models for the Azure status functions."""
from enum import Enum
from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel


class RoleAssignment(BaseModel):
    """Role assignment model.

    Attributes:
        role_definition_id: The role definition ID.
        role_name: The role name.
        principal_id: The principal ID.
        display_name: The display name of the role.
        mail: The email address for the user.
        scope: The scope of the role.
    """

    role_definition_id: str
    role_name: str
    principal_id: str
    display_name: str
    mail: Optional[str]
    scope: Optional[str]


class SubscriptionState(str, Enum):
    """The state of the subscription.

    See https://learn.microsoft.com/en-us/azure/cost-management-billing/manage/subscription-states # noqa pylint: disable=C0301

    Attributes:
        DELETED: The subscription has been deleted.
        DISABLED: The subscription has been disabled.
        ENABLED: The subscription is enabled.
        PASTDUE: The subscription is past due.
        WARNED: The subscription is warned.
    """

    DELETED = "Deleted"
    DISABLED = "Disabled"
    ENABLED = "Enabled"
    PASTDUE = "PastDue"
    WARNED = "Warned"


class SubscriptionStatus(BaseModel):
    """The status of a subscription.

    See https://docs.microsoft.com/en-us/rest/api/resources/subscriptions/list#subscription  # noqa pylint: disable=C0301

    Attributes:
        subscription_id: The subscription ID.
        display_name: The display name of the subscription.
        state: The state of the subscription.
        role_assignments: The role assignments for the subscription.
    """

    subscription_id: UUID
    display_name: str
    state: SubscriptionState
    role_assignments: Tuple[RoleAssignment, ...]


class AllSubscriptionStatus(BaseModel):
    """Subscription status for all subscriptions.

    Attributes:
        status_list: A list of subscription statuses.
    """

    status_list: List[SubscriptionStatus]
