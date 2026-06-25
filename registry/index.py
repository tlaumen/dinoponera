"""Explicit source of truth for registered calculation nodes."""

from __future__ import annotations

from collections.abc import Callable

from dinoponera.core.models import NodeSummary
from dinoponera.core.registry_introspection import build_summary
from registry.nodes.double_value import double_value
from registry.nodes.example_source_value import example_source_value
from registry.nodes.format_result import format_result

NODES: list[Callable[..., object]] = [
    example_source_value,
    double_value,
    format_result,
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
