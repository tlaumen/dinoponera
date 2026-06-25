"""Dinoponera calculation-agent framework."""

from dinoponera.config import load_environment

# Load repo/user .env values as soon as the package is imported. This ensures
# provider credentials such as ANTHROPIC_API_KEY are visible before live BAML
# calls are made from dinoponera.agent.planning.
load_environment()

__all__ = ["load_environment"]
