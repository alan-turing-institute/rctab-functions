"""Pydantic models for the Azure status functions."""
from enum import Enum
from typing import List
from uuid import UUID

from pydantic import BaseModel


class HashBaseModel(BaseModel):
    """BaseModel with hash. This allows unique data generation for property based
    tests."""

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.__dict__.values()))


class SubscriptionState(str, Enum):
    DELETED = "Deleted"
    DISABLED = "Disabled"
    ENABLED = "Enabled"
    PASTDUE = "PastDue"
    WARNED = "Warned"


class SubscriptionStatus(BaseModel):
    subscription_id: UUID
    display_name: str
    state: SubscriptionState


class AllSubscriptionStatus(BaseModel):
    subscription_status_list: List[SubscriptionStatus]


class DesiredState(HashBaseModel):
    subscription_id: UUID
    desired_state: SubscriptionState
