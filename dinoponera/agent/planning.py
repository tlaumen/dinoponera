"""BAML-boundary planning orchestration for the MVP flow.

Direct BAML client usage is intentionally localized here. Tests monkeypatch
``baml_identify_goal`` and ``baml_extend_graph`` with deterministic fakes;
live usage calls the generated ``baml_client`` wrappers below.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

try:  # pragma: no cover - live BAML calls require provider credentials.
    from baml_client import types as baml_types
    from baml_client.sync_client import b

    def _to_baml(value: Any, target_type: Any) -> Any:
        if isinstance(value, target_type):
            return value
        if hasattr(value, "model_dump"):
            return target_type.model_validate(value.model_dump())
        if isinstance(value, dict):
            return target_type.model_validate(value)
        return value

    def baml_identify_goal(problem: str, registry: list[NodeSummary], clarifications: list[QA]) -> Any:
        return b.IdentifyGoal(
            problem=problem,
            registry=[_to_baml(item, baml_types.BamlNodeSummary) for item in registry],
            clarifications=[_to_baml(item, baml_types.BamlQA) for item in clarifications],
        )

    def baml_extend_graph(
        current_unresolved: UnresolvedInput,
        state_summary: StateSummary,
        graph: CalculationGraph,
        registry: list[NodeSummary],
        clarifications: list[QA],
    ) -> Any:
        return b.ExtendGraph(
            current_unresolved=_to_baml(current_unresolved, baml_types.BamlUnresolvedInput),
            state_summary=_to_baml(state_summary, baml_types.BamlStateSummary),
            graph=_to_baml(graph, baml_types.BamlCalculationGraph),
            registry=[_to_baml(item, baml_types.BamlNodeSummary) for item in registry],
            clarifications=[_to_baml(item, baml_types.BamlQA) for item in clarifications],
        )
except Exception:  # pragma: no cover - deterministic tests monkeypatch these.

    def baml_identify_goal(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("BAML client is not generated; monkeypatch baml_identify_goal in tests")

    def baml_extend_graph(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("BAML client is not generated; monkeypatch baml_extend_graph in tests")

from dinoponera.agent.io import ConsoleInteractor, UserInteractor
from dinoponera.core.graph_building import candidate_summaries_for_unresolved, write_graph
from dinoponera.core.leaf_stub_generation import create_leaf_stub
from dinoponera.core.lint import lint_graph
from dinoponera.core.models import (
    CalculationGraph,
    Edge,
    NodeSummary,
    QA,
    StateSummary,
    UnresolvedInput,
)
from dinoponera.core.naming import normalise_name
from dinoponera.core.render import render_graph
from dinoponera.core.script_generation import write_run_script
from dinoponera.core.traversal import BreadthFirstTraversal
from registry import index as registry_index


class MissingNodeError(ValueError):
    """Raised when an engineer must add a missing computation node manually."""


class PlanningRejectedError(ValueError):
    """Raised when the user rejects graph approval."""


class PlanningClarificationError(ValueError):
    """Raised when planner clarification cannot be consumed in the current path."""


def _variant_name(value: Any) -> str:
    raw = _get(value, "kind", "type", "variant", "tag", default=None)
    if raw is None:
        raw = value.__class__.__name__
    raw = getattr(raw, "value", raw)
    return str(raw).replace("_", "").replace("-", "").lower()


def _get(value: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _as_state_summary(value: Any, *, fallback_goal: str = "") -> StateSummary:
    if isinstance(value, StateSummary):
        return value
    if isinstance(value, dict):
        return StateSummary.model_validate(value)
    if value is None:
        return StateSummary(goal=fallback_goal)
    return StateSummary(
        goal=_get(value, "goal", default=fallback_goal),
        decisions=list(_get(value, "decisions", default=[]) or []),
        open_items=list(_get(value, "open_items", "openItems", default=[]) or []),
        phase1_clarification_summary=_get(
            value,
            "phase1_clarification_summary",
            "phase1ClarificationSummary",
            default="",
        )
        or "",
    )


def _as_node_summary(value: Any) -> NodeSummary:
    if isinstance(value, NodeSummary):
        return value
    if isinstance(value, dict):
        return NodeSummary.model_validate(value)
    if hasattr(value, "model_dump"):
        return NodeSummary.model_validate(value.model_dump())
    raise TypeError(f"Cannot convert {value!r} to NodeSummary")


def _validate_producer(
    *,
    producer_id: str,
    unresolved: UnresolvedInput,
    summaries: list[NodeSummary],
    require_existing_in_graph: CalculationGraph | None = None,
) -> None:
    summary_by_id = {summary.id: summary for summary in summaries}
    producer = summary_by_id.get(producer_id)
    if producer is None:
        raise PlanningClarificationError(
            f"BAML selected unknown producer node {producer_id!r} for "
            f"{unresolved.node_id}.{unresolved.input_name}"
        )
    if producer.output != unresolved.input_type:
        raise PlanningClarificationError(
            f"BAML selected producer {producer_id!r} with output {producer.output!r}, "
            f"but {unresolved.node_id}.{unresolved.input_name} requires {unresolved.input_type!r}"
        )
    if producer_id == unresolved.node_id:
        raise PlanningClarificationError(
            f"BAML selected node {producer_id!r} to satisfy its own input "
            f"{unresolved.input_name!r}"
        )
    if require_existing_in_graph is not None and producer_id not in require_existing_in_graph.nodes:
        raise PlanningClarificationError(
            f"ConnectExisting selected {producer_id!r}, but it is not already in graph.nodes"
        )


def _validate_optional_alias_id(result: Any, primary: str, *aliases: str) -> None:
    for alias in aliases:
        value = _get(result, alias, default=None)
        if value is not None and value != primary:
            raise PlanningClarificationError(
                f"BAML returned inconsistent producer ids: {primary!r} and {value!r}"
            )


def _append_edge(graph: CalculationGraph, producer_id: str, unresolved: UnresolvedInput) -> None:
    for edge in graph.edges:
        if (
            edge.to_node == unresolved.node_id
            and edge.to_input == unresolved.input_name
            and edge.type == unresolved.input_type
        ):
            if edge.from_node == producer_id:
                return
            raise PlanningClarificationError(
                f"Input {unresolved.node_id}.{unresolved.input_name} already has producer "
                f"{edge.from_node!r}; refusing to add {producer_id!r}"
            )

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


def _updated_state(result: Any, current: StateSummary) -> StateSummary:
    value = _get(result, "updated_state_summary", "updatedStateSummary", default=None)
    if value is None:
        return current
    return _as_state_summary(value, fallback_goal=current.goal)


def identify_goal_loop(
    problem: str,
    interactor: UserInteractor,
    *,
    summaries_fn: Callable[[], list[NodeSummary]] = registry_index.summaries,
) -> Any:
    """Run Phase 1 goal identification until explicit user confirmation."""

    clarifications: list[QA] = []
    while True:
        registry_summaries = summaries_fn()
        result = baml_identify_goal(problem, registry_summaries, clarifications)
        variant = _variant_name(result)

        if variant == "needsclarification":
            question = _get(result, "question", default="")
            context = _get(result, "context", default=None)
            answer = interactor.ask_clarification(question, context)
            clarifications.append(QA(question=question, answer=answer))
            continue

        if variant == "goalclear":
            terminal_node_id = _get(result, "terminal_node_id", "terminalNodeId", default=None)
            calculation_type = _get(result, "calculation_type", "calculationType", default=problem)
            if terminal_node_id is None:
                missing_description = _get(result, "missing_description", "missingDescription", default="")
                raise MissingNodeError(
                    f"No terminal node found for {calculation_type!r}. "
                    f"Add the missing computation node manually and restart. {missing_description}"
                )
            if interactor.confirm_goal(calculation_type, terminal_node_id):
                return result
            question = (
                "What should change about the calculation goal or terminal result?"
            )
            answer = interactor.ask_clarification(
                question,
                "The proposed goal was rejected; provide the correction before replanning.",
            )
            clarifications.append(QA(question=question, answer=answer))
            continue

        raise PlanningClarificationError(f"Unknown baml_identify_goal result variant: {variant}")


def _resolve_source_gap(
    *,
    graph: CalculationGraph,
    unresolved: UnresolvedInput,
    state_summary: StateSummary,
    interactor: UserInteractor,
    create_leaf_stub_fn: Callable[[str, str], str],
) -> str:
    response = interactor.resolve_source_gap(unresolved, state_summary)
    if response.kind == "missing_computation":
        detail = f": {response.detail}" if response.detail else ""
        raise MissingNodeError(
            f"Missing computation node for {unresolved.node_id}.{unresolved.input_name} "
            f"({unresolved.input_type}){detail}. Add it manually and restart."
        )
    node_id = create_leaf_stub_fn(response.kind, unresolved.input_type)
    _append_edge(graph, node_id, unresolved)
    return node_id


def build_graph_loop(
    goal: Any,
    interactor: UserInteractor,
    *,
    graph_dir: str | Path = "graphs",
    summaries_fn: Callable[[], list[NodeSummary]] = registry_index.summaries,
    create_leaf_stub_fn: Callable[[str, str], str] = create_leaf_stub,
) -> CalculationGraph:
    """Run Phase 2 graph building, lint, review, approval, and serialization."""

    calculation_type = _get(goal, "calculation_type", "calculationType", default="calculation")
    terminal_node_id = _get(goal, "terminal_node_id", "terminalNodeId", default=None)
    if terminal_node_id is None:
        raise MissingNodeError("Goal has no terminal node id")

    graph = CalculationGraph(
        name=normalise_name(calculation_type),
        terminal_node_id=terminal_node_id,
        nodes=[terminal_node_id],
        edges=[],
    )
    state_summary = _as_state_summary(
        _get(goal, "state_summary", "stateSummary", default=None),
        fallback_goal=calculation_type,
    )
    clarifications: list[QA] = []
    traversal = BreadthFirstTraversal()
    summaries = summaries_fn()

    while unresolved := traversal.next_unresolved(graph, summaries):
        filtered = candidate_summaries_for_unresolved(unresolved, summaries)
        result = baml_extend_graph(unresolved, state_summary, graph, filtered, clarifications)
        variant = _variant_name(result)

        if variant == "connectexisting":
            producer_id = _get(result, "from_node_id", "fromNodeId", "from_node", default=None)
            if producer_id is None:
                raise PlanningClarificationError("ConnectExisting result missing from_node_id")
            _validate_optional_alias_id(result, producer_id, "node_id", "nodeId")
            _validate_producer(
                producer_id=producer_id,
                unresolved=unresolved,
                summaries=summaries,
                require_existing_in_graph=graph,
            )
            _append_edge(graph, producer_id, unresolved)
            state_summary = _updated_state(result, state_summary)
            continue

        if variant == "addfromregistry":
            node_id = _get(result, "node_id", "nodeId", default=None)
            if node_id is None:
                raise PlanningClarificationError("AddFromRegistry result missing node_id")
            _validate_optional_alias_id(result, node_id, "from_node_id", "fromNodeId", "from_node")
            _validate_producer(producer_id=node_id, unresolved=unresolved, summaries=summaries)
            _append_edge(graph, node_id, unresolved)
            state_summary = _updated_state(result, state_summary)
            continue

        if variant == "applicabilitycheck":
            question = _get(result, "question", default="Choose an applicable node")
            raw_candidates = _get(result, "candidates", default=filtered) or []
            candidates = [_as_node_summary(candidate) for candidate in raw_candidates]
            response = interactor.resolve_applicability(question, candidates)
            if response.kind == "chosen":
                if response.node_id is None:
                    raise PlanningClarificationError("Applicability chosen response missing node_id")
                candidate_ids = {candidate.id for candidate in candidates}
                if response.node_id not in candidate_ids:
                    raise PlanningClarificationError(
                        f"Applicability selected {response.node_id!r}, which is not one of "
                        f"the offered candidates {sorted(candidate_ids)}"
                    )
                _validate_producer(producer_id=response.node_id, unresolved=unresolved, summaries=summaries)
                _append_edge(graph, response.node_id, unresolved)
                continue
            if response.kind == "rejected_all":
                raise MissingNodeError(
                    f"No acceptable producer for {unresolved.node_id}.{unresolved.input_name} "
                    f"({unresolved.input_type}); add a computation node manually and restart."
                )
            clarifications.append(QA(question=question, answer=response.detail or ""))
            continue

        if variant == "nocandidate":
            _resolve_source_gap(
                graph=graph,
                unresolved=unresolved,
                state_summary=state_summary,
                interactor=interactor,
                create_leaf_stub_fn=create_leaf_stub_fn,
            )
            summaries = summaries_fn()
            state_summary = _updated_state(result, state_summary)
            continue

        raise PlanningClarificationError(f"Unknown baml_extend_graph result variant: {variant}")

    lint_graph(graph, summaries)
    rendered = render_graph(graph, summaries)
    if not interactor.approve_graph(graph, rendered):
        raise PlanningRejectedError("Graph rejected by user")

    write_graph(graph, Path(graph_dir) / f"{graph.name}.json")
    return graph


def plan_calculation(
    problem: str,
    interactor: UserInteractor,
    *,
    graph_dir: str | Path = "graphs",
    summaries_fn: Callable[[], list[NodeSummary]] = registry_index.summaries,
    create_leaf_stub_fn: Callable[[str, str], str] = create_leaf_stub,
) -> CalculationGraph:
    """Run Phase 1 + Phase 2 and return the approved serialized graph."""

    goal = identify_goal_loop(problem, interactor, summaries_fn=summaries_fn)
    return build_graph_loop(
        goal,
        interactor,
        graph_dir=graph_dir,
        summaries_fn=summaries_fn,
        create_leaf_stub_fn=create_leaf_stub_fn,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan a calculation graph with BAML and optional script generation."
    )
    parser.add_argument("problem", help="Natural-language calculation problem")
    parser.add_argument("--graph-dir", default="graphs", help="Directory for approved graph JSON")
    parser.add_argument(
        "--generate-script",
        action="store_true",
        help="Also generate runs/run_{graph.name}.py after graph approval",
    )
    parser.add_argument("--runs-dir", default="runs", help="Directory for generated run scripts")
    args = parser.parse_args(argv)

    graph = plan_calculation(
        args.problem,
        ConsoleInteractor(),
        graph_dir=args.graph_dir,
    )
    graph_path = Path(args.graph_dir) / f"{graph.name}.json"
    print(f"Graph: {graph_path}")

    if args.generate_script:
        script_path = write_run_script(graph, runs_dir=args.runs_dir)
        print(f"Run script: {script_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
