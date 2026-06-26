"""Terminal illustrative piled-foundation capacity calculation node."""

from __future__ import annotations

from math import pi

from calc_types.cpt import CptData
from calc_types.piled_foundation import (
    PileFoundationParameters,
    PileFoundationResult,
    PileGeometry,
)
from registry.decorators import node


@node(
    node_type="computation",
    description="Calculate illustrative shaft plus base piled-foundation capacity.",
    when_to_use="Use as the terminal node for the CPT-required piled-foundation manual workflow.",
    assumptions=[
        "Shaft capacity is unit_shaft_resistance_kpa * perimeter_m * embedded_length_m.",
        "Base capacity is unit_base_resistance_kpa * base_area_m2.",
        "Design capacity is ultimate capacity divided by resistance factor.",
        "This calculation requires CPT provenance and is illustrative manual-test logic only.",
    ],
    references=[],
)
def calculate_pile_foundation_capacity(
    geometry: PileGeometry,
    parameters: PileFoundationParameters,
    cpt: CptData,
) -> PileFoundationResult:
    perimeter_m = pi * geometry.diameter_m
    base_area_m2 = pi * geometry.diameter_m**2 / 4
    shaft_capacity_kn = (
        parameters.unit_shaft_resistance_kpa
        * perimeter_m
        * geometry.embedded_length_m
    )
    base_capacity_kn = parameters.unit_base_resistance_kpa * base_area_m2
    ultimate_capacity_kn = shaft_capacity_kn + base_capacity_kn
    design_capacity_kn = ultimate_capacity_kn / parameters.resistance_factor

    return PileFoundationResult(
        shaft_capacity_kn=shaft_capacity_kn,
        base_capacity_kn=base_capacity_kn,
        ultimate_capacity_kn=ultimate_capacity_kn,
        design_capacity_kn=design_capacity_kn,
        notes=[
            "Illustrative CPT-required pile capacity calculation for manual workflow testing only.",
            "Not a production-grade or design-standard geotechnical pile design method.",
            f"CPT source {cpt.source_name} with {len(cpt.points)} points was provided to the terminal node.",
        ],
    )
