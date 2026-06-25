"""Naming helpers for graph files, generated variables, and stubs."""

from __future__ import annotations

import re


_NON_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]+")
_CAMEL_BOUNDARY_1_RE = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_BOUNDARY_2_RE = re.compile(r"([a-z0-9])([A-Z])")


def normalise_name(value: str) -> str:
    """Normalize a human calculation name for graph/run filenames."""

    normalized = _NON_ALNUM_RE.sub("_", value.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "calculation"


def to_snake_case(value: str) -> str:
    """Convert PascalCase/camelCase/free text to snake_case."""

    value = value.strip().replace("-", "_").replace(" ", "_")
    value = _CAMEL_BOUNDARY_1_RE.sub(r"\1_\2", value)
    value = _CAMEL_BOUNDARY_2_RE.sub(r"\1_\2", value)
    value = _NON_ALNUM_RE.sub("_", value).lower()
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "value"


def import_path_leaf(import_path: str) -> str:
    """Return the class/function name from a dotted import path."""

    return import_path.rsplit(".", 1)[-1]
