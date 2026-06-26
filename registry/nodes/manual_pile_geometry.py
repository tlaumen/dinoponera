"""Representative manual pile-geometry source node."""

from __future__ import annotations

from calc_types.piled_foundation import PileGeometry
from registry.decorators import node


@node(
    node_type="user_input",
    description="Return representative pile geometry for an illustrative CPT pile-capacity manual test.",
    when_to_use="Use when the piled-foundation CPT manual workflow needs a simple manual design geometry input.",
    assumptions=[
        "Returns deterministic representative geometry rather than prompting interactively.",
        "Intended for manual workflow testing, not project-specific pile design.",
    ],
    references=[],
)
def manual_pile_geometry() -> PileGeometry:
    return PileGeometry(diameter_m=0.6, embedded_length_m=12.0)
