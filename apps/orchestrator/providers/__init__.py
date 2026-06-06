"""Provider registry — get_provider(name) returns a configured provider instance.

Names recognised:
  aoai                  -> AOAIProvider (APIM-fronted by default)
  foundry, foundry-oai  -> FoundryProvider(shape="foundry-oai")
  foundry-anthropic     -> FoundryProvider(shape="foundry-anthropic")
  databricks            -> DatabricksAnthropicProvider
  anthropic, anthropic-direct -> AnthropicDirectProvider

Each call constructs a fresh provider (cheap — they hold no long-lived state
besides config). The caller passes via_apim through kwargs to override defaults.
"""
from __future__ import annotations

from typing import Any

from .anthropic_direct import AnthropicDirectProvider
from .aoai import AOAIProvider
from .base import ChatResponse, Provider
from .databricks import DatabricksAnthropicProvider
from .foundry import FoundryProvider

__all__ = [
    "ChatResponse",
    "Provider",
    "get_provider",
    "AOAIProvider",
    "FoundryProvider",
    "DatabricksAnthropicProvider",
    "AnthropicDirectProvider",
]


def get_provider(name: str, **kwargs: Any) -> Provider:
    """Resolve a provider by name. Raises ValueError on unknown names."""
    key = (name or "").strip().lower()
    if key == "aoai":
        return AOAIProvider(**kwargs)
    if key in ("foundry", "foundry-oai"):
        return FoundryProvider(shape="foundry-oai", **kwargs)
    if key == "foundry-anthropic":
        return FoundryProvider(shape="foundry-anthropic", **kwargs)
    if key == "databricks":
        return DatabricksAnthropicProvider(**kwargs)
    if key in ("anthropic", "anthropic-direct"):
        return AnthropicDirectProvider(**kwargs)
    raise ValueError(
        f"unknown provider {name!r}; expected one of: "
        "aoai, foundry, foundry-oai, foundry-anthropic, databricks, anthropic"
    )
