"""Package configuration helpers."""

from __future__ import annotations

from pathlib import Path

from dotenv import find_dotenv, load_dotenv


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
