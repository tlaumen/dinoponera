from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from dinoponera.core.graph_building import (
    GraphBuildError,
    build_graph_by_unique_matches,
    candidate_summaries_for_unresolved,
    write_graph,
)
from dinoponera.core.models import CalculationGraph, Edge, NodeInput, NodeSummary
from dinoponera.core.render import render_graph
from dinoponera.core.script_generation import write_run_script
from dinoponera.core.traversal import BreadthFirstTraversal
from registry import index as registry_index


def example_graph() -> CalculationGraph:
    return CalculationGraph.model_validate_json(
        Path("tests/fixtures/graphs/example_doubling.json").read_text()
    )


def summaries() -> list[NodeSummary]:
    return registry_index.summaries()


def test_traversal_returns_first_unresolved_named_input() -> None:
    graph = CalculationGraph(
        name="partial",
        terminal_node_id="format_result",
        nodes=["format_result"],
        edges=[],
    )

    unresolved = BreadthFirstTraversal().next_unresolved(graph, summaries())

    assert unresolved is not None
    assert unresolved.node_id == "format_result"
    assert unresolved.input_name == "doubled"
    assert unresolved.input_type == "calc_types.example.DoubledValue"


def test_traversal_skips_resolved_inputs_and_leaf_nodes() -> None:
    graph = CalculationGraph(
        name="partial",
        terminal_node_id="format_result",
        nodes=["format_result", "double_value", "example_source_value"],
        edges=[
            Edge(
                from_node="double_value",
                to_node="format_result",
                to_input="doubled",
                type="calc_types.example.DoubledValue",
            ),
            Edge(
                from_node="example_source_value",
                to_node="double_value",
                to_input="base",
                type="calc_types.example.BaseValue",
            ),
        ],
    )

    assert BreadthFirstTraversal().next_unresolved(graph, summaries()) is None


def test_candidate_filtering_uses_required_output_type() -> None:
    graph = CalculationGraph(
        name="partial",
        terminal_node_id="format_result",
        nodes=["format_result"],
        edges=[],
    )
    unresolved = BreadthFirstTraversal().next_unresolved(graph, summaries())
    assert unresolved is not None

    candidates = candidate_summaries_for_unresolved(unresolved, summaries())

    assert [candidate.id for candidate in candidates] == ["double_value"]


def test_render_graph_includes_nodes_outputs_and_connections() -> None:
    rendered = render_graph(example_graph(), summaries())

    assert "Calculation graph: example_doubling" in rendered
    assert "A: format_result [computation]" in rendered
    assert "      output: CalculationResult" in rendered
    assert "C: example_source_value [data_retrieval]" in rendered
    assert "      output: BaseValue" in rendered
    assert "B -> A (doubled)" in rendered
    assert "C -> B (base)" in rendered


def test_unique_match_graph_building_closes_loop_from_terminal_node(tmp_path: Path) -> None:
    graph = build_graph_by_unique_matches(
        name="auto example doubling",
        terminal_node_id="format_result",
    )

    assert graph.name == "auto_example_doubling"
    assert graph.nodes == ["format_result", "double_value", "example_source_value"]
    assert [(edge.from_node, edge.to_node, edge.to_input) for edge in graph.edges] == [
        ("double_value", "format_result", "doubled"),
        ("example_source_value", "double_value", "base"),
    ]

    graph_path = write_graph(graph, tmp_path / "auto_example_doubling.json")
    assert CalculationGraph.model_validate_json(graph_path.read_text()) == graph

    script_path = write_run_script(graph, runs_dir=tmp_path)
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{Path.cwd()}{os.pathsep}{env.get('PYTHONPATH', '')}"
    completed = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=Path.cwd(),
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "42.0" in completed.stdout


def test_unique_match_graph_building_refuses_ambiguous_candidates() -> None:
    summaries_with_ambiguity = summaries() + [
        NodeSummary(
            id="alternate_double_value",
            node_type="computation",
            description="Ambiguous alternate producer.",
            when_to_use="Test ambiguity.",
            assumptions=[],
            inputs=[NodeInput(name="base", type="calc_types.example.BaseValue")],
            output="calc_types.example.DoubledValue",
            references=[],
        )
    ]

    with pytest.raises(GraphBuildError, match="Cannot deterministically satisfy"):
        build_graph_by_unique_matches(
            name="ambiguous",
            terminal_node_id="format_result",
            summaries=summaries_with_ambiguity,
        )
