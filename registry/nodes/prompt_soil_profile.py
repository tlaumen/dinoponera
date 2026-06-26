"""Interactive manual soil-profile source node for settlement manual tests."""

from __future__ import annotations

from calc_types.soil import SoilLayer, SoilProfile
from registry.decorators import node


@node(
    node_type="user_input",
    description="Prompt for a layered soil profile for an illustrative settlement calculation.",
    when_to_use="Use when the settlement manual test should use manually entered soil layers.",
    assumptions=[
        "Interactive source node intended for manual workflow testing.",
        "Entered compressibility values are illustrative and chosen so the settlement formula returns millimetres.",
    ],
    references=[],
)
def prompt_soil_profile() -> SoilProfile:
    layer_count = int(input("Number of soil layers: "))
    layers: list[SoilLayer] = []

    for index in range(layer_count):
        layer_number = index + 1
        name = input(f"Layer {layer_number} name: ")
        top_m = float(input(f"Layer {layer_number} top depth (m): "))
        bottom_m = float(input(f"Layer {layer_number} bottom depth (m): "))
        compressibility_per_kpa = float(
            input(f"Layer {layer_number} compressibility per kPa: ")
        )
        layers.append(
            SoilLayer(
                name=name,
                top_m=top_m,
                bottom_m=bottom_m,
                compressibility_per_kpa=compressibility_per_kpa,
            )
        )

    return SoilProfile(layers=layers)
