"""Human-readable graph rendering for review."""

from __future__ import annotations

from dinoponera.core.models import CalculationGraph, NodeSummary


def _type_leaf(type_path: str) -> str:
    return type_path.rsplit(".", 1)[-1]


def _node_label(index: int) -> str:
    """Return spreadsheet-style labels: A, B, ..., Z, AA, AB, ..."""

    if index < 0:
        raise ValueError("Node label index must be non-negative")

    label = ""
    value = index
    while True:
        value, remainder = divmod(value, 26)
        label = chr(ord("A") + remainder) + label
        if value == 0:
            return label
        value -= 1


def render_graph(graph: CalculationGraph, summaries: list[NodeSummary]) -> str:
    summary_by_id = {summary.id: summary for summary in summaries}
    label_by_node = {node_id: _node_label(index) for index, node_id in enumerate(graph.nodes)}

    lines: list[str] = [
        f"Calculation graph: {graph.name}",
        f"Terminal node: {graph.terminal_node_id}",
        "",
        "Nodes:",
    ]

    for index, node_id in enumerate(graph.nodes):
        if index > 0:
            lines.append("")
        label = label_by_node[node_id]
        summary = summary_by_id.get(node_id)
        if summary is None:
            lines.append(f"{label}: {node_id} [unknown]")
            continue
        lines.append(f"{label}: {node_id} [{summary.node_type}]")
        lines.append(f"      output: {_type_leaf(summary.output)}")
        if summary.description:
            lines.append(f"      description: {summary.description}")
        if summary.inputs:
            rendered_inputs = ", ".join(
                f"{node_input.name}: {_type_leaf(node_input.type)}" for node_input in summary.inputs
            )
            lines.append(f"      inputs: {rendered_inputs}")

    lines.extend(["", "Connections:"])
    if not graph.edges:
        lines.append("- none")
    else:
        for edge in graph.edges:
            from_label = label_by_node.get(edge.from_node, edge.from_node)
            to_label = label_by_node.get(edge.to_node, edge.to_node)
            lines.append(f"{from_label} -> {to_label} ({edge.to_input})")

    return "\n".join(lines)
