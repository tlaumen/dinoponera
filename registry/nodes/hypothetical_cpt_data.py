"""Deterministic hypothetical CPT source node for geotechnical manual tests."""

from __future__ import annotations

from calc_types.cpt import CptData, CptPoint
from registry.decorators import node


@node(
    node_type="data_retrieval",
    description="Return deterministic CPT data representing a hypothetical source file.",
    when_to_use="Use when a geotechnical manual test should follow the CPT-derived settlement path.",
    assumptions=[
        "CPT points are hard-coded and illustrative.",
        "The source name represents a hypothetical file; no file parsing is performed.",
    ],
    references=[],
)
def hypothetical_cpt_data() -> CptData:
    return CptData(
        source_name="hypothetical_cpt_file.csv",
        points=[
            CptPoint(depth_m=0.0, cone_resistance_mpa=4.0, sleeve_friction_kpa=35.0),
            CptPoint(depth_m=2.0, cone_resistance_mpa=5.0, sleeve_friction_kpa=42.0),
            CptPoint(depth_m=5.0, cone_resistance_mpa=8.0, sleeve_friction_kpa=55.0),
            CptPoint(depth_m=8.0, cone_resistance_mpa=10.0, sleeve_friction_kpa=62.0),
        ],
    )
