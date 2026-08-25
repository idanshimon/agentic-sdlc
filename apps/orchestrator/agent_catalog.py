"""Agent catalog — governed view over `.github/agents/*.agent.md`.

The prompt library governs the PIPELINE lane: prompts live as versioned YAML
under `prompts/`, a resolver walks team → persona → global, and the chain is
pinned onto every ledger entry.

This module is the equivalent for the AGENT HQ lane. The seven custom agents in
`.github/agents/` each carry a markdown body that IS a system prompt — hard
rules, output shapes, bundle citations — and before `govern-agent-lane-prompts`
they carried no `version`, no `status`, no `owner_persona`, and no binding to
the YAML catalog. Two prompt surfaces in one repo, one governance claim, and
only one of them governed.

Design (see openspec/changes/govern-agent-lane-prompts/proposal.md):

  - Governance frontmatter mirrors `PromptFile`: prompt_id, version, status,
    owner_persona, git_sha, authored_by, reason, prompt_ref.
  - `prompt_ref` binds an agent to a YAML prompt. The shared instruction block
    in the agent body is GENERATED from that YAML between explicit markers, so
    the YAML stays the single source of truth and the agent body is derived.
  - Agents with no pipeline counterpart (pipeline-doctor, standards-change,
    review-loop-controller) carry `prompt_ref: null` and are governed by their
    own frontmatter alone.

Read-only over the filesystem, same as the prompt catalog. Editing goes through
`POST /api/config/agents/save`, which opens a PR — never an in-place write.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

_logger = logging.getLogger(__name__)

# Markers delimiting the block generated from the referenced prompt YAML.
# Kept as HTML comments so they render invisibly in the agent markdown.
GENERATED_BEGIN_RE = re.compile(
    r"<!--\s*BEGIN GENERATED FROM\s+(?P<source>[^\s]+)\s*(?:—|--)?[^>]*-->",
)
GENERATED_END = "<!-- END GENERATED -->"

AgentStatus = ("draft", "published", "superseded")


class AgentValidationError(Exception):
    """Raised when an agent file fails schema validation.

    Unlike the prompt loader, this is NOT fail-fast at startup: a malformed
    agent file must not take the orchestrator down, because agent files are
    consumed by Copilot runtimes rather than by the pipeline. It surfaces as
    an HTTP error on the catalog endpoints and as a CI failure in the
    agent-governance workflow.
    """


class AgentFile(BaseModel):
    """One `.agent.md` file's frontmatter.

    Runtime fields (tools, preferred_models, bundle_subscriptions,
    ledger_writes) come from the original agent format. Governance fields
    (prompt_id .. prompt_ref) are added by govern-agent-lane-prompts.
    """

    # --- runtime (pre-existing) ---
    name: str
    description: str = ""
    tools: list[str] = Field(default_factory=list)
    preferred_models: list[str] = Field(default_factory=list)
    bundle_subscriptions: list[str] = Field(default_factory=list)
    ledger_writes: list[Any] = Field(default_factory=list)

    # --- governance (new) ---
    prompt_id: str
    version: str = Field(pattern=r"^v\d+(\.\d+){0,2}$")
    status: str
    owner_persona: str
    git_sha: str = ""
    authored_by: str = ""
    reason: str = ""
    # None is meaningful: "this agent has no pipeline counterpart", distinct
    # from a dangling reference, which is a validation failure.
    prompt_ref: Optional[str] = None

    model_config = {"extra": "allow", "protected_namespaces": ()}

    @field_validator("status")
    @classmethod
    def status_known(cls, v: str) -> str:
        if v not in AgentStatus:
            raise ValueError(
                f"status must be one of {AgentStatus}, got {v!r}",
            )
        return v


@dataclass
class AgentEntry:
    """A parsed agent file: frontmatter + body + generated-block state."""

    meta: AgentFile
    body: str
    path: Path
    generated_source: Optional[str] = None   # e.g. "prompts/global/assessor/v1.yaml"
    generated_block: Optional[str] = None

    @property
    def has_generated_block(self) -> bool:
        return self.generated_block is not None

    def summary(self) -> dict[str, Any]:
        """List-view shape. Ships body_chars, not the body — one agent body is
        ~3KB and a 7-agent catalog would otherwise be 20KB+ per request."""
        return {
            "name": self.meta.name,
            "prompt_id": self.meta.prompt_id,
            "version": self.meta.version,
            "status": self.meta.status,
            "owner_persona": self.meta.owner_persona,
            "prompt_ref": self.meta.prompt_ref,
            "git_sha": self.meta.git_sha,
            "authored_by": self.meta.authored_by,
            "reason": self.meta.reason,
            "tools": self.meta.tools,
            "preferred_models": self.meta.preferred_models,
            "bundle_subscriptions": self.meta.bundle_subscriptions,
            "ledger_writes": [str(w) for w in self.meta.ledger_writes],
            "description": self.meta.description.strip(),
            "body_chars": len(self.body),
            "has_generated_block": self.has_generated_block,
            "generated_source": self.generated_source,
            "path": str(self.path.name),
        }

    def detail(self) -> dict[str, Any]:
        """Detail-view shape: everything in summary plus the full body."""
        out = self.summary()
        out["body"] = self.body
        out["generated_block"] = self.generated_block
        return out


@dataclass
class AgentCatalog:
    """In-memory index of every governed agent file."""

    _all: list[AgentEntry] = field(default_factory=list)

    def add(self, entry: AgentEntry) -> None:
        self._all.append(entry)

    def all(self) -> list[AgentEntry]:
        """Public iteration. Deliberately a method, not a bare attribute:
        the prompt catalog's endpoint reaches into `catalog._all` directly,
        which silently breaks if the internal shape changes."""
        return list(self._all)

    def get(self, name: str) -> Optional[AgentEntry]:
        return next((e for e in self._all if e.meta.name == name), None)

    def by_persona(self) -> dict[str, list[dict[str, Any]]]:
        out: dict[str, list[dict[str, Any]]] = {}
        for e in self._all:
            out.setdefault(e.meta.owner_persona, []).append(e.summary())
        return out


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split `---\\n<yaml>\\n---\\n<body>` into (frontmatter, body).

    Raises AgentValidationError when the file has no frontmatter block at all —
    that is a malformed agent file, not an agent with empty metadata.
    """
    m = re.match(r"^---\n(?P<fm>.*?)\n---\n(?P<body>.*)$", text, re.S)
    if not m:
        raise AgentValidationError("file has no YAML frontmatter block")
    try:
        fm = yaml.safe_load(m.group("fm")) or {}
    except yaml.YAMLError as exc:
        raise AgentValidationError(f"frontmatter YAML parse error: {exc}") from exc
    if not isinstance(fm, dict):
        raise AgentValidationError("frontmatter must be a YAML mapping")
    return fm, m.group("body")


def extract_generated_block(body: str) -> tuple[Optional[str], Optional[str]]:
    """Return (source_path, block_content) for the generated section, if present.

    Returns (None, None) when the body carries no generated markers — valid for
    agents with `prompt_ref: null`.
    """
    begin = GENERATED_BEGIN_RE.search(body)
    if not begin:
        return None, None
    start = begin.end()
    end_idx = body.find(GENERATED_END, start)
    if end_idx == -1:
        raise AgentValidationError(
            "generated block has a BEGIN marker with no matching END marker",
        )
    return begin.group("source"), body[start:end_idx].strip("\n")


def _agents_root() -> Path:
    """Where to look for .github/agents/. Mirrors _prompts_root()'s strategy.

    Order:
      1. AGENTS_ROOT env var (test fixtures)
      2. /app/.github/agents (production container layout)
      3. <repo_root>/.github/agents (developer laptop)
    """
    env = os.environ.get("AGENTS_ROOT")
    if env:
        return Path(env)
    container = Path("/app/.github/agents")
    if container.is_dir():
        return container
    here = Path(__file__).resolve()
    for parent in [here.parent.parent.parent, here.parent.parent]:
        candidate = parent / ".github" / "agents"
        if candidate.is_dir():
            return candidate
    return Path(".github/agents")


def load_agents(root: Optional[Path] = None) -> AgentCatalog:
    """Scan `<root>/*.agent.md`, parse + validate all.

    Unlike load_prompts(), a single malformed file does not abort the whole
    load — it is recorded and skipped, so one bad agent file cannot blank the
    catalog endpoint for the other six. CI is where a malformed agent file
    hard-fails.
    """
    root = root or _agents_root()
    catalog = AgentCatalog()
    if not root.is_dir():
        raise AgentValidationError(f"agents directory does not exist: {root}")

    for path in sorted(root.glob("*.agent.md")):
        try:
            fm, body = split_frontmatter(path.read_text(encoding="utf-8"))
            meta = AgentFile(**fm)
            source, block = extract_generated_block(body)
        except AgentValidationError as exc:
            _logger.warning("skipping malformed agent file %s: %s", path.name, exc)
            continue
        except ValidationError as exc:
            _logger.warning(
                "skipping agent file %s: frontmatter validation failed: %s",
                path.name, exc,
            )
            continue

        catalog.add(AgentEntry(
            meta=meta, body=body, path=path,
            generated_source=source, generated_block=block,
        ))

    _logger.info("Loaded %d agent files from %s", len(catalog.all()), root)
    return catalog


# ---------------------------------------------------------------------------
# Lazily-loaded singleton, same pattern as the prompt catalog.
# ---------------------------------------------------------------------------

_catalog: AgentCatalog | None = None


def get_agent_catalog() -> AgentCatalog:
    global _catalog
    if _catalog is None:
        _catalog = load_agents()
    return _catalog


def reset_agent_catalog() -> None:
    """Force the next get_agent_catalog() to re-read from disk. Used by
    POST /api/config/reload and by tests."""
    global _catalog
    _catalog = None
