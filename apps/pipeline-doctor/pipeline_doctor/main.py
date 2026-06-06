"""Pipeline Doctor entrypoint — runs one detection + dispatch pass.

Usage:
    python -m pipeline_doctor [--mode dry-run|apply] [--team-id <id>]

Reads ledger entries from the configured Cosmos. Runs all five drift
detectors. For each signal, decides:
  - does this map to an auto-fix proposal? (within envelope)
  - if not, build a change proposal and open a PR

Designed to run as a Container Job on a cron schedule (every 1 hour).
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

import yaml
from ledger_core import LedgerClient, LedgerEntry

from .auto_fixer import AutoFixer
from .change_proposer import ChangeProposer
from .drift_detector import DriftDetector
from .envelope_validator import EnvelopeValidator, load_envelope, load_rules
from .models import (
    AutoFixProposal,
    BlastClass,
    ChangeProposal,
    DoctorRunSummary,
    DriftSignal,
    DriftSignalKind,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
_logger = logging.getLogger("pipeline_doctor")


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pipeline-doctor")
    parser.add_argument(
        "--mode",
        choices=["dry-run", "apply"],
        default=os.environ.get("DOCTOR_MODE", "dry-run"),
        help="dry-run prints what would happen; apply commits ledger writes + opens PRs",
    )
    parser.add_argument(
        "--team-id",
        default=os.environ.get("LEDGER_TEAM_ID", "team-demo"),
        help="team_id partition to scan (use '*' for cross-team)",
    )
    parser.add_argument(
        "--bundles-root",
        type=Path,
        default=Path(os.environ.get("STANDARDS_BUNDLES_ROOT", "standards-bundles")),
    )
    parser.add_argument(
        "--templates-dir",
        type=Path,
        default=Path(__file__).parent.parent / "templates",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=30,
        help="how many days of ledger to analyze",
    )
    parser.add_argument(
        "--target-repo",
        default=os.environ.get("STANDARDS_BUNDLES_REPO"),
        help='owner/repo for change-proposal PRs (e.g. "idanshimon/agentic-sdlc")',
    )
    return parser.parse_args(argv)


async def collect_entries(
    ledger: LedgerClient, team_id: str, window_days: int,
) -> List[LedgerEntry]:
    if team_id == "*":
        # Cross-team aggregate not implemented in v0.7; would require enable_cross_partition_query
        _logger.warning("cross-team aggregate not implemented; using team-demo")
        team_id = "team-demo"
    return await ledger.query_recent_for_team(team_id=team_id, limit=200)


def known_rule_ids(bundles_root: Path) -> List[str]:
    """Walk standards-bundles/, return all rule refs in '<dept>/<version>/<id>' form."""
    out: List[str] = []
    for dept_dir in sorted(bundles_root.iterdir()):
        if not dept_dir.is_dir() or dept_dir.name.startswith("."):
            continue
        for version_dir in sorted(dept_dir.iterdir()):
            rules_path = version_dir / "rules.yaml"
            if not rules_path.exists():
                continue
            with open(rules_path) as f:
                data = yaml.safe_load(f) or {}
            for rule in data.get("rules", []):
                rid = rule.get("id")
                if rid:
                    out.append(f"{dept_dir.name}/{version_dir.name}/{rid}")
    return out


def build_proposal_from_signal(
    signal: DriftSignal,
    bundles_root: Path,
) -> Optional[AutoFixProposal]:
    """Map a drift signal to an auto-fix proposal where applicable.

    Not every signal maps to an auto-fix:
      - phi_class_violation: NEVER auto-fix; always becomes a change proposal
      - bundle_rule_unused: NEVER auto-fix; tag for committee review
      - class_drift_unexpected: NEVER auto-fix; new class needs human input
      - autopilot_rejection_rate_high: maps to autopilot threshold tuning
      - cost_per_decision_climbing: maps to provider routing change
    """
    if signal.kind == DriftSignalKind.AUTOPILOT_REJECTION_RATE_HIGH:
        # Lower threshold by 0.03
        rule_id = "AUTOPILOT-THRESHOLD-AUTH" if signal.ambiguity_class == "auth-policy" else None
        if not rule_id:
            return None
        bundle_ref = f"finops/v0.1.0/{rule_id}"
        return AutoFixProposal(
            triggered_by=signal.id,
            bundle_ref=bundle_ref,
            rule_id=rule_id,
            field_path=f"{rule_id}.defaults.threshold",
            current_value=0.85,    # would be looked up from registry
            proposed_value=0.82,    # current - 0.03
            rationale=signal.description,
            expected_impact=(
                "Lower rejection rate by allowing borderline cases through; "
                "monitor for reverse drift over next 14 days."
            ),
        )
    return None


def build_change_proposal_from_signal(
    signal: DriftSignal, dept: str, blast: BlastClass,
) -> ChangeProposal:
    return ChangeProposal(
        triggered_by=signal.id,
        dept=dept,
        rule_id=signal.bundle_ref or "(unknown)",
        blast_class=blast,
        summary=f"Drift signal: {signal.kind.value} on {signal.bundle_ref or signal.ambiguity_class}",
        rationale=(
            f"Pipeline Doctor surfaced a {signal.kind.value} signal that does not "
            f"map to a bounded auto-fix. Requires committee review.\n\n"
            f"Description: {signal.description}\n"
            f"Sample size: {signal.sample_size}\n"
            f"Detected at: {signal.detected_at}"
        ),
        proposed_diff="<diff to be authored by reviewer>",
        drift_evidence=signal,
    )


async def run_doctor(args: argparse.Namespace) -> DoctorRunSummary:
    summary = DoctorRunSummary(dry_run=(args.mode == "dry-run"))

    cosmos_endpoint = os.environ.get("COSMOS_ENDPOINT")
    if not cosmos_endpoint:
        _logger.warning("COSMOS_ENDPOINT not set; running in offline mode (no real writes)")
        # In offline mode we bail with a clear error — real ledger access required.
        summary.errors.append("COSMOS_ENDPOINT not set")
        summary.finished_at = datetime.now(timezone.utc).isoformat()
        return summary

    ledger = LedgerClient(
        cosmos_endpoint=cosmos_endpoint,
        cosmos_db=os.environ.get("COSMOS_DB", "agentic-sdlc"),
    )

    try:
        entries = await collect_entries(ledger, args.team_id, args.window_days)
        _logger.info("collected %d ledger entries", len(entries))

        rule_ids = known_rule_ids(args.bundles_root)
        _logger.info("known rules: %d", len(rule_ids))

        detector = DriftDetector()
        signals = detector.detect(entries, bundle_rule_ids=rule_ids)
        summary.signals_detected = len(signals)
        _logger.info("detected %d drift signals", len(signals))

        # Lazy-load envelopes by dept
        envelope_cache: dict[str, EnvelopeValidator] = {}

        def get_validator(bundle_ref: str) -> Optional[EnvelopeValidator]:
            # bundle_ref like "finops/v0.1.0/AUTOPILOT-THRESHOLD-AUTH"
            parts = bundle_ref.split("/")
            if len(parts) < 3:
                return None
            dept, version = parts[0], parts[1]
            key = f"{dept}/{version}"
            if key not in envelope_cache:
                base = args.bundles_root / dept / version
                envelope_cache[key] = EnvelopeValidator(
                    envelope_yaml=load_envelope(str(base / "envelope.yaml")),
                    bundle_rules=load_rules(str(base / "rules.yaml")),
                )
            return envelope_cache[key]

        auto_fixer = AutoFixer(ledger, dry_run=args.mode == "dry-run")
        change_proposer = ChangeProposer(
            bundles_root=args.bundles_root,
            templates_dir=args.templates_dir,
            target_repo=args.target_repo,
            dry_run=args.mode == "dry-run",
        )

        for signal in signals:
            proposal = build_proposal_from_signal(signal, args.bundles_root)
            if proposal is not None:
                validator = get_validator(proposal.bundle_ref)
                if validator is None:
                    _logger.warning("no validator for %s", proposal.bundle_ref)
                    summary.errors.append(f"no validator for {proposal.bundle_ref}")
                    continue
                check = validator.validate(
                    proposal,
                    recent_fix_count_for_dept=0,  # would query ledger in real impl
                    precondition_state={
                        "drift_signal_present_for_days": 9,
                        "phi_class_not_high": True,
                    },
                )
                if check.allowed:
                    entry_id = await auto_fixer.apply(
                        proposal, check, team_id=args.team_id,
                    )
                    if entry_id:
                        summary.auto_fixes_applied += 1
                    else:
                        _logger.info("dry-run skipped apply for proposal %s", proposal.id)
                    continue
                else:
                    summary.auto_fixes_rejected += 1
                    _logger.info(
                        "envelope check failed for %s: %s",
                        proposal.id,
                        [v.reason for v in check.violations],
                    )

            # Either no auto-fix mapped, or envelope rejected → change proposal
            dept = (signal.bundle_ref or "architect/").split("/")[0]
            if dept not in {"architect", "security", "privacy", "finops"}:
                dept = "architect"
            blast = (
                BlastClass.HIGH if signal.kind == DriftSignalKind.PHI_CLASS_VIOLATION
                else BlastClass.MED if signal.kind == DriftSignalKind.CLASS_DRIFT_UNEXPECTED
                else BlastClass.LOW
            )
            cp = build_change_proposal_from_signal(signal, dept=dept, blast=blast)
            url = change_proposer.open_pr(cp)
            if url or args.mode == "dry-run":
                summary.change_proposals_opened += 1

    except Exception as e:
        _logger.exception("doctor run failed")
        summary.errors.append(str(e))
    finally:
        await ledger.close()
        summary.finished_at = datetime.now(timezone.utc).isoformat()

    return summary


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    summary = asyncio.run(run_doctor(args))
    print(json.dumps(summary.model_dump(), indent=2))
    return 0 if not summary.errors else 1


if __name__ == "__main__":
    sys.exit(main())
