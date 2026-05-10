from decimal import Decimal

from pydantic import BaseModel, Field


class SettingsOut(BaseModel):
    retail_markup: Decimal


class SettingsUpdate(BaseModel):
    retail_markup: Decimal | None = Field(None, ge=0)
