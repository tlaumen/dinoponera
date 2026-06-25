"""Pure validation for approved calculation graphs."""

from __future__ import annotations

from collections import defaultdict, deque

from dinoponera.core.models import CalculationGraph, NodeSummary

LEAF_NODE_TYPES = {"data_retrieval", "user_input"}


class GraphLintError(ValueError):
    """Base class for graph lint failures."""


class DuplicateNodeError(GraphLintError):
    """Raised when node IDs are duplicated."""


class UnknownNodeError(GraphLintError):
    """Raised when a graph references a node outside the registry/graph."""


class CyclicGraphError(GraphLintError):
    """Raised when graph edges contain a cycle."""


class MissingInputError(GraphLintError):
    """Raised when a non-leaf node input has no producer edge."""


class DuplicateInputError(GraphLintError):
    """Raised when a non-leaf node input has multiple producer edges."""


class InvalidEdgeError(GraphLintError):
    """Raised when an edge does not match producer/consumer type contracts."""


def _summary_map(summaries: list[NodeSummary]) -> dict[str, NodeSummary]:
    result: dict[str, NodeSummary] = {}
    for summary in summaries:
        if summary.id in result:
            raise DuplicateNodeError(f"Duplicate node summary id: {summary.id}")
        result[summary.id] = summary
    return result


def has_cycle(graph: CalculationGraph) -> bool:
    """Return True when graph edges contain a cycle among graph.nodes."""

    node_set = set(graph.nodes)
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in graph.nodes}
    indegree: dict[str, int] = {node_id: 0 for node_id in graph.nodes}

    for edge in graph.edges:
        if edge.from_node not in node_set or edge.to_node not in node_set:
            continue
        adjacency[edge.from_node].append(edge.to_node)
        indegree[edge.to_node] += 1

    queue = deque(node_id for node_id in graph.nodes if indegree[node_id] == 0)
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for downstream in adjacency[node_id]:
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                queue.append(downstream)

    return visited != len(graph.nodes)


def lint_graph(graph: CalculationGraph, summaries: list[NodeSummary]) -> None:
    """Validate graph structure against registry summaries.

    The linter is intentionally pure: it raises clear exceptions and does not
    prompt, print, mutate registry files, or alter the graph.
    """

    if len(set(graph.nodes)) != len(graph.nodes):
        raise DuplicateNodeError("Graph contains duplicate node IDs")

    summary_by_id = _summary_map(summaries)
    graph_node_set = set(graph.nodes)

    if graph.terminal_node_id not in graph_node_set:
        raise UnknownNodeError(
            f"Terminal node {graph.terminal_node_id!r} is not present in graph.nodes"
        )

    missing_registry_nodes = sorted(node_id for node_id in graph.nodes if node_id not in summary_by_id)
    if missing_registry_nodes:
        raise UnknownNodeError(
            f"Graph references nodes missing from registry summaries: {missing_registry_nodes}"
        )

    for edge in graph.edges:
        if edge.from_node not in graph_node_set:
            raise UnknownNodeError(f"Edge references unknown producer: {edge.from_node}")
        if edge.to_node not in graph_node_set:
            raise UnknownNodeError(f"Edge references unknown consumer: {edge.to_node}")

    if has_cycle(graph):
        raise CyclicGraphError("Graph contains a cycle")

    for edge in graph.edges:
        producer = summary_by_id[edge.from_node]
        consumer = summary_by_id[edge.to_node]

        if edge.type != producer.output:
            raise InvalidEdgeError(
                f"Edge {edge.from_node}->{edge.to_node}.{edge.to_input} has type "
                f"{edge.type!r}, but producer output is {producer.output!r}"
            )

        valid_consumer_inputs = {
            (node_input.name, node_input.type) for node_input in consumer.inputs
        }
        if (edge.to_input, edge.type) not in valid_consumer_inputs:
            raise InvalidEdgeError(
                f"Edge targets {edge.to_node}.{edge.to_input} with type {edge.type!r}, "
                "but the consumer has no matching named input"
            )

    incoming: dict[tuple[str, str, str], int] = defaultdict(int)
    for edge in graph.edges:
        incoming[(edge.to_node, edge.to_input, edge.type)] += 1

    for node_id in graph.nodes:
        summary = summary_by_id[node_id]
        if summary.node_type in LEAF_NODE_TYPES:
            continue
        for node_input in summary.inputs:
            count = incoming[(node_id, node_input.name, node_input.type)]
            if count == 0:
                raise MissingInputError(
                    f"Node {node_id!r} input {node_input.name!r} of type "
                    f"{node_input.type!r} has no incoming edge"
                )
            if count > 1:
                raise DuplicateInputError(
                    f"Node {node_id!r} input {node_input.name!r} of type "
                    f"{node_input.type!r} has {count} incoming edges"
                )
