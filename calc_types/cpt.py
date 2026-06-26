"""CPT domain types for geotechnical manual-test calculations."""

from __future__ import annotations

from pydantic import BaseModel


class CptPoint(BaseModel):
    depth_m: float
    cone_resistance_mpa: float
    sleeve_friction_kpa: float


class CptData(BaseModel):
    source_name: str
    points: list[CptPoint]
