"""Example source node for the walking-skeleton loop."""

from __future__ import annotations

from calc_types.example import BaseValue
from registry.decorators import node


@node(
    node_type="data_retrieval",
    description="Return a deterministic example base value.",
    when_to_use="Use for the example doubling calculation.",
    assumptions=["Hard-coded only for framework smoke testing."],
    references=[],
)
def example_source_value() -> BaseValue:
    return BaseValue(value=21.0)
