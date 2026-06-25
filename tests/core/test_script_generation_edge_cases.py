from __future__ import annotations

from pydantic import BaseModel

from dinoponera.core.models import CalculationGraph, Edge
from dinoponera.core.script_generation import generate_script_source, topological_sort
from registry import index as registry_index
from registry.decorators import node


class SharedValue(BaseModel):
    value: float


class CombinedResult(BaseModel):
    total: float


class ChainValue(BaseModel):
    value: float


class FinalValue(BaseModel):
    value: float


@node(
    node_type="data_retrieval",
    description="Return left shared value.",
    when_to_use="Testing duplicate output-type variable names.",
)
def left_shared_value() -> SharedValue:
    return SharedValue(value=1.0)


@node(
    node_type="data_retrieval",
    description="Return right shared value.",
    when_to_use="Testing duplicate output-type variable names.",
)
def right_shared_value() -> SharedValue:
    return SharedValue(value=2.0)


@node(
    node_type="computation",
    description="Combine two shared values.",
    when_to_use="Testing duplicate input types on one node.",
)
def combine_shared_values(left: SharedValue, right: SharedValue) -> CombinedResult:
    return CombinedResult(total=left.value + right.value)


@node(
    node_type="data_retrieval",
    description="Return chain value.",
    when_to_use="Testing same-type transformer chains.",
)
def chain_source_value() -> ChainValue:
    return ChainValue(value=1.0)


@node(
    node_type="computation",
    description="Transform a value without changing its type.",
    when_to_use="Testing same input/output type nodes.",
)
def normalize_chain_value(value: ChainValue) -> ChainValue:
    return ChainValue(value=value.value)


@node(
    node_type="computation",
    description="Consume chain value.",
    when_to_use="Testing same-type transformer chains.",
)
def finish_chain_value(value: ChainValue) -> FinalValue:
    return FinalValue(value=value.value)


def test_script_generation_disambiguates_variable_name_collisions(monkeypatch) -> None:
    monkeypatch.setattr(
        registry_index,
        "NODES",
        [left_shared_value, right_shared_value, combine_shared_values],
    )
    graph = CalculationGraph(
        name="collision",
        terminal_node_id="combine_shared_values",
        nodes=["combine_shared_values", "left_shared_value", "right_shared_value"],
        edges=[
            Edge(
                from_node="left_shared_value",
                to_node="combine_shared_values",
                to_input="left",
                type=f"{SharedValue.__module__}.SharedValue",
            ),
            Edge(
                from_node="right_shared_value",
                to_node="combine_shared_values",
                to_input="right",
                type=f"{SharedValue.__module__}.SharedValue",
            ),
        ],
    )

    assert topological_sort(graph) == [
        "left_shared_value",
        "right_shared_value",
        "combine_shared_values",
    ]
    source = generate_script_source(graph)

    assert "shared_value = left_shared_value()" in source
    assert "shared_value_right_shared_value = right_shared_value()" in source
    assert (
        "combined_result = combine_shared_values(left=shared_value, "
        "right=shared_value_right_shared_value)"
    ) in source
    assert "def run() -> CombinedResult:" in source


def test_script_generation_handles_same_type_transformer_nodes(monkeypatch) -> None:
    monkeypatch.setattr(
        registry_index,
        "NODES",
        [chain_source_value, normalize_chain_value, finish_chain_value],
    )
    graph = CalculationGraph(
        name="same_type_transformer",
        terminal_node_id="finish_chain_value",
        nodes=["finish_chain_value", "normalize_chain_value", "chain_source_value"],
        edges=[
            Edge(
                from_node="normalize_chain_value",
                to_node="finish_chain_value",
                to_input="value",
                type=f"{ChainValue.__module__}.ChainValue",
            ),
            Edge(
                from_node="chain_source_value",
                to_node="normalize_chain_value",
                to_input="value",
                type=f"{ChainValue.__module__}.ChainValue",
            ),
        ],
    )

    assert topological_sort(graph) == [
        "chain_source_value",
        "normalize_chain_value",
        "finish_chain_value",
    ]
    source = generate_script_source(graph)

    assert "chain_value = chain_source_value()" in source
    assert "chain_value_normalize_chain_value = normalize_chain_value(value=chain_value)" in source
    assert "final_value = finish_chain_value(value=chain_value_normalize_chain_value)" in source
    assert "def run() -> FinalValue:" in source
