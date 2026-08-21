"""Work-item provenance — the pipeline's governed entrance.

Part of `add-enterprise-integrations-plane`. A run's PRD is usually downstream of
a planning system of record (Aha!, Jira, Azure Boards): the PRD is a rendering of
an idea/epic/story. Because the pipeline never recorded WHICH work item a run came
from, the ledger could not answer the audit question one hop upstream:

    planning work item -> run -> stage decisions -> delivered PR

This module normalizes that reference. Two hard rules from the spec:

  1. **Optional and non-blocking.** No provenance == today's behaviour exactly.
     A configured tracker that cannot resolve the ref does NOT fail the run.
  2. **Never imply verification we did not perform.** A reference we did not
     fetch is `claimed`, not `verified`. Only a real successful resolve may set
     `verified`; a resolve that cannot be attempted is `unverifiable` with a
     reason.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .integrations import Integration, IntegrationsRegistry, KIND_PLANNING_TRACKER

_logger = logging.getLogger("orchestrator.work_items")

Verification = Literal["claimed", "verified", "unverifiable"]

# Conservative: a work-item ref is an opaque short token from an external system.
# We neither invent structure nor let arbitrary text through into the ledger.
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-/#]{0,127}$")

ITEM_TYPES = ("idea", "epic", "story", "task", "feature", "bug", "unknown")


class WorkItem(BaseModel):
    """The normalized record shape every planning provider returns.

    One shape across Aha!/Jira/Azure Boards/generic is the whole point of the
    provider seam: adding a provider must not change any consumer.
    """

    id: str
    item_type: str = "unknown"
    title: str = ""
    body: str = ""          # usable as PRD input
    url: str = ""


class WorkItemRef(BaseModel):
    """Provenance stamped on a run and on every ledger entry that run writes."""

    source_system: str = ""            # integration id or provider name as submitted
    source_ref: str = ""               # the work-item id in that system
    item_type: str = "unknown"
    title: str = ""
    url: str = ""
    verification: Verification = "claimed"
    reason: str = ""                   # why unverifiable / why verification failed

    @property
    def is_present(self) -> bool:
        return bool(self.source_ref)

    def summary(self) -> str:
        if not self.is_present:
            return ""
        sys_part = self.source_system or "unknown-system"
        return f"{sys_part}:{self.source_ref}"


def normalize_ref(
    source_system: Optional[str],
    source_ref: Optional[str],
    *,
    registry: Optional[IntegrationsRegistry] = None,
) -> Optional[WorkItemRef]:
    """Turn raw intake fields into a WorkItemRef, or None when absent.

    Returns None when no ref was supplied — the caller then behaves exactly as
    before this capability existed. Never raises on bad input: a malformed ref
    becomes an `unverifiable` reference carrying the reason, because refusing a
    run over a planning-system typo would make the governed entrance a new
    outage surface.
    """
    ref = (source_ref or "").strip()
    if not ref:
        return None

    system = (source_system or "").strip()

    if not _REF_RE.match(ref):
        return WorkItemRef(
            source_system=system,
            source_ref=ref[:128],
            verification="unverifiable",
            reason="work-item reference is not a well-formed external identifier",
        )

    integration: Optional[Integration] = None
    if registry is not None and registry.loaded:
        integration = registry.planning_tracker(system)

    if integration is None:
        # Declared by the submitter, but this instance has no configured tracker
        # to check it against. That is a CLAIM. Saying anything stronger would be
        # asserting a validation we never performed.
        reason = (
            "no planning-tracker integration configured for this source system"
            if system
            else "no source system named and no unique planning tracker configured"
        )
        return WorkItemRef(
            source_system=system,
            source_ref=ref,
            verification="claimed",
            reason=reason,
        )

    # A configured tracker gives us a URL template, so we can at least render a
    # deep link. Rendering a link is NOT verification — we have not fetched it.
    return WorkItemRef(
        source_system=integration.id or integration.provider,
        source_ref=ref,
        url=integration.resolve_item_url(ref),
        verification="claimed",
        reason="reference recorded from intake; not fetched from the planning system",
    )


def apply_resolution(
    ref: WorkItemRef,
    item: Optional[WorkItem],
    *,
    error: str = "",
) -> WorkItemRef:
    """Fold a resolve() outcome into the reference.

    Success -> `verified` with the fetched title/type/url.
    Failure -> stays unverified with the reason. NEVER raises: planning-system
    unavailability must not fail a run (spec scenario).
    """
    if item is not None:
        return ref.model_copy(
            update={
                "item_type": item.item_type or ref.item_type,
                "title": item.title or ref.title,
                "url": item.url or ref.url,
                "verification": "verified",
                "reason": "",
            }
        )
    return ref.model_copy(
        update={
            "verification": "unverifiable",
            "reason": error or "planning system did not resolve the reference",
        }
    )


def ledger_fields(ref: Optional[WorkItemRef]) -> dict[str, Any]:
    """The dict merged into a LedgerEntry write. Empty when there's no provenance,
    so entries for runs without a work item are byte-identical to today's."""
    if ref is None or not ref.is_present:
        return {}
    return {"work_item": ref.model_dump()}
