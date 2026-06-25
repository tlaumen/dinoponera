"""Decorators and metadata for hand-authored calculation nodes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TypeVar

F = TypeVar("F", bound=Callable[..., object])


@dataclass(frozen=True)
class NodeMetadata:
    node_type: str
    description: str
    when_to_use: str
    assumptions: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)


def node(
    *,
    node_type: str,
    description: str,
    when_to_use: str,
    assumptions: list[str] | None = None,
    references: list[str] | None = None,
) -> Callable[[F], F]:
    """Attach calculation-node metadata to a Python function."""

    metadata = NodeMetadata(
        node_type=node_type,
        description=description,
        when_to_use=when_to_use,
        assumptions=list(assumptions or []),
        references=list(references or []),
    )

    def decorate(fn: F) -> F:
        setattr(fn, "_node_metadata", metadata)
        return fn

    return decorate
