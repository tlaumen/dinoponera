"""Simple interactive Dinoponera entrypoint.

This is the user-facing loop:
1. ask what to calculate,
2. run the BAML-assisted planning/approval loop,
3. generate the standalone execution script,
4. optionally run that script.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Callable

from dinoponera.agent.io import ConsoleInteractor
from dinoponera.agent.planning import plan_calculation
from dinoponera.core.models import CalculationGraph
from dinoponera.core.render import render_graph
from dinoponera.core.script_generation import write_run_script
from registry import index as registry_index


def _yes_no(prompt: str, input_fn: Callable[[str], str] = input) -> bool:
    while True:
        choice = input_fn(prompt).strip().lower()
        if choice in {"y", "yes"}:
            return True
        if choice in {"n", "no", ""}:
            return False
        print("Please answer y or n.")


def _nodes_requiring_implementation(graph: CalculationGraph) -> list[str]:
    summaries = {summary.id: summary for summary in registry_index.summaries()}
    result: list[str] = []
    for node_id in graph.nodes:
        summary = summaries.get(node_id)
        if summary is None:
            continue
        assumptions = "\n".join(summary.assumptions).lower()
        if "generated stub" in assumptions or "implement before running" in assumptions:
            result.append(node_id)
    return result


def main(input_fn: Callable[[str], str] = input) -> int:
    problem = input_fn("What do you want to calculate?\n> ").strip()
    if not problem:
        print("No calculation problem provided.")
        return 1

    graph = plan_calculation(problem, ConsoleInteractor())
    graph_path = Path("graphs") / f"{graph.name}.json"
    script_path = write_run_script(graph)
    needs_implementation = _nodes_requiring_implementation(graph)

    print("\nApproved graph summary:")
    print(render_graph(graph, registry_index.summaries()))
    print(f"Graph written to: {graph_path}")
    print(f"Execution script written to: {script_path}")

    if needs_implementation:
        print("\nWarning: generated leaf stubs must be implemented before reliable execution:")
        for node_id in needs_implementation:
            print(f"- registry/nodes/{node_id}.py")

    if _yes_no("Run the generated execution script now? [y/N] ", input_fn):
        if needs_implementation and not _yes_no(
            "This graph contains unimplemented stubs. Run anyway? [y/N] ", input_fn
        ):
            print(f"To execute after implementing stubs, run: {sys.executable} {script_path}")
            return 0
        completed = subprocess.run([sys.executable, str(script_path)], check=False)
        return completed.returncode

    print(f"To execute later, run: {sys.executable} {script_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
