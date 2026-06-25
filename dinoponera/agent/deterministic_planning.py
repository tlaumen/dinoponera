"""Console-guided deterministic planning before BAML integration.

This module keeps the walking skeleton moving while the BAML planner is still
absent: start from a terminal node id, automatically connect unique compatible
producers, ask the user when a choice is ambiguous, resolve source gaps as leaf
stubs, lint, render, approve, and serialize the graph.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from dinoponera.agent.io import ConsoleInteractor, UserInteractor
from dinoponera.core.graph_building import candidate_summaries_for_unresolved, write_graph
from dinoponera.core.leaf_stub_generation import create_leaf_stub
from dinoponera.core.lint import lint_graph
from dinoponera.core.models import CalculationGraph, Edge, NodeSummary, StateSummary
from dinoponera.core.naming import normalise_name
from dinoponera.core.render import render_graph
from dinoponera.core.traversal import BreadthFirstTraversal
from registry import index as registry_index


class MissingNodeError(ValueError):
    """Raised when the user classifies a gap as requiring a missing computation."""


class PlanningRejectedError(ValueError):
    """Raised when the user rejects goal or graph approval in this pre-BAML planner."""


class PlanningClarificationError(ValueError):
    """Raised when clarification is needed but no BAML loop exists to consume it."""


@dataclass(frozen=True)
class PlanningResult:
    graph: CalculationGraph
    path: Path
    rendered: str


def _append_edge_for_producer(graph: CalculationGraph, producer_id: str, unresolved) -> None:
    if producer_id not in graph.nodes:
        graph.nodes.append(producer_id)
    graph.edges.append(
        Edge(
            from_node=producer_id,
            to_node=unresolved.node_id,
            to_input=unresolved.input_name,
            type=unresolved.input_type,
        )
    )


def _choose_or_create_producer(
    *,
    graph: CalculationGraph,
    unresolved,
    summaries: list[NodeSummary],
    interactor: UserInteractor,
    state_summary: StateSummary,
    create_leaf_stub_fn: Callable[[str, str], str],
) -> bool:
    """Satisfy one unresolved input.

    Returns True when registry summaries should be refreshed because a leaf stub
    was created.
    """

    candidates = [
        summary
        for summary in candidate_summaries_for_unresolved(unresolved, summaries)
        if summary.id != unresolved.node_id
    ]
    existing_candidates = [summary for summary in candidates if summary.id in graph.nodes]
    new_candidates = [summary for summary in candidates if summary.id not in graph.nodes]

    if len(existing_candidates) == 1:
        _append_edge_for_producer(graph, existing_candidates[0].id, unresolved)
        return False
    if not existing_candidates and len(new_candidates) == 1:
        _append_edge_for_producer(graph, new_candidates[0].id, unresolved)
        return False

    if candidates:
        response = interactor.resolve_applicability(
            question=(
                f"Choose a producer for {unresolved.node_id}.{unresolved.input_name} "
                f"({unresolved.input_type})."
            ),
            candidates=candidates,
        )
        if response.kind == "chosen":
            candidate_ids = {candidate.id for candidate in candidates}
            if response.node_id not in candidate_ids:
                raise MissingNodeError(
                    f"Chosen node {response.node_id!r} is not a valid candidate for "
                    f"{unresolved.node_id}.{unresolved.input_name}"
                )
            _append_edge_for_producer(graph, response.node_id, unresolved)
            return False
        if response.kind == "rejected_all":
            raise MissingNodeError(
                f"No acceptable producer for {unresolved.node_id}.{unresolved.input_name} "
                f"({unresolved.input_type}); add a computation node manually and restart."
            )
        raise PlanningClarificationError(
            response.detail or "Applicability clarification requested."
        )

    source_response = interactor.resolve_source_gap(unresolved, state_summary)
    if source_response.kind == "missing_computation":
        detail = f": {source_response.detail}" if source_response.detail else ""
        raise MissingNodeError(
            f"Missing computation node for {unresolved.node_id}.{unresolved.input_name}"
            f" ({unresolved.input_type}){detail}. Add it manually and restart."
        )

    leaf_node_id = create_leaf_stub_fn(source_response.kind, unresolved.input_type)
    _append_edge_for_producer(graph, leaf_node_id, unresolved)
    return True


def plan_from_terminal_node(
    *,
    calculation_type: str,
    terminal_node_id: str,
    interactor: UserInteractor,
    graph_dir: str | Path = "graphs",
    summaries_fn: Callable[[], list[NodeSummary]] = registry_index.summaries,
    create_leaf_stub_fn: Callable[[str, str], str] = create_leaf_stub,
) -> PlanningResult:
    """Plan, approve, and serialize a graph starting from a terminal node id."""

    if not interactor.confirm_goal(calculation_type, terminal_node_id):
        raise PlanningRejectedError("Goal rejected by user")

    summaries = summaries_fn()
    if terminal_node_id not in {summary.id for summary in summaries}:
        raise MissingNodeError(
            f"Terminal node {terminal_node_id!r} is not in the registry; add it manually and restart."
        )

    graph = CalculationGraph(
        name=normalise_name(calculation_type),
        terminal_node_id=terminal_node_id,
        nodes=[terminal_node_id],
        edges=[],
    )
    state_summary = StateSummary(goal=calculation_type)
    traversal = BreadthFirstTraversal()

    while unresolved := traversal.next_unresolved(graph, summaries):
        should_refresh = _choose_or_create_producer(
            graph=graph,
            unresolved=unresolved,
            summaries=summaries,
            interactor=interactor,
            state_summary=state_summary,
            create_leaf_stub_fn=create_leaf_stub_fn,
        )
        if should_refresh:
            summaries = summaries_fn()

    lint_graph(graph, summaries)
    rendered = render_graph(graph, summaries)
    if not interactor.approve_graph(graph, rendered):
        raise PlanningRejectedError("Graph rejected by user")

    path = write_graph(graph, Path(graph_dir) / f"{graph.name}.json")
    return PlanningResult(graph=graph, path=path, rendered=rendered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan a graph from a terminal node using deterministic/user-guided choices."
    )
    parser.add_argument("terminal_node_id")
    parser.add_argument("--name", help="Calculation type/name; defaults to terminal node id")
    parser.add_argument("--graph-dir", default="graphs")
    args = parser.parse_args(argv)

    result = plan_from_terminal_node(
        calculation_type=args.name or args.terminal_node_id,
        terminal_node_id=args.terminal_node_id,
        interactor=ConsoleInteractor(),
        graph_dir=args.graph_dir,
    )
    print(result.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
