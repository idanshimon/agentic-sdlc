"""Tests for change_proposer ADR rendering — pure-function, no I/O needed."""
from pathlib import Path

import pytest
from pipeline_doctor.change_proposer import ChangeProposer
from pipeline_doctor.models import (
    BlastClass, ChangeProposal, DriftSignal, DriftSignalKind,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
BUNDLES_ROOT = REPO_ROOT / "standards-bundles"
TEMPLATES_DIR = REPO_ROOT / "apps" / "pipeline-doctor" / "templates"


@pytest.fixture
def proposer():
    return ChangeProposer(
        bundles_root=BUNDLES_ROOT,
        templates_dir=TEMPLATES_DIR,
        target_repo=None,
        dry_run=True,
    )


@pytest.fixture
def sample_signal():
    return DriftSignal(
        kind=DriftSignalKind.CLASS_DRIFT_UNEXPECTED,
        ambiguity_class="naming-convention",
        metric_value=8.5,
        metric_baseline=5.0,
        sample_size=12,
        description="Class 'naming-convention' = 8.5% with zero precedent_refs",
    )


@pytest.fixture
def sample_proposal(sample_signal):
    return ChangeProposal(
        triggered_by=sample_signal.id,
        dept="architect",
        rule_id="NAMING-CONVENTION-X",
        blast_class=BlastClass.MED,
        summary="add NAMING-CONVENTION-X rule for unprecedented class",
        rationale="Drift signal indicates new class needs explicit rule",
        proposed_diff="<diff to be authored>",
        drift_evidence=sample_signal,
    )


def test_render_adr_includes_summary(proposer, sample_proposal):
    md = proposer.render_adr(sample_proposal)
    assert sample_proposal.summary in md
    assert "Pipeline Doctor" in md
    assert sample_proposal.blast_class.value in md
    assert "ADR-" in md


def test_render_adr_includes_drift_evidence(proposer, sample_proposal):
    md = proposer.render_adr(sample_proposal)
    assert "naming-convention" in md
    assert "12" in md  # sample size
    assert "8.5" in md  # metric value


def test_render_adr_includes_proposed_diff(proposer, sample_proposal):
    sample_proposal.proposed_diff = "+ rule_id: NEW-RULE\n+ severity: WARN"
    md = proposer.render_adr(sample_proposal)
    assert "NEW-RULE" in md


def test_load_reviewers_for_security_high():
    p = ChangeProposer(BUNDLES_ROOT, TEMPLATES_DIR, dry_run=True)
    reqs = p.required_reviewers("security", "v0.1.0", BlastClass.HIGH)
    assert reqs["required_approvers"] == 3
    # security HIGH must include security_lead + privacy_dpo
    assert "security_lead" in reqs["must_include_roles"]
    assert "privacy_dpo" in reqs["must_include_roles"]
    # emails resolved from people: map
    assert any("security-lead" in e for e in reqs["emails_must"])


def test_load_reviewers_for_finops_low():
    p = ChangeProposer(BUNDLES_ROOT, TEMPLATES_DIR, dry_run=True)
    reqs = p.required_reviewers("finops", "v0.1.0", BlastClass.LOW)
    assert reqs["required_approvers"] == 1
    assert "finops_lead" in reqs["must_include_roles"]


def test_dry_run_does_not_call_gh(proposer, sample_proposal):
    """In dry-run mode, open_pr returns None and does not call gh CLI."""
    result = proposer.open_pr(sample_proposal, version="v0.1.0")
    assert result is None
    # If gh CLI were called and missing it would raise; dry_run prevents that.
