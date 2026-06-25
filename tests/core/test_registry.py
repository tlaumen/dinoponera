from __future__ import annotations

import pytest
from pydantic import BaseModel

from dinoponera.core.registry_introspection import RegistryIntrospectionError, build_summary
from registry import index as registry_index
from registry.decorators import node
from registry.nodes.double_value import double_value
from registry.nodes.example_source_value import example_source_value
from registry.nodes.format_result import format_result


class DomainInput(BaseModel):
    value: float


class DomainOutput(BaseModel):
    value: float


@node(
    node_type="computation",
    description="Test node.",
    when_to_use="Registry tests.",
    assumptions=["test assumption"],
    references=["test reference"],
)
def sample_node(left: DomainInput, right: DomainInput) -> DomainOutput:
    return DomainOutput(value=left.value + right.value)


def test_node_decorator_metadata_and_build_summary() -> None:
    summary = build_summary(sample_node)

    assert summary.id == "sample_node"
    assert summary.node_type == "computation"
    assert summary.assumptions == ["test assumption"]
    assert [node_input.name for node_input in summary.inputs] == ["left", "right"]
    assert [node_input.type for node_input in summary.inputs] == [
        f"{DomainInput.__module__}.DomainInput",
        f"{DomainInput.__module__}.DomainInput",
    ]
    assert summary.output == f"{DomainOutput.__module__}.DomainOutput"


def test_missing_metadata_fails() -> None:
    def undecorated(value: DomainInput) -> DomainOutput:
        return DomainOutput(value=value.value)

    with pytest.raises(RegistryIntrospectionError, match="missing @node metadata"):
        build_summary(undecorated)


def test_missing_parameter_annotation_fails() -> None:
    @node(
        node_type="computation",
        description="Bad node.",
        when_to_use="Test.",
    )
    def bad_node(value) -> DomainOutput:  # noqa: ANN001
        return DomainOutput(value=value.value)

    with pytest.raises(RegistryIntrospectionError, match="missing a type annotation"):
        build_summary(bad_node)


def test_missing_return_annotation_fails() -> None:
    @node(
        node_type="computation",
        description="Bad node.",
        when_to_use="Test.",
    )
    def bad_node(value: DomainInput):  # noqa: ANN202
        return DomainOutput(value=value.value)

    with pytest.raises(RegistryIntrospectionError, match="missing a return annotation"):
        build_summary(bad_node)


def test_unresolved_annotation_fails() -> None:
    @node(
        node_type="computation",
        description="Bad node.",
        when_to_use="Test.",
    )
    def bad_node(value: "MissingDomainType") -> DomainOutput:  # noqa: F821
        return DomainOutput(value=value.value)

    with pytest.raises(RegistryIntrospectionError, match="unresolved or invalid type annotations"):
        build_summary(bad_node)


def test_primitive_io_annotation_fails() -> None:
    @node(
        node_type="computation",
        description="Bad node.",
        when_to_use="Test.",
    )
    def bad_node(value: int) -> DomainOutput:
        return DomainOutput(value=float(value))

    with pytest.raises(RegistryIntrospectionError, match="pydantic.BaseModel subclass"):
        build_summary(bad_node)


def test_registry_index_lookup_behaviour(monkeypatch) -> None:
    monkeypatch.setattr(
        registry_index,
        "NODES",
        [example_source_value, double_value, format_result],
    )

    summaries = registry_index.summaries()
    assert [summary.id for summary in summaries] == [
        "example_source_value",
        "double_value",
        "format_result",
    ]
    assert registry_index.get("double_value") is double_value
    assert registry_index.get_summary("format_result").output == "calc_types.example.CalculationResult"
    assert registry_index.exists("format_result") is True
    assert registry_index.exists("missing") is False

    with pytest.raises(registry_index.RegistryError, match="Unknown node id"):
        registry_index.get("missing")


def test_registry_index_duplicate_node_id_fails(monkeypatch) -> None:
    monkeypatch.setattr(registry_index, "NODES", [double_value, double_value])

    with pytest.raises(registry_index.RegistryError, match="Duplicate node id"):
        registry_index.summaries()
