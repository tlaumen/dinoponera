from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from baml_client.types import GoalIdentificationKind, GraphExtensionKind

from dinoponera.agent import planning
from dinoponera.core.models import (
    ApplicabilityResponse,
    CalculationGraph,
    NodeInput,
    NodeSummary,
    SourceGapResponse,
    StateSummary,
    UnresolvedInput,
)
from registry import index as registry_index


class FakeInteractor:
    def __init__(
        self,
        *,
        confirmations: list[bool] | None = None,
        approve: bool = True,
        applicability: ApplicabilityResponse | None = None,
        source_gap: SourceGapResponse | None = None,
    ) -> None:
        self.confirmations = confirmations or [True]
        self.approve = approve
        self.applicability = applicability
        self.source_gap = source_gap
        self.clarification_questions: list[str] = []
        self.rendered: str | None = None

    def ask_clarification(self, question: str, context: str | None = None) -> str:
        self.clarification_questions.append(question)
        return "clarified answer"

    def confirm_goal(self, calculation_type: str, terminal_node_id: str) -> bool:
        return self.confirmations.pop(0)

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


def goal(calculation_type: str, terminal_node_id: str | None) -> SimpleNamespace:
    return SimpleNamespace(
        kind="GoalClear",
        calculation_type=calculation_type,
        terminal_node_id=terminal_node_id,
        state_summary=StateSummary(goal=calculation_type),
    )


def test_variant_name_handles_generated_baml_enums() -> None:
    assert planning._variant_name(SimpleNamespace(kind=GoalIdentificationKind.GoalClear)) == "goalclear"
    assert planning._variant_name(SimpleNamespace(kind=GraphExtensionKind.AddFromRegistry)) == "addfromregistry"


def test_phase1_clarification_loop(monkeypatch) -> None:
    responses = iter(
        [
            SimpleNamespace(kind="NeedsClarification", question="Which result?", context="ctx"),
            goal("Example", "example_source_value"),
        ]
    )
    seen_clarification_counts: list[int] = []

    def fake_identify(problem, registry, clarifications):
        seen_clarification_counts.append(len(clarifications))
        return next(responses)

    monkeypatch.setattr(planning, "baml_identify_goal", fake_identify)
    interactor = FakeInteractor()

    result = planning.identify_goal_loop("problem", interactor)

    assert result.terminal_node_id == "example_source_value"
    assert interactor.clarification_questions == ["Which result?"]
    assert seen_clarification_counts == [0, 1]


def test_goal_confirmation_rejected_replans_with_user_correction(monkeypatch) -> None:
    responses = iter([goal("Wrong", "example_source_value"), goal("Right", "example_source_value")])
    seen_clarification_counts: list[int] = []

    def fake_identify(problem, registry, clarifications):
        seen_clarification_counts.append(len(clarifications))
        return next(responses)

    monkeypatch.setattr(planning, "baml_identify_goal", fake_identify)
    interactor = FakeInteractor(confirmations=[False, True])

    result = planning.identify_goal_loop("problem", interactor)

    assert result.calculation_type == "Right"
    assert interactor.clarification_questions == [
        "What should change about the calculation goal or terminal result?"
    ]
    assert seen_clarification_counts == [0, 1]


def test_missing_terminal_node_reports_missing_node(monkeypatch) -> None:
    monkeypatch.setattr(
        planning,
        "baml_identify_goal",
        lambda *args: SimpleNamespace(
            kind="GoalClear",
            calculation_type="Missing",
            terminal_node_id=None,
            missing_description="Need terminal calculation.",
            state_summary=StateSummary(goal="Missing"),
        ),
    )

    with pytest.raises(planning.MissingNodeError, match="No terminal node"):
        planning.identify_goal_loop("problem", FakeInteractor())


def test_plan_calculation_add_from_registry_serializes_graph(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(planning, "baml_identify_goal", lambda *args: goal("BAML example", "format_result"))
    responses = iter(
        [
            SimpleNamespace(kind="AddFromRegistry", node_id="double_value"),
            SimpleNamespace(kind="AddFromRegistry", node_id="example_source_value"),
        ]
    )
    monkeypatch.setattr(planning, "baml_extend_graph", lambda *args: next(responses))

    graph = planning.plan_calculation("problem", FakeInteractor(), graph_dir=tmp_path)

    assert graph.name == "baml_example"
    assert graph.nodes == ["format_result", "double_value", "example_source_value"]
    assert (tmp_path / "baml_example.json").exists()


def test_build_graph_connect_existing_path(monkeypatch, tmp_path: Path) -> None:
    summaries = [
        NodeSummary(
            id="combine_base_values",
            node_type="computation",
            description="Combine two base values.",
            when_to_use="Test.",
            assumptions=[],
            inputs=[
                NodeInput(name="left", type="calc_types.example.BaseValue"),
                NodeInput(name="right", type="calc_types.example.BaseValue"),
            ],
            output="calc_types.example.CalculationResult",
            references=[],
        ),
        NodeSummary(
            id="example_source_value",
            node_type="data_retrieval",
            description="Source.",
            when_to_use="Test.",
            assumptions=[],
            inputs=[],
            output="calc_types.example.BaseValue",
            references=[],
        ),
    ]
    responses = iter(
        [
            SimpleNamespace(kind="AddFromRegistry", node_id="example_source_value"),
            SimpleNamespace(kind="ConnectExisting", from_node_id="example_source_value"),
        ]
    )
    monkeypatch.setattr(planning, "baml_extend_graph", lambda *args: next(responses))

    graph = planning.build_graph_loop(
        goal("Combine", "combine_base_values"),
        FakeInteractor(),
        graph_dir=tmp_path,
        summaries_fn=lambda: summaries,
    )

    assert [edge.to_input for edge in graph.edges] == ["left", "right"]
    assert all(edge.from_node == "example_source_value" for edge in graph.edges)


def test_applicability_check_path(monkeypatch, tmp_path: Path) -> None:
    responses = iter(
        [
            SimpleNamespace(
                kind="ApplicabilityCheck",
                question="Which doubler?",
                candidates=[registry_index.get_summary("double_value")],
            ),
            SimpleNamespace(kind="AddFromRegistry", node_id="example_source_value"),
        ]
    )
    monkeypatch.setattr(planning, "baml_extend_graph", lambda *args: next(responses))

    graph = planning.build_graph_loop(
        goal("Applicability", "format_result"),
        FakeInteractor(applicability=ApplicabilityResponse(kind="chosen", node_id="double_value")),
        graph_dir=tmp_path,
    )

    assert graph.edges[0].from_node == "double_value"
    assert graph.edges[0].to_input == "doubled"


def test_no_candidate_path_creates_leaf_stub_with_injected_generator(monkeypatch, tmp_path: Path) -> None:
    summaries = [
        NodeSummary(
            id="needs_source_value",
            node_type="computation",
            description="Needs source value.",
            when_to_use="Test.",
            assumptions=[],
            inputs=[NodeInput(name="base", type="calc_types.example.BaseValue")],
            output="calc_types.example.CalculationResult",
            references=[],
        )
    ]

    def fake_create_leaf_stub(node_type: str, output_type_path: str) -> str:
        assert node_type == "data_retrieval"
        summaries.append(
            NodeSummary(
                id="reader_base_value",
                node_type="data_retrieval",
                description="Generated reader.",
                when_to_use="Test.",
                assumptions=[],
                inputs=[],
                output=output_type_path,
                references=[],
            )
        )
        return "reader_base_value"

    monkeypatch.setattr(
        planning,
        "baml_extend_graph",
        lambda *args: SimpleNamespace(kind="NoCandidate"),
    )

    graph = planning.build_graph_loop(
        goal("No candidate", "needs_source_value"),
        FakeInteractor(source_gap=SourceGapResponse(kind="data_retrieval")),
        graph_dir=tmp_path,
        summaries_fn=lambda: summaries,
        create_leaf_stub_fn=fake_create_leaf_stub,
    )

    assert graph.nodes == ["needs_source_value", "reader_base_value"]
    assert graph.edges[0].from_node == "reader_base_value"


def test_no_candidate_missing_computation_raises(monkeypatch, tmp_path: Path) -> None:
    summaries = [
        NodeSummary(
            id="needs_source_value",
            node_type="computation",
            description="Needs source value.",
            when_to_use="Test.",
            assumptions=[],
            inputs=[NodeInput(name="base", type="calc_types.example.BaseValue")],
            output="calc_types.example.CalculationResult",
            references=[],
        )
    ]
    monkeypatch.setattr(
        planning,
        "baml_extend_graph",
        lambda *args: SimpleNamespace(kind="NoCandidate"),
    )

    with pytest.raises(planning.MissingNodeError, match="Missing computation node"):
        planning.build_graph_loop(
            goal("No candidate", "needs_source_value"),
            FakeInteractor(
                source_gap=SourceGapResponse(kind="missing_computation", detail="derive base")
            ),
            graph_dir=tmp_path,
            summaries_fn=lambda: summaries,
        )


def test_graph_approval_rejection_raises(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(planning, "baml_extend_graph", lambda *args: pytest.fail("not called"))

    with pytest.raises(planning.PlanningRejectedError, match="Graph rejected"):
        planning.build_graph_loop(
            goal("Rejected", "example_source_value"),
            FakeInteractor(approve=False),
            graph_dir=tmp_path,
        )

    assert list(tmp_path.iterdir()) == []


def test_add_from_registry_unknown_node_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        planning,
        "baml_extend_graph",
        lambda *args: SimpleNamespace(kind="AddFromRegistry", node_id="not_registered"),
    )

    with pytest.raises(planning.PlanningClarificationError, match="unknown producer"):
        planning.build_graph_loop(
            goal("Invalid producer", "format_result"),
            FakeInteractor(),
            graph_dir=tmp_path,
        )


def test_add_from_registry_wrong_output_type_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        planning,
        "baml_extend_graph",
        lambda *args: SimpleNamespace(kind="AddFromRegistry", node_id="example_source_value"),
    )

    with pytest.raises(planning.PlanningClarificationError, match="requires"):
        planning.build_graph_loop(
            goal("Wrong producer", "format_result"),
            FakeInteractor(),
            graph_dir=tmp_path,
        )


def test_connect_existing_requires_existing_graph_node(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        planning,
        "baml_extend_graph",
        lambda *args: SimpleNamespace(kind="ConnectExisting", from_node_id="double_value"),
    )

    with pytest.raises(planning.PlanningClarificationError, match="not already in graph"):
        planning.build_graph_loop(
            goal("Connect missing existing", "format_result"),
            FakeInteractor(),
            graph_dir=tmp_path,
        )


def test_applicability_choice_must_be_offered_candidate(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        planning,
        "baml_extend_graph",
        lambda *args: SimpleNamespace(
            kind="ApplicabilityCheck",
            question="Which node?",
            candidates=[registry_index.get_summary("double_value")],
        ),
    )

    with pytest.raises(planning.PlanningClarificationError, match="not one of"):
        planning.build_graph_loop(
            goal("Bad applicability", "format_result"),
            FakeInteractor(
                applicability=ApplicabilityResponse(kind="chosen", node_id="example_source_value")
            ),
            graph_dir=tmp_path,
        )


def test_add_from_registry_inconsistent_alias_ids_are_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        planning,
        "baml_extend_graph",
        lambda *args: SimpleNamespace(
            kind="AddFromRegistry",
            node_id="double_value",
            from_node_id="example_source_value",
        ),
    )

    with pytest.raises(planning.PlanningClarificationError, match="inconsistent producer ids"):
        planning.build_graph_loop(
            goal("Inconsistent ids", "format_result"),
            FakeInteractor(),
            graph_dir=tmp_path,
        )
