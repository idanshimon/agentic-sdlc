"""Drift detector — reads ledger entries, surfaces 5 signal types.

Pure analysis, no I/O on the ledger itself (caller fetches entries first).
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, List, Optional

from ledger_core import LedgerEntry

from .models import DriftSignal, DriftSignalKind


class DriftDetector:
    """Pure-function drift detection over a window of ledger entries."""

    def __init__(
        self,
        rejection_threshold_pct: float = 25.0,
        rejection_window_days: int = 7,
        cost_baseline_window_days: int = 30,
        cost_climb_multiplier: float = 1.5,
        class_drift_threshold_pct: float = 5.0,
        unused_rule_window_days: int = 30,
    ):
        self._rejection_threshold_pct = rejection_threshold_pct
        self._rejection_window = timedelta(days=rejection_window_days)
        self._cost_baseline_window = timedelta(days=cost_baseline_window_days)
        self._cost_climb_multiplier = cost_climb_multiplier
        self._class_drift_threshold_pct = class_drift_threshold_pct
        self._unused_rule_window = timedelta(days=unused_rule_window_days)

    def detect(
        self,
        recent_entries: List[LedgerEntry],
        bundle_rule_ids: Optional[List[str]] = None,
        now: Optional[datetime] = None,
    ) -> List[DriftSignal]:
        """Run all five detectors over a list of ledger entries.

        Args:
            recent_entries: ledger entries in the analysis window (caller filters by date)
            bundle_rule_ids: full list of known rule IDs (for unused-rule detection)
            now: clock injection for testability
        """
        now = now or datetime.now(timezone.utc)
        signals: List[DriftSignal] = []

        signals.extend(self._detect_autopilot_rejection(recent_entries, now))
        signals.extend(self._detect_cost_climb(recent_entries, now))
        signals.extend(self._detect_class_drift(recent_entries))
        signals.extend(self._detect_unused_rules(recent_entries, bundle_rule_ids or []))
        signals.extend(self._detect_phi_violations(recent_entries))

        return signals

    # ---- 1. autopilot rejection rate -----------------------------------
    def _detect_autopilot_rejection(
        self,
        entries: List[LedgerEntry],
        now: datetime,
    ) -> List[DriftSignal]:
        cutoff = (now - self._rejection_window).isoformat()
        recent = [e for e in entries
                  if e.entry_type == "runtime"
                  and e.created_at >= cutoff
                  and e.confidence_source == "autopilot"]
        if not recent:
            return []
        # Group by ambiguity_class
        by_class: Dict[str, List[LedgerEntry]] = defaultdict(list)
        for e in recent:
            if e.ambiguity_class:
                by_class[e.ambiguity_class].append(e)

        out: List[DriftSignal] = []
        for klass, klass_entries in by_class.items():
            rejected = sum(1 for e in klass_entries if e.decision_kind == "reject")
            total = len(klass_entries)
            if total < 4:  # too few to be statistically meaningful
                continue
            pct = (rejected / total) * 100.0
            if pct >= self._rejection_threshold_pct:
                out.append(DriftSignal(
                    kind=DriftSignalKind.AUTOPILOT_REJECTION_RATE_HIGH,
                    ambiguity_class=klass,
                    metric_value=pct,
                    metric_baseline=self._rejection_threshold_pct,
                    sample_size=total,
                    evidence_entry_ids=[e.id for e in klass_entries],
                    description=(
                        f"Autopilot rejection rate for class '{klass}' = "
                        f"{pct:.1f}% ({rejected}/{total}) over last "
                        f"{self._rejection_window.days}d, threshold "
                        f"{self._rejection_threshold_pct}%."
                    ),
                ))
        return out

    # ---- 2. cost-per-decision climbing ----------------------------------
    def _detect_cost_climb(
        self,
        entries: List[LedgerEntry],
        now: datetime,
    ) -> List[DriftSignal]:
        runtime = [e for e in entries
                   if e.entry_type == "runtime" and e.cost_usd > 0]
        if len(runtime) < 10:
            return []
        baseline_cutoff = (now - self._cost_baseline_window).isoformat()
        recent_cutoff = (now - timedelta(days=7)).isoformat()
        # Group by stage
        by_stage_baseline: Dict[str, List[float]] = defaultdict(list)
        by_stage_recent: Dict[str, List[float]] = defaultdict(list)
        for e in runtime:
            if not e.stage:
                continue
            if e.created_at >= recent_cutoff:
                by_stage_recent[e.stage].append(e.cost_usd)
            elif e.created_at >= baseline_cutoff:
                by_stage_baseline[e.stage].append(e.cost_usd)

        out: List[DriftSignal] = []
        for stage, recent_costs in by_stage_recent.items():
            baseline_costs = by_stage_baseline.get(stage, [])
            if len(baseline_costs) < 5 or len(recent_costs) < 3:
                continue
            recent_mean = mean(recent_costs)
            baseline_mean = mean(baseline_costs)
            if baseline_mean == 0:
                continue
            ratio = recent_mean / baseline_mean
            if ratio >= self._cost_climb_multiplier:
                out.append(DriftSignal(
                    kind=DriftSignalKind.COST_PER_DECISION_CLIMBING,
                    stage=stage,
                    metric_value=recent_mean,
                    metric_baseline=baseline_mean,
                    sample_size=len(recent_costs),
                    description=(
                        f"Stage '{stage}' mean $/decision = ${recent_mean:.4f} "
                        f"vs 30d baseline ${baseline_mean:.4f} (ratio {ratio:.2f}x)"
                    ),
                ))
        return out

    # ---- 3. class drift unexpected --------------------------------------
    def _detect_class_drift(
        self,
        entries: List[LedgerEntry],
    ) -> List[DriftSignal]:
        runtime = [e for e in entries
                   if e.entry_type == "runtime" and e.ambiguity_class]
        if len(runtime) < 10:
            return []
        class_counts = Counter(e.ambiguity_class for e in runtime)
        total = sum(class_counts.values())
        # A class is drift-y if it appears > threshold% AND has zero precedent_refs
        # (no historical decisions to learn from).
        out: List[DriftSignal] = []
        for klass, count in class_counts.items():
            pct = (count / total) * 100.0
            if pct < self._class_drift_threshold_pct:
                continue
            klass_entries = [e for e in runtime if e.ambiguity_class == klass]
            with_precedent = sum(1 for e in klass_entries if e.precedent_refs)
            if with_precedent > 0:
                continue  # has historical context; not drift
            out.append(DriftSignal(
                kind=DriftSignalKind.CLASS_DRIFT_UNEXPECTED,
                ambiguity_class=klass,
                metric_value=pct,
                metric_baseline=self._class_drift_threshold_pct,
                sample_size=count,
                description=(
                    f"Class '{klass}' = {pct:.1f}% ({count}/{total}) of recent "
                    f"decisions but has zero precedent_refs — unprecedented drift."
                ),
            ))
        return out

    # ---- 4. bundle rule unused ------------------------------------------
    def _detect_unused_rules(
        self,
        entries: List[LedgerEntry],
        known_rule_ids: List[str],
    ) -> List[DriftSignal]:
        if not known_rule_ids:
            return []
        seen_refs: set[str] = set()
        for e in entries:
            seen_refs.update(e.bundle_refs)

        out: List[DriftSignal] = []
        for rule_id in known_rule_ids:
            if rule_id in seen_refs:
                continue
            out.append(DriftSignal(
                kind=DriftSignalKind.BUNDLE_RULE_UNUSED,
                bundle_ref=rule_id,
                metric_value=0,
                description=f"Rule {rule_id} has zero ledger references in window",
            ))
        return out

    # ---- 5. PHI class violation -----------------------------------------
    def _detect_phi_violations(
        self,
        entries: List[LedgerEntry],
    ) -> List[DriftSignal]:
        out: List[DriftSignal] = []
        for e in entries:
            if e.runtime_kind == "phi_block" or (
                e.phi_class == "high" and e.decision_kind == "reject"
            ):
                out.append(DriftSignal(
                    kind=DriftSignalKind.PHI_CLASS_VIOLATION,
                    bundle_ref=next(iter(e.bundle_refs), None),
                    team_id=e.team_id,
                    sample_size=1,
                    evidence_entry_ids=[e.id],
                    description=(
                        f"PHI class violation in team {e.team_id}, "
                        f"decision: {e.decision[:80]}"
                    ),
                ))
        return out
