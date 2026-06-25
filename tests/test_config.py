from __future__ import annotations

import os

from dinoponera.config import load_environment


def test_load_environment_loads_explicit_dotenv_without_overriding(monkeypatch, tmp_path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("DINOPONERA_TEST_ENV=from-file\nDINOPONERA_KEEP=from-file\n")
    monkeypatch.setenv("DINOPONERA_KEEP", "from-env")
    monkeypatch.delenv("DINOPONERA_TEST_ENV", raising=False)

    assert load_environment(dotenv_path) is True

    assert os.environ["DINOPONERA_TEST_ENV"] == "from-file"
    assert os.environ["DINOPONERA_KEEP"] == "from-env"


def test_load_environment_can_override_when_requested(monkeypatch, tmp_path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("DINOPONERA_OVERRIDE=from-file\n")
    monkeypatch.setenv("DINOPONERA_OVERRIDE", "from-env")

    assert load_environment(dotenv_path, override=True) is True

    assert os.environ["DINOPONERA_OVERRIDE"] == "from-file"
