"""Python-owned data models for registry summaries and calculation graphs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NodeInput(BaseModel):
    """A named input parameter for a registered node function."""

    name: str
    type: str


class NodeSummary(BaseModel):
    """Serializable summary of a registered node."""

    id: str
    node_type: str
    description: str
    when_to_use: str
    assumptions: list[str] = Field(default_factory=list)
    inputs: list[NodeInput] = Field(default_factory=list)
    output: str
    references: list[str] = Field(default_factory=list)


class UnresolvedInput(BaseModel):
    """A specific downstream node parameter that still needs a producer."""

    node_id: str
    input_name: str
    input_type: str


class Edge(BaseModel):
    """Producer-to-consumer graph edge satisfying a named downstream input."""

    from_node: str
    to_node: str
    to_input: str
    type: str


class CalculationGraph(BaseModel):
    """Approved calculation DAG serialized to graphs/{name}.json."""

    name: str
    terminal_node_id: str
    nodes: list[str]
    edges: list[Edge] = Field(default_factory=list)

    def has_edge(self, to: str, to_input: str, type: str) -> bool:
        return any(
            edge.to_node == to and edge.to_input == to_input and edge.type == type
            for edge in self.edges
        )


class QA(BaseModel):
    question: str
    answer: str


class StateSummary(BaseModel):
    goal: str
    decisions: list[str] = Field(default_factory=list)
    open_items: list[str] = Field(default_factory=list)
    phase1_clarification_summary: str = ""


class ApplicabilityResponse(BaseModel):
    kind: Literal["chosen", "rejected_all", "unsure"]
    node_id: str | None = None
    detail: str | None = None


class SourceGapResponse(BaseModel):
    kind: Literal["data_retrieval", "user_input", "missing_computation"]
    detail: str | None = None
