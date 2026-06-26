"""Explicit source of truth for registered calculation nodes."""

from __future__ import annotations

from collections.abc import Callable

from dinoponera.core.models import NodeSummary
from dinoponera.core.registry_introspection import build_summary
from registry.nodes.calculate_pile_foundation_capacity import (
    calculate_pile_foundation_capacity,
)
from registry.nodes.calculate_settlement import calculate_settlement
from registry.nodes.derive_pile_foundation_parameters_from_cpt import (
    derive_pile_foundation_parameters_from_cpt,
)
from registry.nodes.derive_settlement_parameters_from_cpt import (
    derive_settlement_parameters_from_cpt,
)
from registry.nodes.double_value import double_value
from registry.nodes.example_source_value import example_source_value
from registry.nodes.format_result import format_result
from registry.nodes.hypothetical_cpt_data import hypothetical_cpt_data
from registry.nodes.interpret_cpt_soil_profile import interpret_cpt_soil_profile
from registry.nodes.manual_pile_geometry import manual_pile_geometry
from registry.nodes.prompt_settlement_parameters import prompt_settlement_parameters
from registry.nodes.prompt_soil_profile import prompt_soil_profile

NODES: list[Callable[..., object]] = [
    example_source_value,
    double_value,
    format_result,
    prompt_soil_profile,
    prompt_settlement_parameters,
    hypothetical_cpt_data,
    interpret_cpt_soil_profile,
    derive_settlement_parameters_from_cpt,
    calculate_settlement,
    manual_pile_geometry,
    derive_pile_foundation_parameters_from_cpt,
    calculate_pile_foundation_capacity,
]


class RegistryError(ValueError):
    """Raised when registry lookups or registry integrity checks fail."""


def _node_map() -> dict[str, Callable[..., object]]:
    result: dict[str, Callable[..., object]] = {}
    for fn in NODES:
        node_id = fn.__name__
        if node_id in result:
            raise RegistryError(f"Duplicate node id in registry: {node_id}")
        result[node_id] = fn
    return result


def summaries() -> list[NodeSummary]:
    return [build_summary(fn) for fn in _node_map().values()]


def get(node_id: str) -> Callable[..., object]:
    try:
        return _node_map()[node_id]
    except KeyError as exc:
        raise RegistryError(f"Unknown node id: {node_id}") from exc


def get_summary(node_id: str) -> NodeSummary:
    return build_summary(get(node_id))


def exists(node_id: str) -> bool:
    return node_id in _node_map()
