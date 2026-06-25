from __future__ import annotations

from dinoponera.agent.io import ConsoleInteractor
from dinoponera.core.models import NodeSummary, StateSummary, UnresolvedInput


def test_console_confirm_goal_parses_yes_and_no(monkeypatch) -> None:
    interactor = ConsoleInteractor()

    monkeypatch.setattr("builtins.input", lambda prompt: "yes")
    assert interactor.confirm_goal("Example", "format_result") is True

    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    assert interactor.confirm_goal("Example", "format_result") is False


def test_console_applicability_can_choose_candidate(monkeypatch) -> None:
    interactor = ConsoleInteractor()
    candidate = NodeSummary(
        id="double_value",
        node_type="computation",
        description="Double value.",
        when_to_use="Test.",
        assumptions=[],
        inputs=[],
        output="calc_types.example.DoubledValue",
        references=[],
    )

    monkeypatch.setattr("builtins.input", lambda prompt: "1")
    response = interactor.resolve_applicability("Choose", [candidate])

    assert response.kind == "chosen"
    assert response.node_id == "double_value"


def test_console_source_gap_can_choose_data_retrieval(monkeypatch) -> None:
    interactor = ConsoleInteractor()
    answers = iter(["1", "because external data"])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    response = interactor.resolve_source_gap(
        UnresolvedInput(
            node_id="format_result",
            input_name="doubled",
            input_type="calc_types.example.DoubledValue",
        ),
        StateSummary(goal="Example"),
    )

    assert response.kind == "data_retrieval"
    assert response.detail == "because external data"
