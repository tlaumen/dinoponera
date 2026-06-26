"""Illustrative CPT-derived pile-foundation parameter node."""

from __future__ import annotations

from calc_types.cpt import CptData
from calc_types.piled_foundation import PileFoundationParameters
from registry.decorators import node


@node(
    node_type="computation",
    description="Derive illustrative pile resistance parameters from CPT averages.",
    when_to_use="Use when piled-foundation capacity parameters should be derived from CPT data.",
    assumptions=[
        "Average sleeve friction is used as unit shaft resistance.",
        "Unit base resistance is 15 percent of average cone resistance converted from MPa to kPa.",
        "Resistance factor is fixed at 2.0.",
        "This is illustrative manual-test logic, not a production geotechnical design correlation.",
    ],
    references=[],
)
def derive_pile_foundation_parameters_from_cpt(
    cpt: CptData,
) -> PileFoundationParameters:
    point_count = len(cpt.points)
    average_qc_kpa = (
        sum(point.cone_resistance_mpa for point in cpt.points) / point_count
    ) * 1000
    average_fs_kpa = sum(point.sleeve_friction_kpa for point in cpt.points) / point_count

    return PileFoundationParameters(
        unit_shaft_resistance_kpa=average_fs_kpa,
        unit_base_resistance_kpa=0.15 * average_qc_kpa,
        resistance_factor=2.0,
    )
