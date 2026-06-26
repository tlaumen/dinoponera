"""Soil profile domain types for geotechnical manual-test calculations."""

from __future__ import annotations

from pydantic import BaseModel


class SoilLayer(BaseModel):
    name: str
    top_m: float
    bottom_m: float
    compressibility_per_kpa: float


class SoilProfile(BaseModel):
    layers: list[SoilLayer]
