"""Terminal illustrative settlement calculation node."""

from __future__ import annotations

from calc_types.settlement import (
    SettlementLayerContribution,
    SettlementParameters,
    SettlementResult,
)
from calc_types.soil import SoilProfile
from registry.decorators import node


@node(
    node_type="computation",
    description="Calculate illustrative layered soil-compressibility settlement.",
    when_to_use="Use as the terminal node for manual or CPT-derived settlement manual tests.",
    assumptions=[
        "Layer settlement is surface_load_kpa * compressibility_per_kpa * thickness_m.",
        "Compressibility inputs are assumed to be scaled so the formula returns millimetres.",
        "This is illustrative manual-test logic, not a production geotechnical design method.",
    ],
    references=[],
)
def calculate_settlement(
    soil_profile: SoilProfile,
    parameters: SettlementParameters,
) -> SettlementResult:
    contributions: list[SettlementLayerContribution] = []

    for layer in soil_profile.layers:
        thickness_m = layer.bottom_m - layer.top_m
        settlement_mm = (
            parameters.surface_load_kpa * layer.compressibility_per_kpa * thickness_m
        )
        contributions.append(
            SettlementLayerContribution(
                layer_name=layer.name,
                thickness_m=thickness_m,
                compressibility_per_kpa=layer.compressibility_per_kpa,
                settlement_mm=settlement_mm,
            )
        )

    return SettlementResult(
        total_settlement_mm=sum(
            contribution.settlement_mm for contribution in contributions
        ),
        contributions=contributions,
        notes=[
            "Illustrative layered compressibility settlement calculation for manual workflow testing only.",
            "Not a production-grade or design-standard geotechnical settlement method.",
        ],
    )
