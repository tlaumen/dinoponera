"""Example terminal node for the walking-skeleton loop."""

from __future__ import annotations

from calc_types.example import CalculationResult, DoubledValue
from registry.decorators import node


@node(
    node_type="computation",
    description="Format the doubled value as the terminal calculation result.",
    when_to_use="Use as the terminal node for the example doubling calculation.",
    assumptions=[],
    references=[],
)
def format_result(doubled: DoubledValue) -> CalculationResult:
    return CalculationResult(message="Doubled value", value=doubled.value)
