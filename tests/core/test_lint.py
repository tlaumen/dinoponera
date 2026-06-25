from __future__ import annotations

from pathlib import Path

import pytest

from dinoponera.core.lint import (
    CyclicGraphError,
    DuplicateInputError,
    InvalidEdgeError,
    MissingInputError,
    UnknownNodeError,
    has_cycle,
    lint_graph,
)
from dinoponera.core.models import CalculationGraph, Edge
from dinoponera.core.script_generation import generate_script_source
from registry import index as registry_index


def example_graph() -> CalculationGraph:
    return CalculationGraph.model_validate_json(Path("graphs/example_doubling.json").read_text())


def summaries():
    return registry_index.summaries()


def test_clean_graph_passes_lint() -> None:
    graph = example_graph()

    assert has_cycle(graph) is False
    assert lint_graph(graph, summaries()) is None


def test_missing_named_input_fails_clearly() -> None:
    graph = CalculationGraph(
        name="missing_input",
        terminal_node_id="format_result",
        nodes=["format_result"],
        edges=[],
    )

    with pytest.raises(MissingInputError, match="doubled"):
        lint_graph(graph, summaries())


def test_duplicate_incoming_edge_for_same_named_input_fails() -> None:
    graph = example_graph()
    duplicate = graph.model_copy(deep=True)
    duplicate.edges.append(
        Edge(
            from_node="double_value",
            to_node="format_result",
            to_input="doubled",
            type="calc_types.example.DoubledValue",
        )
    )

    with pytest.raises(DuplicateInputError, match="2 incoming edges"):
        lint_graph(duplicate, summaries())


def test_cycle_detection_fails_clearly() -> None:
    graph = example_graph()
    cyclic = graph.model_copy(deep=True)
    cyclic.edges.append(
        Edge(
            from_node="format_result",
            to_node="double_value",
            to_input="base",
            type="calc_types.example.CalculationResult",
        )
    )

    assert has_cycle(cyclic) is True
    with pytest.raises(CyclicGraphError):
        lint_graph(cyclic, summaries())


def test_unknown_node_ids_fail_clearly() -> None:
    graph = example_graph()
    unknown = graph.model_copy(deep=True)
    unknown.nodes.append("not_registered")

    with pytest.raises(UnknownNodeError, match="not_registered"):
        lint_graph(unknown, summaries())


def test_invalid_edge_type_or_consumer_input_fails() -> None:
    graph = example_graph()
    invalid = graph.model_copy(deep=True)
    invalid.edges[1] = Edge(
        from_node="double_value",
        to_node="format_result",
        to_input="doubled",
        type="calc_types.example.BaseValue",
    )

    with pytest.raises(InvalidEdgeError, match="producer output"):
        lint_graph(invalid, summaries())


def test_script_generation_runs_lint_before_rendering() -> None:
    graph = example_graph()
    invalid = graph.model_copy(deep=True)
    invalid.edges = invalid.edges[:-1]

    with pytest.raises(MissingInputError):
        generate_script_source(invalid)
