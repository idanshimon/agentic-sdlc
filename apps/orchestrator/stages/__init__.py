"""Pipeline stages dispatcher.

The deliver stage dispatches on `config.deliver_provider`:
  - "github" (default): deliver_github.py — opens a PR on a GH repo
  - "ado":              deliver_ado.py — opens an ADO PR (legacy v0.6 path)

Per-team override via `config.delivery_overrides[team_id].provider`.
"""
from typing import Any

from .deliver_github import deliver_to_github
from .deliver_ado import deliver_to_ado


def get_deliver_fn(provider: str):
    """Return the deliver function for the given provider name."""
    if provider == "github":
        return deliver_to_github
    if provider == "ado":
        return deliver_to_ado
    raise ValueError(f"Unknown deliver_provider: {provider!r}")


__all__ = ["get_deliver_fn", "deliver_to_github", "deliver_to_ado"]
