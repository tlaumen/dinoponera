from __future__ import annotations

from pathlib import Path

import calculate
from dinoponera.core.models import CalculationGraph, NodeSummary


def test_calculate_script_prompts_plans_generates_and_does_not_run(monkeypatch, tmp_path) -> None:
    graph = CalculationGraph(
        name="example",
        terminal_node_id="terminal",
        nodes=["terminal"],
        edges=[],
    )
    seen: dict[str, object] = {}

    def fake_plan_calculation(problem, interactor):
        seen["problem"] = problem
        seen["interactor"] = interactor
        return graph

    def fake_write_run_script(planned_graph):
        seen["graph"] = planned_graph
        return tmp_path / "run_example.py"

    monkeypatch.setattr(calculate, "plan_calculation", fake_plan_calculation)
    monkeypatch.setattr(calculate, "write_run_script", fake_write_run_script)

    answers = iter(["calculate the example", "n"])
    exit_code = calculate.main(input_fn=lambda prompt: next(answers))

    assert exit_code == 0
    assert seen["problem"] == "calculate the example"
    assert seen["graph"] == graph


def test_calculate_script_can_run_generated_script(monkeypatch, tmp_path) -> None:
    graph = CalculationGraph(
        name="example",
        terminal_node_id="terminal",
        nodes=["terminal"],
        edges=[],
    )
    script_path = tmp_path / "run_example.py"
    seen: dict[str, object] = {}

    class Completed:
        returncode = 7

    def fake_run(command, check):
        seen["command"] = command
        seen["check"] = check
        return Completed()

    monkeypatch.setattr(calculate, "plan_calculation", lambda problem, interactor: graph)
    monkeypatch.setattr(calculate, "write_run_script", lambda planned_graph: script_path)
    monkeypatch.setattr(calculate.subprocess, "run", fake_run)

    answers = iter(["calculate the example", "yes"])
    exit_code = calculate.main(input_fn=lambda prompt: next(answers))

    assert exit_code == 7
    assert seen["command"][-1] == str(script_path)
    assert seen["check"] is False


def test_calculate_script_warns_and_does_not_run_unimplemented_stubs(monkeypatch, tmp_path) -> None:
    graph = CalculationGraph(
        name="with_stub",
        terminal_node_id="reader_base_value",
        nodes=["reader_base_value"],
        edges=[],
    )
    script_path = tmp_path / "run_with_stub.py"
    run_called = False

    def fake_run(command, check):
        nonlocal run_called
        run_called = True
        raise AssertionError("subprocess.run should not be called")

    monkeypatch.setattr(calculate, "plan_calculation", lambda problem, interactor: graph)
    monkeypatch.setattr(calculate, "write_run_script", lambda planned_graph: script_path)
    monkeypatch.setattr(
        calculate.registry_index,
        "summaries",
        lambda: [
            NodeSummary(
                id="reader_base_value",
                node_type="data_retrieval",
                description="Generated reader.",
                when_to_use="Test.",
                assumptions=["Generated stub; implement before running."],
                inputs=[],
                output="calc_types.example.BaseValue",
                references=[],
            )
        ],
    )
    monkeypatch.setattr(calculate.subprocess, "run", fake_run)

    answers = iter(["calculate with source", "y", "n"])
    exit_code = calculate.main(input_fn=lambda prompt: next(answers))

    assert exit_code == 0
    assert run_called is False


def test_calculate_script_rejects_empty_problem() -> None:
    assert calculate.main(input_fn=lambda prompt: "   ") == 1
