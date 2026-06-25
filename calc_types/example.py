"""Small example domain types used by the walking-skeleton loop."""

from __future__ import annotations

from pydantic import BaseModel


class BaseValue(BaseModel):
    value: float


class DoubledValue(BaseModel):
    value: float


class CalculationResult(BaseModel):
    message: str
    value: float
