"""Pipeline stages dispatcher.

The deliver stage dispatches on `config.deliver_provider`:
  - "github" (default): deliver_github.py — opens a PR on a GH repo
  - "ado":              deliver_ado.py — opens an ADO PR (legacy v0.6 path)

Per-team override via `config.delivery_overrides[team_id].provider`.

This package also re-exports the seven legacy stage functions from
`apps/orchestrator/_pipeline_stages.py` so `main.py` can keep its
`from .stages import stage_architect, ...` form. v0.6 had a single
`stages.py` module; v0.7 split delivery into a sub-package while
leaving the other six stages in the legacy module.
"""
from typing import Any

from .deliver_github import deliver_to_github
from .deliver_ado import deliver_to_ado

# Re-export legacy stage functions so `from orchestrator.stages import stage_X` keeps working.
from .._pipeline_stages import (  # noqa: F401  (re-export)
    stage_architect,
    stage_assessor,
    stage_codegen,
    stage_deliver,
    stage_ingest,
    stage_review_scan,
    stage_test_plan,
)


def get_deliver_fn(provider: str):
    """Return the deliver function for the given provider name."""
    if provider == "github":
        return deliver_to_github
    if provider == "ado":
        return deliver_to_ado
    raise ValueError(f"Unknown deliver_provider: {provider!r}")


__all__ = [
    "get_deliver_fn",
    "deliver_to_github",
    "deliver_to_ado",
    "stage_architect",
    "stage_assessor",
    "stage_codegen",
    "stage_deliver",
    "stage_ingest",
    "stage_review_scan",
    "stage_test_plan",
]
