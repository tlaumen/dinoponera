"""Deterministic graph-building primitives used before BAML planning exists."""

from __future__ import annotations

import argparse
from pathlib import Path

from dinoponera.core.lint import lint_graph
from dinoponera.core.models import CalculationGraph, Edge, NodeSummary, UnresolvedInput
from dinoponera.core.naming import normalise_name
from dinoponera.core.traversal import BreadthFirstTraversal
from registry import index as registry_index


class GraphBuildError(ValueError):
    """Raised when deterministic graph construction cannot choose safely."""


def candidate_summaries_for_unresolved(
    unresolved: UnresolvedInput,
    summaries: list[NodeSummary],
) -> list[NodeSummary]:
    """Return registry summaries whose output exactly matches the required type."""

    return [summary for summary in summaries if summary.output == unresolved.input_type]


def build_graph_by_unique_matches(
    *,
    name: str,
    terminal_node_id: str,
    summaries: list[NodeSummary] | None = None,
) -> CalculationGraph:
    """Build a graph by repeatedly selecting the only type-compatible producer.

    This is intentionally conservative. It is a pre-BAML walking-skeleton tool:
    if there are zero or multiple possible producers for an unresolved input, it
    raises instead of guessing.
    """

    summaries = summaries if summaries is not None else registry_index.summaries()
    summary_by_id = {summary.id: summary for summary in summaries}
    if terminal_node_id not in summary_by_id:
        raise GraphBuildError(f"Unknown terminal node: {terminal_node_id}")

    graph = CalculationGraph(
        name=normalise_name(name),
        terminal_node_id=terminal_node_id,
        nodes=[terminal_node_id],
        edges=[],
    )
    traversal = BreadthFirstTraversal()

    while unresolved := traversal.next_unresolved(graph, summaries):
        existing_candidates = [
            summary
            for summary in candidate_summaries_for_unresolved(unresolved, summaries)
            if summary.id in graph.nodes and summary.id != unresolved.node_id
        ]
        new_candidates = [
            summary
            for summary in candidate_summaries_for_unresolved(unresolved, summaries)
            if summary.id not in graph.nodes
        ]

        if len(existing_candidates) == 1:
            producer_id = existing_candidates[0].id
        elif not existing_candidates and len(new_candidates) == 1:
            producer_id = new_candidates[0].id
            graph.nodes.append(producer_id)
        else:
            candidate_ids = [summary.id for summary in existing_candidates + new_candidates]
            raise GraphBuildError(
                f"Cannot deterministically satisfy {unresolved.node_id}.{unresolved.input_name} "
                f"of type {unresolved.input_type}; candidates={candidate_ids}"
            )

        graph.edges.append(
            Edge(
                from_node=producer_id,
                to_node=unresolved.node_id,
                to_input=unresolved.input_name,
                type=unresolved.input_type,
            )
        )

    lint_graph(graph, summaries)
    return graph


def write_graph(graph: CalculationGraph, path: str | Path) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(graph.model_dump_json(indent=2) + "\n")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a calculation graph using deterministic unique type matches."
    )
    parser.add_argument("terminal_node_id")
    parser.add_argument("--name", help="Calculation graph name; defaults to terminal node id")
    parser.add_argument("--output", help="Output graph JSON path; defaults to graphs/{name}.json")
    args = parser.parse_args(argv)

    graph_name = normalise_name(args.name or args.terminal_node_id)
    graph = build_graph_by_unique_matches(name=graph_name, terminal_node_id=args.terminal_node_id)
    output = args.output or f"graphs/{graph.name}.json"
    path = write_graph(graph, output)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
