"""Prompt Library v2 — YAML-backed, persona-owned, inheritance-resolved.

Replaces the dataclass strings in prompt_library.py with a file-tree of
versioned YAML prompts under <repo>/prompts/{scope}/{persona}/{stage}/v{N}.yaml.

Inheritance walk at resolution time:
    run_overrides → team → persona → global

Every resolve() call returns (template, chain) where chain is the full
list of scopes considered with `matched: True` on the one that won.
The chain is written to LedgerEntry.prompt_resolution_path so every
decision is auditable: "which prompt produced this, what version,
what git_sha."

See openspec/changes/add-multi-persona-prompt-library/ for the design
+ WHEN/THEN scenarios this module is built to satisfy.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

_logger = logging.getLogger(__name__)

# Personas + stages — kept as data so the customer-engagement workshops can
# extend without code changes. The loader validates against these but doesn't
# reject unknown values (a new persona can ship before code knows about it).
KNOWN_PERSONAS = {"pm", "architect", "qa", "sre", "seceng", "compliance"}
KNOWN_STAGES = {
    "ingest", "assessor", "architect", "test_plan", "codegen", "review_scan",
}

PromptScope = Literal["global", "persona", "team"]
PromptStatus = Literal["draft", "published", "superseded"]


class PromptValidationError(Exception):
    """Raised when a prompt YAML file fails schema validation. Fail-fast:
    if the file tree is invalid, the orchestrator must not start (per
    openspec spec ADDED Requirement 1 / Scenario 2).
    """


class PromptFile(BaseModel):
    """One prompt YAML file's full content.

    Mirrors the frontmatter schema documented in
    openspec/changes/add-multi-persona-prompt-library/proposal.md.
    """
    prompt_id: str
    version: str = Field(pattern=r"^v\d+(\.\d+){0,2}$")
    status: PromptStatus
    scope: PromptScope
    owner_persona: str
    stage: str
    model_compat_notes: str = ""
    effective_from: str
    superseded_by: Optional[str] = None
    git_sha: str
    authored_by: str
    reason: str = ""
    template: str

    # Allow extras so future fields (e.g. cost_estimate, target_models)
    # don't require a schema migration before the file can load.
    # protected_namespaces=() silences pydantic's warning that
    # "model_compat_notes" looks like a model_-prefixed field — that's a
    # false positive; this field has nothing to do with pydantic models.
    model_config = {"extra": "allow", "protected_namespaces": ()}

    @field_validator("template")
    @classmethod
    def template_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("template must be a non-empty string")
        return v


@dataclass
class ResolutionStep:
    """One step in the inheritance walk. Used both for the resolver's
    return value and for what gets written into the ledger.
    """
    scope: PromptScope
    matched: bool
    prompt_id: Optional[str] = None
    version: Optional[str] = None
    git_sha: Optional[str] = None
    owner_persona: Optional[str] = None
    reason: Optional[str] = None  # e.g. "no file found at this scope"

    def as_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "matched": self.matched,
            "prompt_id": self.prompt_id,
            "version": self.version,
            "git_sha": self.git_sha,
            "owner_persona": self.owner_persona,
            "reason": self.reason,
        }


@dataclass
class ResolveResult:
    """What resolve() returns: the matched template + the full chain
    that was considered. Both go into the ledger entry."""
    template: str
    chain: list[ResolutionStep]

    @property
    def matched_step(self) -> Optional[ResolutionStep]:
        return next((s for s in self.chain if s.matched), None)

    def chain_as_list(self) -> list[dict[str, Any]]:
        return [s.as_dict() for s in self.chain]


@dataclass
class PromptCatalog:
    """In-memory index of all prompts loaded from disk.

    Indexed for the two lookup shapes the resolver and UI need:
      _by_scope_stage: (scope, team_or_persona_or_None, stage) -> list[PromptFile]
        — for resolve(): walks the chain
      _all: list[PromptFile]
        — for the UI's get_versions / get_prompts_owned_by
    """
    _all: list[PromptFile] = field(default_factory=list)
    _by_lookup: dict[tuple[str, Optional[str], str], list[PromptFile]] = field(
        default_factory=dict,
    )

    def add(self, prompt: PromptFile, key_team: Optional[str], key_persona: Optional[str]) -> None:
        """Insert a prompt into both indexes.

        key_team and key_persona are the routing keys for the chain walk:
          - global scope:  key_team=None, key_persona=None
          - persona scope: key_team=None, key_persona=<persona>
          - team scope:    key_team=<team>, key_persona=None
        """
        if prompt.scope == "global":
            lookup_key = ("global", None, prompt.stage)
        elif prompt.scope == "persona":
            lookup_key = ("persona", key_persona or prompt.owner_persona, prompt.stage)
        else:  # team
            if not key_team:
                raise PromptValidationError(
                    f"team-scoped prompt {prompt.prompt_id} requires a team key in its path",
                )
            lookup_key = ("team", key_team, prompt.stage)
        self._by_lookup.setdefault(lookup_key, []).append(prompt)
        self._all.append(prompt)

    def get_versions(self, stage: str, scope: str = "global",
                     team: Optional[str] = None,
                     persona: Optional[str] = None) -> list[PromptFile]:
        """Return all versions of a given prompt, newest first.

        Satisfies openspec spec Requirement: "PromptCatalog MUST be
        queryable by stage" with scenario "listing assessor versions
        returns the version history."
        """
        if scope == "global":
            key = ("global", None, stage)
        elif scope == "persona":
            key = ("persona", persona, stage)
        else:
            key = ("team", team, stage)
        versions = list(self._by_lookup.get(key, []))
        # Newest first: lexicographic descending on `version` works for v1, v2, v10
        # but not perfectly for semver — sort by parsed integer parts.
        def parse(v: str) -> tuple[int, ...]:
            return tuple(int(x) for x in v.lstrip("v").split("."))
        versions.sort(key=lambda p: parse(p.version), reverse=True)
        return versions

    def get_prompts_owned_by(self, persona: str) -> list[PromptFile]:
        """Return every prompt owned by the given persona, regardless of scope.

        Satisfies openspec spec Requirement: "PromptCatalog MUST be
        queryable by persona."
        """
        return [p for p in self._all if p.owner_persona == persona]

    def resolve(
        self,
        stage: str,
        model: Optional[str] = None,
        team: Optional[str] = None,
        persona_hint: Optional[str] = None,
    ) -> ResolveResult:
        """Walk team → persona → global, return matched template + full chain.

        Args:
            stage: canonical stage name (one of KNOWN_STAGES, soft-validated)
            model: model id (carried into ledger chain for audit; not used in
                lookup yet — that's a Phase 2 follow-on for per-model variants)
            team: team id; if None, skip team-scope lookup
            persona_hint: persona to check at persona scope; if None,
                infer from the global prompt's owner_persona

        Returns:
            ResolveResult with template (the winner's text) and chain
            (every scope considered, marked matched=True on the winner).

        Raises:
            PromptValidationError if no prompt at any scope matches (which
            means the global prompt is missing — that's a fatal misconfig,
            not a soft fallback).
        """
        chain: list[ResolutionStep] = []
        winner: Optional[PromptFile] = None

        # 1. team scope
        if team:
            team_versions = self.get_versions(stage, scope="team", team=team)
            published = [p for p in team_versions if p.status == "published"]
            if published:
                winner = published[0]
                chain.append(ResolutionStep(
                    scope="team", matched=True,
                    prompt_id=winner.prompt_id, version=winner.version,
                    git_sha=winner.git_sha, owner_persona=winner.owner_persona,
                ))
            else:
                chain.append(ResolutionStep(
                    scope="team", matched=False,
                    reason=f"no published team prompt for team={team} stage={stage}",
                ))
        else:
            chain.append(ResolutionStep(
                scope="team", matched=False, reason="no team provided",
            ))

        # 2. persona scope — only if team didn't match
        if winner is None:
            # Need a persona to check. Use the hint, or peek at global to
            # find the owning persona.
            persona = persona_hint
            if not persona:
                global_versions = self.get_versions(stage, scope="global")
                if global_versions:
                    persona = global_versions[0].owner_persona
            if persona:
                persona_versions = self.get_versions(stage, scope="persona", persona=persona)
                published = [p for p in persona_versions if p.status == "published"]
                if published:
                    winner = published[0]
                    chain.append(ResolutionStep(
                        scope="persona", matched=True,
                        prompt_id=winner.prompt_id, version=winner.version,
                        git_sha=winner.git_sha, owner_persona=winner.owner_persona,
                    ))
                else:
                    chain.append(ResolutionStep(
                        scope="persona", matched=False,
                        owner_persona=persona,
                        reason=f"no published persona prompt for persona={persona} stage={stage}",
                    ))
            else:
                chain.append(ResolutionStep(
                    scope="persona", matched=False,
                    reason="no persona to resolve against",
                ))
        else:
            chain.append(ResolutionStep(
                scope="persona", matched=False,
                reason="skipped — team scope matched",
            ))

        # 3. global scope — only if neither team nor persona matched
        if winner is None:
            global_versions = self.get_versions(stage, scope="global")
            published = [p for p in global_versions if p.status == "published"]
            if published:
                winner = published[0]
                chain.append(ResolutionStep(
                    scope="global", matched=True,
                    prompt_id=winner.prompt_id, version=winner.version,
                    git_sha=winner.git_sha, owner_persona=winner.owner_persona,
                ))
            else:
                chain.append(ResolutionStep(
                    scope="global", matched=False,
                    reason=f"no published global prompt for stage={stage}",
                ))
        else:
            chain.append(ResolutionStep(
                scope="global", matched=False,
                reason="skipped — earlier scope matched",
            ))

        if winner is None:
            raise PromptValidationError(
                f"no published prompt found at any scope for stage={stage}",
            )

        return ResolveResult(template=winner.template, chain=chain)


def load_prompts(root: Path) -> PromptCatalog:
    """Scan `<root>/{scope}/{...}/{stage}/v{N}.yaml`, load + validate all.

    Path structure:
      root/global/<stage>/v*.yaml
      root/persona/<persona>/<stage>/v*.yaml
      root/team/<team>/<stage>/v*.yaml

    Raises:
        PromptValidationError on any malformed YAML, missing required
        frontmatter field, or path/scope mismatch. The orchestrator MUST
        fail to start on this — half-loaded prompts are worse than no
        prompts (per openspec spec Requirement 1, scenario 2).
    """
    catalog = PromptCatalog()
    if not root.exists():
        raise PromptValidationError(
            f"prompts directory does not exist: {root}",
        )

    seen_files = 0
    for yaml_path in sorted(root.rglob("v*.yaml")):
        rel = yaml_path.relative_to(root)
        parts = rel.parts
        # Determine scope from path
        # global: ['global', '<stage>', 'v1.yaml']        -> 3 parts
        # persona: ['persona', '<persona>', '<stage>', 'v1.yaml']  -> 4 parts
        # team: ['team', '<team>', '<stage>', 'v1.yaml']  -> 4 parts
        if len(parts) == 3 and parts[0] == "global":
            scope_expected = "global"
            key_persona = None
            key_team = None
            stage_expected = parts[1]
        elif len(parts) == 4 and parts[0] == "persona":
            scope_expected = "persona"
            key_persona = parts[1]
            key_team = None
            stage_expected = parts[2]
        elif len(parts) == 4 and parts[0] == "team":
            scope_expected = "team"
            key_persona = None
            key_team = parts[1]
            stage_expected = parts[2]
        else:
            raise PromptValidationError(
                f"unexpected prompt file path layout: {rel} "
                f"(expected global/<stage>/vN.yaml, persona/<persona>/<stage>/vN.yaml, or team/<team>/<stage>/vN.yaml)",
            )

        try:
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise PromptValidationError(
                f"{yaml_path}: YAML parse error: {exc}",
            ) from exc

        try:
            prompt = PromptFile(**raw)
        except ValidationError as exc:
            raise PromptValidationError(
                f"{yaml_path}: frontmatter validation failed: {exc}",
            ) from exc

        # Cross-check declared frontmatter against path-inferred values
        if prompt.scope != scope_expected:
            raise PromptValidationError(
                f"{yaml_path}: frontmatter scope={prompt.scope!r} "
                f"contradicts path-implied scope={scope_expected!r}",
            )
        if prompt.stage != stage_expected:
            raise PromptValidationError(
                f"{yaml_path}: frontmatter stage={prompt.stage!r} "
                f"contradicts path-implied stage={stage_expected!r}",
            )

        catalog.add(prompt, key_team=key_team, key_persona=key_persona)
        seen_files += 1

    if seen_files == 0:
        raise PromptValidationError(
            f"prompts directory is empty: {root} "
            f"(expected at least global/<stage>/v1.yaml for each pipeline stage)",
        )

    _logger.info("Loaded %d prompt files from %s", seen_files, root)
    return catalog
