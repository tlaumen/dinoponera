"""Piled-foundation domain types for geotechnical manual-test calculations."""

from __future__ import annotations

from pydantic import BaseModel


class PileGeometry(BaseModel):
    diameter_m: float
    embedded_length_m: float


class PileFoundationParameters(BaseModel):
    unit_shaft_resistance_kpa: float
    unit_base_resistance_kpa: float
    resistance_factor: float


class PileFoundationResult(BaseModel):
    shaft_capacity_kn: float
    base_capacity_kn: float
    ultimate_capacity_kn: float
    design_capacity_kn: float
    notes: list[str]
