"""ADO deliver stage — legacy v0.6 path. Opt-in via config.deliver_provider="ado".

This is a placeholder that calls the legacy v0.6 implementation if available.
The HCA workshop deployment used this path; v0.7 demo defaults to GitHub.
"""
from __future__ import annotations
import logging
from typing import Any, Dict

from ..models import RunState

_logger = logging.getLogger("orchestrator.stages.deliver_ado")


async def deliver_to_ado(
    run: RunState,
    config: Any,
    ledger_client: Any = None,
) -> Dict[str, Any]:
    """Legacy ADO deliver path.

    v0.7 placeholder: the v0.6 deliver-to-ADO implementation is not ported here.
    Customers who need ADO can either:
      - Pin to v0.6 (idanshimon/agentic-sdlc-reference HEAD e04ce0a)
      - Author their own ADO deliver against this signature

    This function exists so the dispatcher in __init__.py has a valid target
    and the config flag works.
    """
    _logger.warning(
        "deliver_to_ado called but v0.7 reference does not implement the ADO path. "
        "Switch to config.deliver_provider=\"github\" or pin to v0.6."
    )
    return {
        "pr_url": None,
        "branch": None,
        "gh_audit_xref": None,
        "error": "deliver_provider=ado not implemented in v0.7 reference",
    }
