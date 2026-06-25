"""Example computation node for the walking-skeleton loop."""

from __future__ import annotations

from calc_types.example import BaseValue, DoubledValue
from registry.decorators import node


@node(
    node_type="computation",
    description="Double an input value.",
    when_to_use="Use when a BaseValue should be multiplied by two.",
    assumptions=[],
    references=[],
)
def double_value(base: BaseValue) -> DoubledValue:
    return DoubledValue(value=base.value * 2)
