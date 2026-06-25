"""Human-readable graph rendering for review."""

from __future__ import annotations

from dinoponera.core.models import CalculationGraph, NodeSummary


def render_graph(graph: CalculationGraph, summaries: list[NodeSummary]) -> str:
    summary_by_id = {summary.id: summary for summary in summaries}

    lines: list[str] = [
        f"Calculation graph: {graph.name}",
        f"Terminal node: {graph.terminal_node_id}",
        "",
        "Nodes:",
    ]

    for node_id in graph.nodes:
        summary = summary_by_id.get(node_id)
        if summary is None:
            lines.append(f"- {node_id} [unknown]")
            continue
        lines.append(f"- {node_id} [{summary.node_type}] -> {summary.output}")
        if summary.description:
            lines.append(f"  {summary.description}")
        if summary.inputs:
            rendered_inputs = ", ".join(
                f"{node_input.name}: {node_input.type}" for node_input in summary.inputs
            )
            lines.append(f"  inputs: {rendered_inputs}")

    lines.extend(["", "Connections:"])
    if not graph.edges:
        lines.append("- none")
    else:
        for edge in graph.edges:
            lines.append(
                f"- {edge.from_node} -> {edge.to_node}.{edge.to_input} ({edge.type})"
            )

    return "\n".join(lines)
