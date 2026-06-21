"""Agent → bundle resolver.

Closes a real wiring gap (caught 2026-06-21): every agent under
`.github/agents/*.agent.md` declares `bundle_subscriptions:` (e.g. architect →
[architect, security]), and the UI faithfully renders those subscriptions — but
NO backend code read them. The pipeline wrote ledger entries with an empty
`bundle_refs`, so the agent→bundle relationship was display-only metadata, never
driving behaviour or showing up on decisions.

This module makes the relationship load-bearing: it parses the agent files once
and exposes the bundle subscriptions per agent / per stage, so the stage writers
can stamp `bundle_refs` on the ledger entry they emit. That makes "this decision
was governed by the architect + security bundles" a queryable fact on every
decision, not a label on a card.

Mapping note: stages map to agents by the `agent_name` the stage already passes
to `_call(...)` (assessor → "assessor", architect → "architect", etc.). The
agent file's `name:` frontmatter is the join key.
"""
from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_logger = logging.getLogger("orchestrator.agent_bundles")

# Repo root: this file is apps/orchestrator/agent_bundles.py → ../../ is root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_AGENTS_DIR = Path(os.environ.get("AGENTS_DIR", _REPO_ROOT / ".github" / "agents"))
_BUNDLES_DIR = Path(os.environ.get("BUNDLES_DIR", _REPO_ROOT / "standards-bundles"))


def _load_known_bundles() -> frozenset:
    """Bundle names that exist as standards-bundles/<dept>/ dirs.

    Validates parsed subscriptions — guards against prose placeholders
    ("all (read-only)") and inline-comment noise leaking into bundle_refs.
    """
    if not _BUNDLES_DIR.is_dir():
        return frozenset()
    return frozenset(
        p.name for p in _BUNDLES_DIR.iterdir()
        if p.is_dir() and not p.name.startswith(".")
    )


_KNOWN_BUNDLES = _load_known_bundles()

# Stage key (as used in _pipeline_stages.py / ledger entries) → agent file name.
# Some stages run multiple sub-agents (codegen → codegen-impl + codegen-tests);
# they share the codegen agent's bundle subscriptions.
_STAGE_TO_AGENT: Dict[str, str] = {
    "ingest": "assessor",          # ingest is light; assessor owns the early bundles
    "assessor": "assessor",
    "architect": "architect",
    "test_plan": "test-planner",
    "codegen": "codegen",
    "review_scan": "review-scan",
    "deliver": "codegen",
}


def _parse_frontmatter_bundles(text: str) -> tuple[Optional[str], List[str]]:
    """Extract (name, bundle_subscriptions) from an agent .md frontmatter block.

    Deliberately a small hand-parser rather than a YAML dep: the frontmatter is
    simple and we only need two keys. Returns (name, []) when subscriptions are
    absent, (None, []) when there's no frontmatter at all.
    """
    if not text.startswith("---"):
        return None, []
    # Grab the block between the first two '---' fences.
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, []
    fm = parts[1]

    name_match = re.search(r"^name:\s*(.+?)\s*$", fm, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else None

    bundles: List[str] = []
    # Find the 'bundle_subscriptions:' key, then collect following '- item' lines
    # until a non-indented / non-list line.
    lines = fm.splitlines()
    in_block = False
    for line in lines:
        if re.match(r"^bundle_subscriptions:\s*$", line):
            in_block = True
            continue
        if in_block:
            item = re.match(r"^\s*-\s*(.+?)\s*$", line)
            if item:
                # Strip inline '# comment' (e.g. "finops   # primary bundle")
                # and skip prose placeholders like "all (read-only)".
                val = item.group(1).split("#", 1)[0].strip()
                if val and val in _KNOWN_BUNDLES:
                    bundles.append(val)
            elif line.strip() and not line.startswith((" ", "\t")):
                break  # next top-level key
    return name, bundles


@lru_cache(maxsize=1)
def _agent_bundle_map() -> Dict[str, List[str]]:
    """Load { agent_name: [bundle, ...] } from .github/agents/*.agent.md.

    Cached: agent files are static at runtime (edits go through the config-write
    PR flow + redeploy). Call _agent_bundle_map.cache_clear() after a hot-reload.
    """
    result: Dict[str, List[str]] = {}
    if not _AGENTS_DIR.is_dir():
        _logger.warning("agents dir not found: %s", _AGENTS_DIR)
        return result
    for path in sorted(_AGENTS_DIR.glob("*.agent.md")):
        try:
            name, bundles = _parse_frontmatter_bundles(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            _logger.warning("failed to parse agent file %s: %s", path.name, exc)
            continue
        # Fall back to the filename stem (architect.agent.md → architect) when
        # the frontmatter omits an explicit name.
        key = name or path.name.replace(".agent.md", "")
        result[key] = bundles
    return result


def bundles_for_agent(agent_name: str) -> List[str]:
    """Bundle subscriptions declared by an agent, or [] if unknown."""
    return list(_agent_bundle_map().get(agent_name, []))


def bundles_for_stage(stage: str) -> List[str]:
    """Bundle subscriptions in effect for a pipeline stage.

    This is the function the stage writers call to stamp `bundle_refs` on the
    ledger entry they emit. Returns [] for unmapped/unknown stages so callers
    can stamp unconditionally without guarding.
    """
    agent = _STAGE_TO_AGENT.get(stage)
    if not agent:
        return []
    return bundles_for_agent(agent)


def reload_agent_bundles() -> None:
    """Drop the cache so the next lookup re-reads the agent files (hot-reload)."""
    _agent_bundle_map.cache_clear()
