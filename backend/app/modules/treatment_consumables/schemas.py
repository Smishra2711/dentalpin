"""Pydantic schemas for treatment_consumables."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConsumableLinkCreate(BaseModel):
    catalog_item_id: UUID
    inventory_item_id: UUID
    quantity: Decimal = Field(gt=0, le=9999)


class ConsumableLinkUpdate(BaseModel):
    quantity: Decimal = Field(gt=0, le=9999)


class ConsumableLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clinic_id: UUID
    catalog_item_id: UUID
    inventory_item_id: UUID
    quantity: Decimal
    created_at: datetime
    updated_at: datetime


class ConsumableLinkDetailed(ConsumableLinkResponse):
    """Row enriched with display names read from catalog/inventory."""

    treatment_name: str
    treatment_code: str | None = None
    item_name: str
    item_unit: str | None = None


class LinkOptionsTreatment(BaseModel):
    id: UUID
    name: str
    internal_code: str | None = None


class LinkOptionsItem(BaseModel):
    id: UUID
    name: str
    unit: str | None = None


class LinkOptionsResponse(BaseModel):
    treatments: list[LinkOptionsTreatment]
    items: list[LinkOptionsItem]
