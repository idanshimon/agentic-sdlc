"""Change proposer — opens PRs on standards-bundles/<dept> with ADR drafts.

Used when an auto-fix proposal does NOT pass envelope validation, OR when
the drift signal warrants a rule change rather than a tuning.

Output: a real PR opened via `gh` CLI on the configured target repo,
labeled per blast class, reviewers assigned per dept's reviewers.yaml.
"""
from __future__ import annotations
import json
import logging
import subprocess
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader

from .models import BlastClass, ChangeProposal, DriftSignal

_logger = logging.getLogger("pipeline_doctor.change_proposer")


class ChangeProposer:
    """Renders ADR + opens PR on standards-bundles repo."""

    def __init__(
        self,
        bundles_root: Path,
        templates_dir: Path,
        target_repo: Optional[str] = None,
        dry_run: bool = False,
    ):
        """
        Args:
            bundles_root: filesystem path to standards-bundles/
            templates_dir: filesystem path to apps/pipeline-doctor/templates/
            target_repo: github "<owner>/<repo>" to open PRs on; None = current dir
            dry_run: if True, render the ADR but don't run gh CLI
        """
        self._bundles_root = bundles_root
        self._templates_dir = templates_dir
        self._target_repo = target_repo
        self._dry_run = dry_run
        self._jinja = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_adr(self, proposal: ChangeProposal) -> str:
        """Render the ADR markdown for a change proposal."""
        template = self._jinja.get_template("adr.md.j2")
        return template.render(
            id=proposal.id[:8],
            dept=proposal.dept,
            rule_id=proposal.rule_id,
            blast_class=proposal.blast_class.value,
            summary=proposal.summary,
            rationale=proposal.rationale,
            proposed_diff=proposal.proposed_diff,
            drift=proposal.drift_evidence,
            suggested_reviewers=proposal.suggested_reviewers,
        )

    def load_reviewers(self, dept: str, version: str) -> Dict[str, Any]:
        path = self._bundles_root / dept / version / "reviewers.yaml"
        if not path.exists():
            return {"blast_classes": {}, "people": {}}
        with open(path) as f:
            return yaml.safe_load(f) or {}

    def required_reviewers(
        self, dept: str, version: str, blast_class: BlastClass,
    ) -> Dict[str, Any]:
        """Resolve people emails for a given blast class."""
        roster = self.load_reviewers(dept, version)
        bc = roster.get("blast_classes", {}).get(blast_class.value, {})
        people = roster.get("people", {})
        out = {
            "required_approvers": bc.get("required_approvers", 1),
            "must_include_roles": bc.get("must_include_roles", []),
            "can_include_roles": bc.get("can_include_roles", []),
            "emails_must": [],
            "emails_can": [],
        }
        for role in out["must_include_roles"]:
            out["emails_must"].extend(people.get(role, []))
        for role in out["can_include_roles"]:
            out["emails_can"].extend(people.get(role, []))
        return out

    def open_pr(self, proposal: ChangeProposal, version: str = "v0.1.0") -> Optional[str]:
        """Open a PR on the target repo. Returns the PR URL on success.

        Side effects:
        - Renders ADR
        - Creates a branch named `pipeline-doctor/<id-prefix>`
        - Writes the proposed_diff (assumed to be a single-file diff for v0.7)
        - Commits + pushes
        - Calls `gh pr create` with title/body/labels/reviewers
        """
        adr_md = self.render_adr(proposal)
        reviewers = self.required_reviewers(proposal.dept, version, proposal.blast_class)
        proposal.suggested_reviewers = reviewers["emails_must"] + reviewers["emails_can"]

        title = f"[{proposal.blast_class.value}] Doctor proposes {proposal.rule_id} change: {proposal.summary}"
        body = adr_md
        labels = [
            "pipeline-doctor",
            "standards-change",
            f"blast/{proposal.blast_class.value}",
            f"dept/{proposal.dept}",
        ]

        if self._dry_run:
            _logger.info("DRY-RUN: would open PR title=%r", title)
            _logger.info("DRY-RUN: ADR length=%d chars", len(adr_md))
            _logger.info("DRY-RUN: reviewers=%s", proposal.suggested_reviewers)
            _logger.info("DRY-RUN: labels=%s", labels)
            return None

        # Real PR open via gh CLI
        try:
            return self._gh_pr_create(proposal, title, body, labels, reviewers)
        except subprocess.CalledProcessError as e:
            _logger.error("gh pr create failed: %s", e.stderr)
            return None

    def _gh_pr_create(
        self,
        proposal: ChangeProposal,
        title: str,
        body: str,
        labels: list[str],
        reviewers: Dict[str, Any],
    ) -> Optional[str]:
        """Invoke `gh pr create`. Assumes branch + diff have been applied."""
        cmd = ["gh", "pr", "create", "--title", title, "--body", body]
        for lab in labels:
            cmd.extend(["--label", lab])
        for email in reviewers["emails_must"][:5]:  # GH limits reviewer count
            cmd.extend(["--reviewer", email])
        if self._target_repo:
            cmd.extend(["--repo", self._target_repo])
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        url = result.stdout.strip()
        _logger.info("opened PR: %s", url)
        return url
