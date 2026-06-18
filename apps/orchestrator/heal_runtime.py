"""Self-heal cowork — pluggable brain + executor (both paths, configurable).

The self-heal loop has two runtime-dependent roles, and per Idan's directive
we keep BOTH implementations of each, selected by config, never lock-in:

  BRAIN (diagnoses, proposes a heal, cites precedent):
    - "azure"  → Azure-native: a Foundry-registered agent / AOAI-via-APIM call.
                 The governance-grade default for the MSFT story.
    - "github" → GitHub Copilot SDK brain (the @github/copilot-sdk agentic loop).
    - "stub"   → deterministic, no model call. Runs end-to-end today; used for
                 the working MVP + tests + offline demo.

  EXECUTOR (lands the heal where the code lives):
    - "github" → GitHub Copilot coding agent: opens a real PR on the repo.
    - "azure"  → Azure-native executor: re-runs the stage in-orchestrator, or
                 opens the PR via the Azure DevOps / GitHub REST path with a
                 managed identity. Code surgery still lands as a PR.
    - "stub"   → deterministic, returns a synthetic PR/re-run ref. Working MVP.

Selection precedence mirrors config.py: python default < config.yaml < env var.
Env: HEAL_BRAIN=azure|github|stub, HEAL_EXECUTOR=github|azure|stub,
     HEAL_ACTIONS_ENABLED=true|false (feature flag; false → read-only).

The brain and executor are independent — you can run an Azure brain with a
GitHub executor, or vice versa. The ledger bridges them (heal_proposed from
the brain, heal_executed from the executor) so the handoff is auditable
regardless of the pairing.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional, Protocol, runtime_checkable

from .heal import (
    HealAction,
    HealActionType,
    HealExecution,
    HealProposal,
    HealTrigger,
)

_logger = logging.getLogger("orchestrator.heal_runtime")


# --- config (mirrors config.py Settings pattern) ------------------------------
def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip().lower()


@dataclass(frozen=True)
class HealSettings:
    brain: str            # azure | github | stub
    executor: str         # github | azure | stub
    actions_enabled: bool # master flag; false → read-only
    github_repo: str      # repo the GitHub executor opens PRs against

    @classmethod
    def from_env(cls) -> "HealSettings":
        return cls(
            brain=_env("HEAL_BRAIN", "stub"),
            executor=_env("HEAL_EXECUTOR", "stub"),
            actions_enabled=_env("HEAL_ACTIONS_ENABLED", "true") in ("1", "true", "yes", "on"),
            github_repo=os.getenv("HEAL_GITHUB_REPO", "idanshimon/agentic-sdlc"),
        )


heal_settings = HealSettings.from_env()


def reload_heal_settings() -> "HealSettings":
    """Re-read env. Tests use this after monkeypatching os.environ."""
    global heal_settings
    heal_settings = HealSettings.from_env()
    return heal_settings


# --- protocols ----------------------------------------------------------------
@runtime_checkable
class HealBrain(Protocol):
    """Diagnoses a failing run and proposes ONE heal action, citing precedent.

    Implementations MUST NOT execute anything — they only produce a proposal
    that flows to the validator and then to the human for approval.
    """
    name: str

    async def diagnose(
        self,
        *,
        run_id: str,
        team_id: str,
        trigger: HealTrigger,
        run_summary: dict,
        precedent: list[dict],
    ) -> HealProposal: ...


@runtime_checkable
class HealExecutor(Protocol):
    """Lands an APPROVED heal where the code lives. Returns a HealExecution
    carrying the result ref (a PR url for code heals, a re-run id, etc.).

    Implementations MUST NOT be invoked until the human has approved the
    proposal — that gate is enforced by the orchestrator endpoint, not here.
    """
    name: str

    async def execute(self, proposal: HealProposal) -> HealExecution: ...


# --- STUB brain + executor (the working MVP path; runs today) -----------------
class StubBrain:
    """Deterministic brain — no model call. Inspects the run summary and
    proposes the obvious heal. Good enough to prove the loop end-to-end and to
    run offline / in tests. The Azure + GitHub brains slot in behind the same
    protocol later without touching the endpoints.
    """
    name = "stub"

    async def diagnose(
        self, *, run_id: str, team_id: str, trigger: HealTrigger,
        run_summary: dict, precedent: list[dict],
    ) -> HealProposal:
        status = run_summary.get("status")
        stage = run_summary.get("current_stage") or "codegen"
        # Deterministic heuristic: a failed run gets a code heal on the stage it
        # died at; a gate-paused run gets a re-run proposal for the prior stage.
        if status == "failed":
            action = HealAction(
                action_type=HealActionType.ASSIGN_CODE_HEAL,
                summary=f"Failing {stage} stage — assign a code heal to open a PR fixing it.",
                stage=stage,
                payload={
                    "pr_title": f"heal: fix failing {stage} for run {run_id[:8]}",
                    "pr_body": (
                        f"Automated heal proposal for run `{run_id}` (team `{team_id}`).\n\n"
                        f"The `{stage}` stage failed. This PR addresses the failure.\n\n"
                        f"Cited precedent: {len(precedent)} prior heal(s)."
                    ),
                },
            )
            diagnosis = (
                f"Run {run_id[:8]} failed at the {stage} stage. "
                f"{'Found ' + str(len(precedent)) + ' similar prior heal(s).' if precedent else 'No prior precedent — first of its kind.'} "
                f"Recommended: assign a code heal that opens a PR."
            )
        else:
            action = HealAction(
                action_type=HealActionType.RERUN_STAGE,
                summary=f"Re-run the {stage} stage with the same inputs (idempotent).",
                stage=stage,
                payload={"rerun_stage": stage},
            )
            diagnosis = (
                f"Run {run_id[:8]} is paused at {stage}. "
                f"Recommended: re-run {stage} to clear a transient failure."
            )
        return HealProposal(
            run_id=run_id,
            team_id=team_id,
            trigger=trigger,
            action=action,
            precedent_refs=[p.get("id", "") for p in precedent if p.get("id")],
            diagnosis=diagnosis,
        )


class StubExecutor:
    """Deterministic executor — returns a synthetic but well-formed result ref.
    For ASSIGN_CODE_HEAL it returns a PR-shaped URL (never a bare commit, per
    spec). Lets the full loop + ledger chain run today without a live runtime.
    """
    name = "stub"

    async def execute(self, proposal: HealProposal) -> HealExecution:
        action = proposal.action
        if action.action_type in (HealActionType.ASSIGN_CODE_HEAL,
                                   HealActionType.REPROMPT_STAGE,
                                   HealActionType.BUMP_BUNDLE_RULE):
            # code/rule heals land as a PR
            pr_num = abs(hash(proposal.heal_id)) % 9000 + 1000
            return HealExecution(
                heal_id=proposal.heal_id,
                result_ref=f"https://github.com/{heal_settings.github_repo}/pull/{pr_num}",
                success=True,
                detail=f"[stub] {action.action_type.value} → synthetic PR #{pr_num}",
            )
        # rerun / autopilot heals land as a re-run reference
        return HealExecution(
            heal_id=proposal.heal_id,
            result_ref=f"rerun://{proposal.run_id}/{action.stage or 'unknown'}",
            success=True,
            detail=f"[stub] {action.action_type.value} dispatched",
        )


# --- GitHub Copilot coding-agent executor (real PR path) ----------------------
class GitHubExecutor:
    """Opens a real PR via the GitHub coding agent. In the MVP this shells to
    the `gh` CLI / GitHub REST to create a branch + PR (the coding-agent
    assignment is the production form). Falls back to a clear error if gh is not
    configured, rather than pretending success.
    """
    name = "github"

    async def execute(self, proposal: HealProposal) -> HealExecution:
        # Lazy import so the stub path has zero gh dependency.
        import asyncio
        action = proposal.action
        repo = heal_settings.github_repo
        title = action.payload.get("pr_title", f"heal: {action.summary[:60]}")
        body = action.payload.get("pr_body", proposal.diagnosis)
        # MVP: create an issue assigned to the coding agent (the documented way to
        # hand work to the GitHub Copilot coding agent). The agent opens the PR.
        # We create the issue via gh and return its URL; the executed entry is
        # updated to the PR when the agent reports back (future webhook).
        cmd = [
            "gh", "issue", "create", "--repo", repo,
            "--title", title, "--body", body + "\n\n/cc @github-copilot[bot] (heal executor)",
            "--label", "self-heal",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
            if proc.returncode != 0:
                return HealExecution(
                    heal_id=proposal.heal_id,
                    result_ref="",
                    success=False,
                    detail=f"gh issue create failed: {err.decode()[:200]}",
                )
            url = out.decode().strip().splitlines()[-1]
            return HealExecution(
                heal_id=proposal.heal_id, result_ref=url, success=True,
                detail="GitHub coding-agent issue opened; PR follows on agent completion.",
            )
        except FileNotFoundError:
            return HealExecution(
                heal_id=proposal.heal_id, result_ref="", success=False,
                detail="gh CLI not found; configure the GitHub executor or use HEAL_EXECUTOR=stub.",
            )


# --- Azure-native executor (managed-identity REST path) -----------------------
class AzureExecutor:
    """Azure-native executor. For rerun_stage it dispatches an in-orchestrator
    re-run (no external dependency). For code heals it opens a PR via the GitHub
    REST API using a managed-identity-fronted token (the Azure-governed path).

    MVP: the rerun path is real; the code-PR path returns a clear not-yet-wired
    signal so we never fake a PR url. This keeps the Azure executor honest until
    the MI token broker is configured.
    """
    name = "azure"

    async def execute(self, proposal: HealProposal) -> HealExecution:
        action = proposal.action
        if action.action_type == HealActionType.RERUN_STAGE:
            return HealExecution(
                heal_id=proposal.heal_id,
                result_ref=f"rerun://{proposal.run_id}/{action.stage or 'unknown'}",
                success=True,
                detail="[azure] in-orchestrator stage re-run dispatched",
            )
        return HealExecution(
            heal_id=proposal.heal_id, result_ref="", success=False,
            detail=(
                "[azure] code-heal PR path requires the managed-identity GitHub "
                "token broker (not yet configured). Use HEAL_EXECUTOR=github for "
                "code heals, or HEAL_EXECUTOR=stub for the offline demo."
            ),
        )


# --- factories (config-driven selection) --------------------------------------
def get_brain(name: Optional[str] = None) -> HealBrain:
    """Return the configured brain. `name` overrides config (used by tests)."""
    sel = (name or heal_settings.brain).lower()
    if sel == "stub":
        return StubBrain()
    if sel == "azure":
        # Azure-native brain not yet wired; fall back to stub with a warning so
        # the loop still runs. The protocol slot is reserved.
        _logger.warning("HEAL_BRAIN=azure not yet wired; using stub brain. Slot reserved.")
        return StubBrain()
    if sel == "github":
        _logger.warning("HEAL_BRAIN=github not yet wired; using stub brain. Slot reserved.")
        return StubBrain()
    _logger.warning("unknown HEAL_BRAIN=%r; using stub", sel)
    return StubBrain()


def get_executor(name: Optional[str] = None) -> HealExecutor:
    """Return the configured executor. `name` overrides config (used by tests)."""
    sel = (name or heal_settings.executor).lower()
    if sel == "stub":
        return StubExecutor()
    if sel == "github":
        return GitHubExecutor()
    if sel == "azure":
        return AzureExecutor()
    _logger.warning("unknown HEAL_EXECUTOR=%r; using stub", sel)
    return StubExecutor()
