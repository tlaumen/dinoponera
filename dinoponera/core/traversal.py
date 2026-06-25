"""Dependency traversal helpers for partially built calculation graphs."""

from __future__ import annotations

from typing import Protocol

from dinoponera.core.lint import LEAF_NODE_TYPES
from dinoponera.core.models import CalculationGraph, NodeSummary, UnresolvedInput


class DependencyTraversal(Protocol):
    def next_unresolved(
        self,
        graph: CalculationGraph,
        registry: list[NodeSummary],
    ) -> UnresolvedInput | None: ...


class BreadthFirstTraversal:
    """Find the first graph input not satisfied by an incoming named edge.

    Traversal follows graph.nodes order, which is how planning appends newly
    discovered dependencies. Leaf nodes do not require incoming edges.
    """

    def next_unresolved(
        self,
        graph: CalculationGraph,
        registry: list[NodeSummary],
    ) -> UnresolvedInput | None:
        summary_by_id = {summary.id: summary for summary in registry}

        for node_id in graph.nodes:
            summary = summary_by_id.get(node_id)
            if summary is None or summary.node_type in LEAF_NODE_TYPES:
                continue
            for node_input in summary.inputs:
                if not graph.has_edge(
                    to=node_id,
                    to_input=node_input.name,
                    type=node_input.type,
                ):
                    return UnresolvedInput(
                        node_id=node_id,
                        input_name=node_input.name,
                        input_type=node_input.type,
                    )
        return None
