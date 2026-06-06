"""ledger_core — shared library for the Decision Ledger schema and Cosmos client.

Used by:
  - apps/orchestrator (writes runtime entries)
  - apps/pipeline-doctor (reads ledger, writes auto-fix runtime entries)
  - apps/decision-ledger-mcp (exposes ledger via MCP tools)
"""
from .models import (
    LedgerEntry,
    Actor,
    ReviewerAttribution,
    CanaryMetrics,
    EntryType,
    BlastClass,
    PHIClass,
    RuntimeKind,
    MetaKind,
    AmbiguityClass,
    DecisionKind,
    LedgerStatus,
    INVARIANT_CLASSES,
    is_phi_change,
    has_high_blast,
    from_legacy_v06_dict,
)
from .cosmos import LedgerClient, InvariantWriteBlocked

__all__ = [
    "LedgerEntry",
    "Actor",
    "ReviewerAttribution",
    "CanaryMetrics",
    "EntryType",
    "BlastClass",
    "PHIClass",
    "RuntimeKind",
    "MetaKind",
    "AmbiguityClass",
    "DecisionKind",
    "LedgerStatus",
    "INVARIANT_CLASSES",
    "is_phi_change",
    "has_high_blast",
    "from_legacy_v06_dict",
    "LedgerClient",
    "InvariantWriteBlocked",
]

__version__ = "0.7.0"
