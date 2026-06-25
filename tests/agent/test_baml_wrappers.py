from __future__ import annotations

from types import SimpleNamespace

from baml_client import types as baml_types

from dinoponera.agent import planning
from dinoponera.core.models import CalculationGraph, Edge, QA, StateSummary, UnresolvedInput
from registry import index as registry_index


def test_baml_identify_goal_wrapper_converts_python_models(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeBamlClient:
        def IdentifyGoal(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(kind="GoalClear")

    monkeypatch.setattr(planning, "b", FakeBamlClient())

    summary = registry_index.get_summary("format_result")
    qa = QA(question="Which result?", answer="Example result")
    result = planning.baml_identify_goal("problem", [summary], [qa])

    assert result.kind == "GoalClear"
    assert seen["problem"] == "problem"
    assert isinstance(seen["registry"][0], baml_types.BamlNodeSummary)
    assert isinstance(seen["clarifications"][0], baml_types.BamlQA)
    assert seen["registry"][0].id == "format_result"
    assert seen["clarifications"][0].answer == "Example result"


def test_baml_extend_graph_wrapper_converts_python_models(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeBamlClient:
        def ExtendGraph(self, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(kind="AddFromRegistry")

    monkeypatch.setattr(planning, "b", FakeBamlClient())

    unresolved = UnresolvedInput(
        node_id="format_result",
        input_name="doubled",
        input_type="calc_types.example.DoubledValue",
    )
    state_summary = StateSummary(goal="Example")
    graph = CalculationGraph(
        name="example",
        terminal_node_id="format_result",
        nodes=["format_result", "double_value"],
        edges=[
            Edge(
                from_node="double_value",
                to_node="format_result",
                to_input="doubled",
                type="calc_types.example.DoubledValue",
            )
        ],
    )
    summary = registry_index.get_summary("double_value")

    result = planning.baml_extend_graph(unresolved, state_summary, graph, [summary], [])

    assert result.kind == "AddFromRegistry"
    assert isinstance(seen["current_unresolved"], baml_types.BamlUnresolvedInput)
    assert isinstance(seen["state_summary"], baml_types.BamlStateSummary)
    assert isinstance(seen["graph"], baml_types.BamlCalculationGraph)
    assert isinstance(seen["registry"][0], baml_types.BamlNodeSummary)
    assert seen["current_unresolved"].input_name == "doubled"
    assert seen["graph"].edges[0].to_input == "doubled"
