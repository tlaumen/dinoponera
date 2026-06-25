"""Deterministic generation of leaf source node stubs."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

from dinoponera.core.naming import import_path_leaf, to_snake_case

SUPPORTED_LEAF_NODE_TYPES = {"data_retrieval", "user_input"}
_NODE_PREFIX = {
    "data_retrieval": "reader",
    "user_input": "prompt",
}


class LeafStubGenerationError(ValueError):
    """Raised when a leaf source stub cannot be generated."""


def _split_type_path(output_type_path: str) -> tuple[str, str]:
    try:
        module_path, class_name = output_type_path.rsplit(".", 1)
    except ValueError as exc:
        raise LeafStubGenerationError(f"Invalid output type path: {output_type_path}") from exc
    return module_path, class_name


def _candidate_node_id(node_type: str, output_type_path: str, counter: int | None = None) -> str:
    base = f"{_NODE_PREFIX[node_type]}_{to_snake_case(import_path_leaf(output_type_path))}"
    if counter is None:
        return base
    return f"{base}_{counter}"


def _node_id_available(node_id: str, project_root: Path, registry_index: ModuleType) -> bool:
    node_file = project_root / "registry" / "nodes" / f"{node_id}.py"
    exists = getattr(registry_index, "exists", lambda value: False)
    return not node_file.exists() and not exists(node_id)


def _next_node_id(node_type: str, output_type_path: str, project_root: Path, registry_index: ModuleType) -> str:
    node_id = _candidate_node_id(node_type, output_type_path)
    if _node_id_available(node_id, project_root, registry_index):
        return node_id

    counter = 2
    while True:
        node_id = _candidate_node_id(node_type, output_type_path, counter)
        if _node_id_available(node_id, project_root, registry_index):
            return node_id
        counter += 1


def _stub_source(node_id: str, node_type: str, output_type_path: str) -> str:
    module_path, class_name = _split_type_path(output_type_path)
    source_kind = "data retrieval" if node_type == "data_retrieval" else "user input"
    return f'''"""Generated {source_kind} leaf stub for {output_type_path}."""

from __future__ import annotations

from {module_path} import {class_name}
from registry.decorators import node


@node(
    node_type="{node_type}",
    description="Generated {source_kind} source for {output_type_path}.",
    when_to_use="Use when {output_type_path} must be supplied as a leaf source value.",
    assumptions=["Generated stub; implement before running."],
    references=[],
)
def {node_id}() -> {class_name}:
    raise NotImplementedError("Stub — implement before running")
'''


def _update_registry_index(index_path: Path, node_id: str) -> None:
    text = index_path.read_text()
    import_line = f"from registry.nodes.{node_id} import {node_id}\n"
    if import_line not in text:
        marker = "\nNODES: list[Callable[..., object]] = ["
        if marker not in text:
            raise LeafStubGenerationError(
                f"Cannot find explicit NODES declaration in {index_path}"
            )
        text = text.replace(marker, f"\n{import_line}{marker}", 1)

    node_line = f"    {node_id},\n"
    if node_line not in text:
        start = text.find("NODES: list[Callable[..., object]] = [")
        if start == -1:
            raise LeafStubGenerationError(
                f"Cannot find explicit NODES declaration in {index_path}"
            )
        close = text.find("\n]", start)
        if close == -1:
            raise LeafStubGenerationError(f"Cannot find end of NODES list in {index_path}")
        text = f"{text[:close]}\n{node_line}{text[close:]}"

    index_path.write_text(text)


def create_leaf_stub(
    node_type: str,
    output_type_path: str,
    *,
    project_root: str | Path = ".",
) -> str:
    """Create and register a deterministic source leaf stub.

    Supports only MVP source leaf node types: ``data_retrieval`` and
    ``user_input``. The generated node is persisted in ``registry/index.py`` and
    appended to the already-imported in-memory ``registry.index.NODES`` list so
    planning can continue without restarting the process.
    """

    if node_type not in SUPPORTED_LEAF_NODE_TYPES:
        raise LeafStubGenerationError(
            f"Unsupported leaf node type {node_type!r}; expected one of "
            f"{sorted(SUPPORTED_LEAF_NODE_TYPES)}"
        )

    project_root = Path(project_root)
    registry_nodes_dir = project_root / "registry" / "nodes"
    registry_index_path = project_root / "registry" / "index.py"
    registry_nodes_dir.mkdir(parents=True, exist_ok=True)

    from registry import index as registry_index

    node_id = _next_node_id(node_type, output_type_path, project_root, registry_index)
    node_path = registry_nodes_dir / f"{node_id}.py"
    node_path.write_text(_stub_source(node_id, node_type, output_type_path))
    _update_registry_index(registry_index_path, node_id)

    root_string = str(project_root.resolve())
    if root_string not in sys.path:
        sys.path.insert(0, root_string)
    importlib.invalidate_caches()
    module = importlib.import_module(f"registry.nodes.{node_id}")
    fn = getattr(module, node_id)
    registry_index.NODES.append(fn)
    return node_id
