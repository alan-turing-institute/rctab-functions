"""Pydantic models for the Azure status functions."""
from enum import Enum
from typing import List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel


class HashBaseModel(BaseModel):
    """BaseModel with hash.

    This allows unique data generation for property based tests.
    """

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.__dict__.values()))


class RoleAssignment(BaseModel):
    role_definition_id: str
    role_name: str
    principal_id: str
    display_name: str
    mail: Optional[str]
    scope: Optional[str]


class SubscriptionState(str, Enum):
    DELETED = "Deleted"
    DISABLED = "Disabled"
    ENABLED = "Enabled"
    PASTDUE = "PastDue"
    WARNED = "Warned"


class SubscriptionStatus(BaseModel):
    # See https://docs.microsoft.com/en-us/rest/api/resources/subscriptions/list#subscription  # noqa pylint: disable=C0301
    subscription_id: UUID
    display_name: str
    state: SubscriptionState
    role_assignments: Tuple[RoleAssignment, ...]


class AllSubscriptionStatus(BaseModel):
    status_list: List[SubscriptionStatus]
