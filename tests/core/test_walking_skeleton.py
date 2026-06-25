from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from dinoponera.core.models import CalculationGraph
from dinoponera.core.naming import normalise_name, to_snake_case
from dinoponera.core.script_generation import (
    generate_script_source,
    topological_sort,
    write_run_script,
)
from registry import index as registry_index


def load_example_graph() -> CalculationGraph:
    return CalculationGraph.model_validate_json(Path("graphs/example_doubling.json").read_text())


def test_models_round_trip_and_named_edges() -> None:
    graph = load_example_graph()
    dumped = graph.model_dump_json()
    round_tripped = CalculationGraph.model_validate_json(dumped)

    assert round_tripped.name == "example_doubling"
    assert round_tripped.has_edge(
        to="double_value",
        to_input="base",
        type="calc_types.example.BaseValue",
    )
    assert not round_tripped.has_edge(
        to="double_value",
        to_input="other",
        type="calc_types.example.BaseValue",
    )


def test_naming_helpers() -> None:
    assert normalise_name("Settlement Analysis") == "settlement_analysis"
    assert normalise_name("Settlement (SLS)! Analysis") == "settlement_sls_analysis"
    assert to_snake_case("CalculationResult") == "calculation_result"


def test_registry_introspection_summarizes_example_nodes() -> None:
    summaries = {summary.id: summary for summary in registry_index.summaries()}

    assert summaries["example_source_value"].node_type == "data_retrieval"
    assert summaries["example_source_value"].output == "calc_types.example.BaseValue"
    assert summaries["double_value"].inputs[0].name == "base"
    assert summaries["double_value"].inputs[0].type == "calc_types.example.BaseValue"
    assert summaries["format_result"].output == "calc_types.example.CalculationResult"


def test_generate_script_from_manual_graph_and_execute(tmp_path: Path) -> None:
    graph = load_example_graph()

    assert topological_sort(graph) == [
        "example_source_value",
        "double_value",
        "format_result",
    ]

    source = generate_script_source(graph)
    assert "from calc_types.example import BaseValue, CalculationResult, DoubledValue" in source
    assert "from registry.nodes.example_source_value import example_source_value" in source
    assert "def run() -> CalculationResult:" in source
    assert "doubled_value = double_value(base=base_value)" in source
    assert "calculation_result = format_result(doubled=doubled_value)" in source
    assert "baml" not in source.lower()

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

    assert "Doubled value" in completed.stdout
    assert "42.0" in completed.stdout
