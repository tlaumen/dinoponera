from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from dinoponera.core.leaf_stub_generation import (
    LeafStubGenerationError,
    create_leaf_stub,
)
from registry import index as registry_index

OUTPUT_TYPE = "calc_types.example.CalculationResult"
GENERATED_NODE_IDS = [
    "reader_calculation_result",
    "reader_calculation_result_2",
    "prompt_calculation_result",
]


@pytest.fixture()
def clean_leaf_stub_side_effects():
    index_path = Path("registry/index.py")
    original_index_text = index_path.read_text()
    original_nodes = list(registry_index.NODES)

    def cleanup() -> None:
        for node_id in GENERATED_NODE_IDS:
            Path(f"registry/nodes/{node_id}.py").unlink(missing_ok=True)
            sys.modules.pop(f"registry.nodes.{node_id}", None)
        registry_index.NODES[:] = [
            fn for fn in registry_index.NODES if fn.__name__ not in GENERATED_NODE_IDS
        ]
        importlib.invalidate_caches()

    cleanup()
    try:
        yield
    finally:
        index_path.write_text(original_index_text)
        registry_index.NODES[:] = original_nodes
        cleanup()


def test_data_retrieval_stub_is_generated_and_registered(clean_leaf_stub_side_effects) -> None:
    node_id = create_leaf_stub("data_retrieval", OUTPUT_TYPE)

    assert node_id == "reader_calculation_result"
    node_path = Path("registry/nodes/reader_calculation_result.py")
    source = node_path.read_text()
    assert "from calc_types.example import CalculationResult" in source
    assert 'node_type="data_retrieval"' in source
    assert "def reader_calculation_result() -> CalculationResult:" in source
    assert 'raise NotImplementedError("Stub — implement before running")' in source

    index_text = Path("registry/index.py").read_text()
    assert "from registry.nodes.reader_calculation_result import reader_calculation_result" in index_text
    assert "    reader_calculation_result," in index_text

    assert registry_index.exists("reader_calculation_result")
    summary = registry_index.get_summary("reader_calculation_result")
    assert summary.node_type == "data_retrieval"
    assert summary.inputs == []
    assert summary.output == OUTPUT_TYPE


def test_user_input_stub_uses_prompt_prefix(clean_leaf_stub_side_effects) -> None:
    node_id = create_leaf_stub("user_input", OUTPUT_TYPE)

    assert node_id == "prompt_calculation_result"
    source = Path("registry/nodes/prompt_calculation_result.py").read_text()
    assert 'node_type="user_input"' in source
    assert "def prompt_calculation_result() -> CalculationResult:" in source
    assert registry_index.get_summary("prompt_calculation_result").node_type == "user_input"


def test_stub_generation_appends_numeric_suffix_on_collision(clean_leaf_stub_side_effects) -> None:
    first = create_leaf_stub("data_retrieval", OUTPUT_TYPE)
    second = create_leaf_stub("data_retrieval", OUTPUT_TYPE)

    assert first == "reader_calculation_result"
    assert second == "reader_calculation_result_2"
    assert Path("registry/nodes/reader_calculation_result_2.py").exists()
    assert registry_index.exists("reader_calculation_result_2")


def test_unsupported_leaf_node_type_fails(clean_leaf_stub_side_effects) -> None:
    with pytest.raises(LeafStubGenerationError, match="Unsupported leaf node type"):
        create_leaf_stub("computation", OUTPUT_TYPE)
