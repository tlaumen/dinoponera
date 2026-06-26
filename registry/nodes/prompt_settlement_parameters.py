"""Interactive manual settlement-parameter source node."""

from __future__ import annotations

from calc_types.settlement import SettlementParameters
from registry.decorators import node


@node(
    node_type="user_input",
    description="Prompt for settlement load parameters for an illustrative manual test.",
    when_to_use="Use when the settlement manual test should use a manually entered surface load.",
    assumptions=["Interactive source node intended for manual workflow testing."],
    references=[],
)
def prompt_settlement_parameters() -> SettlementParameters:
    return SettlementParameters(surface_load_kpa=float(input("Surface load (kPa): ")))
