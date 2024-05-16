"""Pydantic models for the Azure usage functions."""
import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, confloat


class HashBaseModel(BaseModel):
    """BaseModel with hash.

    This allows unique data generation for property based tests.
    """

    def __hash__(self) -> int:
        """Hash the model."""
        return hash((type(self),) + tuple(self.__dict__.values()))


class Currency(str, Enum):
    """A class for Azure billing currencies."""

    USD = "USD"
    GBP = "GBP"


class Usage(HashBaseModel):
    """A class for Azure subscription usage."""

    id: str
    name: Optional[str] = None
    type: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    billing_account_id: Optional[str] = None
    billing_account_name: Optional[str] = None
    billing_period_start_date: Optional[datetime.date] = None
    billing_period_end_date: Optional[datetime.date] = None
    billing_profile_id: Optional[str] = None
    billing_profile_name: Optional[str] = None
    account_owner_id: Optional[str] = None
    account_name: Optional[str] = None
    subscription_id: UUID
    subscription_name: Optional[str] = None
    date: datetime.date
    product: Optional[str] = None
    part_number: Optional[str] = None
    meter_id: Optional[str] = None
    quantity: Optional[float] = None
    effective_price: Optional[float] = None
    cost: confloat(ge=0.0)  # type: ignore
    amortised_cost: Optional[float] = None
    total_cost: Optional[float] = None
    unit_price: Optional[float] = None
    billing_currency: Optional[str] = None
    resource_location: Optional[str] = None
    consumed_service: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    service_info1: Optional[str] = None
    service_info2: Optional[str] = None
    additional_info: Optional[str] = None
    invoice_section: Optional[str] = None
    cost_center: Optional[str] = None
    resource_group: Optional[str] = None
    reservation_id: Optional[str] = None
    reservation_name: Optional[str] = None
    product_order_id: Optional[str] = None
    offer_id: Optional[str] = None
    is_azure_credit_eligible: Optional[bool] = None
    term: Optional[str] = None
    publisher_name: Optional[str] = None
    publisher_type: Optional[str] = None
    plan_name: Optional[str] = None
    charge_type: Optional[str] = None
    frequency: Optional[str] = None
    monthly_upload: Optional[datetime.date] = None


class AllUsage(BaseModel):
    """A Usage container."""

    usage_list: List[Usage]


class CMUsage(HashBaseModel):
    """A class for Cost Management Usage."""

    subscription_id: UUID
    name: Optional[str] = None
    start_datetime: datetime.date
    end_datetime: datetime.date
    cost: confloat(ge=0.0)  # type: ignore
    billing_currency: str


class AllCMUsage(BaseModel):
    """A wrapper for a list of Cost Management Usage."""

    cm_usage_list: List[CMUsage]


class Budget(BaseModel):
    """A class for our concept of a budget."""

    name: str
    start: datetime.date
    end: datetime.date
    currency: Currency
    amount: float
