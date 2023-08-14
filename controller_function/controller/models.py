"""Pydantic models for the Azure status functions."""
from enum import Enum
from typing import List
from uuid import UUID

from pydantic import BaseModel


class HashBaseModel(BaseModel):
    """BaseModel with hash.

    This allows unique data generation for property based tests.
    """

    def __hash__(self) -> int:
        """Hash the model."""
        return hash((type(self),) + tuple(self.__dict__.values()))


class SubscriptionState(str, Enum):
    """The possible states of a subscription."""

    DELETED = "Deleted"
    DISABLED = "Disabled"
    ENABLED = "Enabled"
    PASTDUE = "PastDue"
    WARNED = "Warned"


class SubscriptionStatus(BaseModel):
    """A class for the current name and state of a subscription."""

    subscription_id: UUID
    display_name: str
    state: SubscriptionState


class AllSubscriptionStatus(BaseModel):
    """A wrapper for a list of subscription status objects."""

    subscription_status_list: List[SubscriptionStatus]


class DesiredState(HashBaseModel):
    """A class for the desired state of a subscription."""

    subscription_id: UUID
    desired_state: SubscriptionState
