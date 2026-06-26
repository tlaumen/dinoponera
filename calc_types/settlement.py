"""Settlement domain types for geotechnical manual-test calculations."""

from __future__ import annotations

from pydantic import BaseModel


class SettlementParameters(BaseModel):
    surface_load_kpa: float


class SettlementLayerContribution(BaseModel):
    layer_name: str
    thickness_m: float
    compressibility_per_kpa: float
    settlement_mm: float


class SettlementResult(BaseModel):
    total_settlement_mm: float
    contributions: list[SettlementLayerContribution]
    notes: list[str]
