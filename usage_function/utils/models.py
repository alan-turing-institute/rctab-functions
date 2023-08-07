"""Pydantic models for the Azure usage functions."""
import datetime
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, confloat


class HashBaseModel(BaseModel):
    """BaseModel with hash. This allows unique data generation for property based
    tests."""

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.__dict__.values()))


class Currency(str, Enum):
    """A class for Azure billing currencies."""

    USD = "USD"
    GBP = "GBP"


class Usage(HashBaseModel):
    """A class for Azure subscription usage."""

    id: str
    name: Optional[str]
    type: Optional[str]
    tags: Optional[Dict[str, str]]
    billing_account_id: Optional[str]
    billing_account_name: Optional[str]
    billing_period_start_date: Optional[datetime.date]
    billing_period_end_date: Optional[datetime.date]
    billing_profile_id: Optional[str]
    billing_profile_name: Optional[str]
    account_owner_id: Optional[str]
    account_name: Optional[str]
    subscription_id: UUID
    subscription_name: Optional[str]
    date: datetime.date
    product: Optional[str]
    part_number: Optional[str]
    meter_id: Optional[str]
    quantity: Optional[float]
    effective_price: Optional[float]
    cost: confloat(ge=0.0)  # type: ignore
    amortised_cost: Optional[float]
    total_cost: Optional[float]
    unit_price: Optional[float]
    billing_currency: Optional[str]
    resource_location: Optional[str]
    consumed_service: Optional[str]
    resource_id: Optional[str]
    resource_name: Optional[str]
    service_info1: Optional[str]
    service_info2: Optional[str]
    additional_info: Optional[str]
    invoice_section: Optional[str]
    cost_center: Optional[str]
    resource_group: Optional[str]
    reservation_id: Optional[str]
    reservation_name: Optional[str]
    product_order_id: Optional[str]
    offer_id: Optional[str]
    is_azure_credit_eligible: Optional[bool]
    term: Optional[str]
    publisher_name: Optional[str]
    publisher_type: Optional[str]
    plan_name: Optional[str]
    charge_type: Optional[str]
    frequency: Optional[str]
    monthly_upload: Optional[datetime.date]


class AllUsage(BaseModel):
    """A Usage container."""

    usage_list: List[Usage]


class CMUsage(HashBaseModel):
    subscription_id: UUID
    name: Optional[str]
    start_datetime: datetime.date
    end_datetime: datetime.date
    cost: confloat(ge=0.0)  # type: ignore
    billing_currency: str


class AllCMUsage(BaseModel):
    cm_usage_list: List[CMUsage]


class Budget(BaseModel):
    """A class for our concept of a budget."""

    name: str
    start: datetime.date
    end: datetime.date
    currency: Currency
    amount: float
