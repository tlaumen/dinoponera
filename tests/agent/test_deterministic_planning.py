from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from dinoponera.agent.deterministic_planning import (
    MissingNodeError,
    PlanningRejectedError,
    plan_from_terminal_node,
)
from dinoponera.core.models import (
    ApplicabilityResponse,
    CalculationGraph,
    NodeInput,
    NodeSummary,
    SourceGapResponse,
    StateSummary,
    UnresolvedInput,
)
from dinoponera.core.script_generation import write_run_script
from registry import index as registry_index


class FakeInteractor:
    def __init__(
        self,
        *,
        confirm: bool = True,
        approve: bool = True,
        applicability: ApplicabilityResponse | None = None,
        source_gap: SourceGapResponse | None = None,
    ) -> None:
        self.confirm = confirm
        self.approve = approve
        self.applicability = applicability
        self.source_gap = source_gap
        self.rendered: str | None = None

    def ask_clarification(self, question: str, context: str | None = None) -> str:
        return "clarification"

    def confirm_goal(self, calculation_type: str, terminal_node_id: str) -> bool:
        return self.confirm

    def resolve_applicability(
        self,
        question: str,
        candidates: list[NodeSummary],
    ) -> ApplicabilityResponse:
        assert self.applicability is not None
        return self.applicability

    def resolve_source_gap(
        self,
        gap: UnresolvedInput,
        state_summary: StateSummary,
    ) -> SourceGapResponse:
        assert self.source_gap is not None
        return self.source_gap

    def approve_graph(self, graph: CalculationGraph, rendered: str) -> bool:
        self.rendered = rendered
        return self.approve


def test_user_guided_planning_closes_loop_from_terminal_node(tmp_path: Path) -> None:
    interactor = FakeInteractor()

    result = plan_from_terminal_node(
        calculation_type="console example doubling",
        terminal_node_id="format_result",
        interactor=interactor,
        graph_dir=tmp_path,
    )

    assert result.path == tmp_path / "console_example_doubling.json"
    assert result.graph.nodes == ["format_result", "double_value", "example_source_value"]
    assert interactor.rendered is not None
    assert "Calculation graph: console_example_doubling" in interactor.rendered

    script_path = write_run_script(result.graph, runs_dir=tmp_path)
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


def test_goal_rejection_stops_before_writing_graph(tmp_path: Path) -> None:
    with pytest.raises(PlanningRejectedError, match="Goal rejected"):
        plan_from_terminal_node(
            calculation_type="rejected",
            terminal_node_id="format_result",
            interactor=FakeInteractor(confirm=False),
            graph_dir=tmp_path,
        )

    assert list(tmp_path.iterdir()) == []


def test_graph_rejection_stops_before_writing_graph(tmp_path: Path) -> None:
    with pytest.raises(PlanningRejectedError, match="Graph rejected"):
        plan_from_terminal_node(
            calculation_type="rejected graph",
            terminal_node_id="format_result",
            interactor=FakeInteractor(approve=False),
            graph_dir=tmp_path,
        )

    assert list(tmp_path.iterdir()) == []


def test_ambiguous_candidate_is_resolved_by_interactor(tmp_path: Path) -> None:
    ambiguous = registry_index.summaries() + [
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

    result = plan_from_terminal_node(
        calculation_type="ambiguous but chosen",
        terminal_node_id="format_result",
        interactor=FakeInteractor(
            applicability=ApplicabilityResponse(kind="chosen", node_id="double_value")
        ),
        graph_dir=tmp_path,
        summaries_fn=lambda: ambiguous,
    )

    assert any(edge.from_node == "double_value" for edge in result.graph.edges)


def test_source_gap_can_create_leaf_stub_with_injected_generator(tmp_path: Path) -> None:
    terminal_summary = NodeSummary(
        id="needs_runtime_result",
        node_type="computation",
        description="Needs a result supplied externally.",
        when_to_use="Test source gap.",
        assumptions=[],
        inputs=[NodeInput(name="result", type="calc_types.example.CalculationResult")],
        output="calc_types.example.DoubledValue",
        references=[],
    )
    summaries: list[NodeSummary] = [terminal_summary]

    def fake_create_leaf_stub(node_type: str, output_type_path: str) -> str:
        assert node_type == "user_input"
        assert output_type_path == "calc_types.example.CalculationResult"
        summaries.append(
            NodeSummary(
                id="prompt_calculation_result",
                node_type="user_input",
                description="Fake prompt source.",
                when_to_use="Test.",
                assumptions=[],
                inputs=[],
                output=output_type_path,
                references=[],
            )
        )
        return "prompt_calculation_result"

    result = plan_from_terminal_node(
        calculation_type="source gap",
        terminal_node_id="needs_runtime_result",
        interactor=FakeInteractor(source_gap=SourceGapResponse(kind="user_input")),
        graph_dir=tmp_path,
        summaries_fn=lambda: summaries,
        create_leaf_stub_fn=fake_create_leaf_stub,
    )

    assert result.graph.nodes == ["needs_runtime_result", "prompt_calculation_result"]
    assert result.graph.edges[0].from_node == "prompt_calculation_result"


def test_source_gap_missing_computation_raises(tmp_path: Path) -> None:
    terminal_summary = NodeSummary(
        id="needs_missing_value",
        node_type="computation",
        description="Needs a missing computation.",
        when_to_use="Test source gap.",
        assumptions=[],
        inputs=[NodeInput(name="result", type="calc_types.example.CalculationResult")],
        output="calc_types.example.DoubledValue",
        references=[],
    )

    with pytest.raises(MissingNodeError, match="Missing computation node"):
        plan_from_terminal_node(
            calculation_type="missing computation",
            terminal_node_id="needs_missing_value",
            interactor=FakeInteractor(
                source_gap=SourceGapResponse(
                    kind="missing_computation",
                    detail="derive result first",
                )
            ),
            graph_dir=tmp_path,
            summaries_fn=lambda: [terminal_summary],
        )
