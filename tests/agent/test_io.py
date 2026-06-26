from __future__ import annotations

from dinoponera.agent.io import ConsoleInteractor
from dinoponera.core.models import NodeSummary, StateSummary, UnresolvedInput


def test_console_clarification_formats_context_and_question(monkeypatch, capsys) -> None:
    interactor = ConsoleInteractor()

    monkeypatch.setattr("builtins.input", lambda prompt: "  clarified answer  ")

    answer = interactor.ask_clarification(
        "Which settlement result do you need?",
        "The request could refer to immediate or consolidation settlement.",
    )

    output = capsys.readouterr().out
    assert answer == "clarified answer"
    assert "The request you made needs clarification" in output
    assert "The clarification is required because:" in output
    assert "    The request could refer to immediate or consolidation settlement." in output
    assert "Please clarify the following:" in output
    assert "    Which settlement result do you need?" in output


def test_console_clarification_wraps_long_context_and_question(monkeypatch, capsys) -> None:
    interactor = ConsoleInteractor()
    long_context = " ".join(["context"] * 30)
    long_question = " ".join(["question"] * 30)

    monkeypatch.setattr("builtins.input", lambda prompt: "answer")

    interactor.ask_clarification(long_question, long_context)

    output_lines = capsys.readouterr().out.splitlines()
    wrapped_lines = [line for line in output_lines if line.strip().startswith(("context", "question"))]

    assert len([line for line in wrapped_lines if "context" in line]) > 1
    assert len([line for line in wrapped_lines if "question" in line]) > 1
    assert all(line.startswith("    ") for line in wrapped_lines)
    assert all(len(line) <= 80 for line in wrapped_lines)


def test_console_clarification_omits_context_section_when_missing(monkeypatch, capsys) -> None:
    interactor = ConsoleInteractor()

    monkeypatch.setattr("builtins.input", lambda prompt: "answer")

    answer = interactor.ask_clarification("Which result?", None)

    output = capsys.readouterr().out
    assert answer == "answer"
    assert "The request you made needs clarification" in output
    assert "The clarification is required because:" not in output
    assert "Please clarify the following:" in output
    assert "    Which result?" in output


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
