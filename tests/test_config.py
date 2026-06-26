from __future__ import annotations

import os

import pytest

from dinoponera import config
from dinoponera.config import ConfigurationError, load_environment, require_anthropic_api_key


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


def test_require_anthropic_api_key_accepts_existing_environment_key(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "load_environment", lambda: False)

    require_anthropic_api_key()


def test_require_anthropic_api_key_accepts_key_loaded_from_dotenv(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def fake_load_environment() -> bool:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-from-dotenv")
        return True

    monkeypatch.setattr(config, "load_environment", fake_load_environment)

    require_anthropic_api_key()


def test_require_anthropic_api_key_fails_with_helpful_message(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(config, "load_environment", lambda: False)

    with pytest.raises(ConfigurationError) as exc_info:
        require_anthropic_api_key()

    message = str(exc_info.value)
    assert "ANTHROPIC_API_KEY is not set" in message
    assert ".env" in message
