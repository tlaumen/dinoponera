"""Illustrative CPT-derived settlement parameter node."""

from __future__ import annotations

from calc_types.cpt import CptData
from calc_types.settlement import SettlementParameters
from registry.decorators import node


@node(
    node_type="computation",
    description="Derive illustrative settlement load parameters from CPT data.",
    when_to_use="Use when settlement parameters should come from the CPT-derived manual-test path.",
    assumptions=[
        "Returns a fixed representative surface load of 100 kPa for deterministic manual testing.",
        "The CPT argument establishes provenance for the path; this is not a production load derivation.",
    ],
    references=[],
)
def derive_settlement_parameters_from_cpt(cpt: CptData) -> SettlementParameters:
    _ = cpt.source_name
    return SettlementParameters(surface_load_kpa=100.0)
