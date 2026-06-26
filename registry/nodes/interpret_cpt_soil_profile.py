"""Illustrative CPT-to-soil-profile interpretation node."""

from __future__ import annotations

from calc_types.cpt import CptData
from calc_types.soil import SoilLayer, SoilProfile
from registry.decorators import node


@node(
    node_type="computation",
    description="Interpret adjacent CPT depth intervals as settlement soil layers.",
    when_to_use="Use when settlement inputs should be derived from the hypothetical CPT data path.",
    assumptions=[
        "Creates one layer per adjacent CPT depth interval.",
        "Layer compressibility is computed as 0.2 divided by average cone resistance in MPa.",
        "This is illustrative manual-test logic, not a geotechnical design-standard interpretation.",
    ],
    references=[],
)
def interpret_cpt_soil_profile(cpt: CptData) -> SoilProfile:
    points = sorted(cpt.points, key=lambda point: point.depth_m)
    layers: list[SoilLayer] = []

    for index, (top_point, bottom_point) in enumerate(zip(points, points[1:]), start=1):
        average_cone_resistance_mpa = (
            top_point.cone_resistance_mpa + bottom_point.cone_resistance_mpa
        ) / 2
        compressibility_per_kpa = 0.2 / average_cone_resistance_mpa
        layers.append(
            SoilLayer(
                name=f"CPT layer {index}",
                top_m=top_point.depth_m,
                bottom_m=bottom_point.depth_m,
                compressibility_per_kpa=compressibility_per_kpa,
            )
        )

    return SoilProfile(layers=layers)
