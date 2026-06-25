"""Build registry summaries from decorated Python node functions."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, get_type_hints

from pydantic import BaseModel

from dinoponera.core.models import NodeInput, NodeSummary
from registry.decorators import NodeMetadata


class RegistryIntrospectionError(ValueError):
    """Raised when a registry node does not satisfy the node contract."""


def type_import_path(annotation: Any) -> str:
    """Return a full import path for an annotated domain Pydantic type."""

    if not inspect.isclass(annotation):
        raise RegistryIntrospectionError(
            f"Node I/O annotation {annotation!r} is not an importable class"
        )
    if not issubclass(annotation, BaseModel):
        raise RegistryIntrospectionError(
            f"Node I/O annotation {annotation!r} must be a pydantic.BaseModel subclass"
        )
    module = annotation.__module__
    qualname = annotation.__qualname__
    if module == "builtins":
        raise RegistryIntrospectionError(
            f"Node I/O annotation {annotation!r} must not be a primitive type"
        )
    return f"{module}.{qualname}"


def build_summary(fn: Callable[..., object]) -> NodeSummary:
    """Inspect a decorated node function and return its serializable summary."""

    metadata = getattr(fn, "_node_metadata", None)
    if not isinstance(metadata, NodeMetadata):
        raise RegistryIntrospectionError(
            f"Node function {fn.__name__!r} is missing @node metadata"
        )

    signature = inspect.signature(fn)
    try:
        type_hints = get_type_hints(fn)
    except Exception as exc:
        raise RegistryIntrospectionError(
            f"Node function {fn.__name__!r} has unresolved or invalid type annotations"
        ) from exc

    inputs: list[NodeInput] = []
    for parameter in signature.parameters.values():
        if parameter.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            raise RegistryIntrospectionError(
                f"Node function {fn.__name__!r} parameter {parameter.name!r} "
                "must be positional-or-keyword or keyword-only"
            )
        if parameter.name not in type_hints:
            raise RegistryIntrospectionError(
                f"Node function {fn.__name__!r} parameter {parameter.name!r} "
                "is missing a type annotation"
            )
        inputs.append(
            NodeInput(name=parameter.name, type=type_import_path(type_hints[parameter.name]))
        )

    if "return" not in type_hints:
        raise RegistryIntrospectionError(
            f"Node function {fn.__name__!r} is missing a return annotation"
        )

    return NodeSummary(
        id=fn.__name__,
        node_type=metadata.node_type,
        description=metadata.description,
        when_to_use=metadata.when_to_use,
        assumptions=metadata.assumptions,
        inputs=inputs,
        output=type_import_path(type_hints["return"]),
        references=metadata.references,
    )
