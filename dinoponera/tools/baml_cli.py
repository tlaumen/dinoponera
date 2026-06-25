"""Run the BAML CLI with Dinoponera's .env loaded."""

from __future__ import annotations

import os
import subprocess
import sys

from dinoponera.config import load_environment


def main(argv: list[str] | None = None) -> int:
    load_environment()
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = ["--help"]
    command = ["npx", "-y", "@boundaryml/baml", *args]
    return subprocess.run(command, env=os.environ.copy(), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
