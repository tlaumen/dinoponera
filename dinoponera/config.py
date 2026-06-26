"""Package configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


class ConfigurationError(RuntimeError):
    """Raised when required runtime configuration is missing."""


def load_environment(dotenv_path: str | Path | None = None, *, override: bool = False) -> bool:
    """Load environment variables from a .env file.

    Existing process environment variables win by default. When ``dotenv_path``
    is omitted, discovery starts at the current working directory so repo-local
    ``.env`` files are loaded for CLI/package usage.
    """

    path = str(dotenv_path) if dotenv_path is not None else find_dotenv(usecwd=True)
    if not path:
        return False
    return load_dotenv(path, override=override)


def require_anthropic_api_key() -> None:
    """Ensure live BAML calls have Anthropic credentials available."""

    load_environment()
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    raise ConfigurationError(
        "ANTHROPIC_API_KEY is not set. Set it in your environment or create a "
        "repo-local .env file containing ANTHROPIC_API_KEY=... before running "
        "live BAML planning commands."
    )
