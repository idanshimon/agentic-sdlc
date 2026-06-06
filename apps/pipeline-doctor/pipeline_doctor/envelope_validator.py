"""Envelope validator — gates Pipeline Doctor's auto-fixes.

Hard rules (override any envelope.yaml content):
  - PHI rules (phi: true) are NEVER auto-fixed.
  - Deny rules (rule_pattern matching "deny/*") are NEVER loosened.

Soft rules (configurable per bundle envelope.yaml):
  - rule_pattern allow-list
  - bounds (min/max/max_delta)
  - preconditions (drift_signal_present_for_days, phi_class_not_high)
  - rate limits (max auto-fixes per dept per N days)
"""
from __future__ import annotations
import fnmatch
from typing import Any, Dict, List, Optional

import yaml

from .models import AutoFixProposal, EnvelopeCheck, EnvelopeViolation


class EnvelopeValidator:
    """Validates auto-fix proposals against a bundle's envelope.yaml."""

    def __init__(self, envelope_yaml: Dict[str, Any], bundle_rules: Dict[str, Any]):
        """
        Args:
            envelope_yaml: parsed envelope.yaml content
            bundle_rules: parsed rules.yaml content (used to check phi: true / deny)
        """
        self._envelope = envelope_yaml
        self._rules_by_id = {
            r["id"]: r for r in bundle_rules.get("rules", [])
        }

    def validate(
        self,
        proposal: AutoFixProposal,
        recent_fix_count_for_dept: int = 0,
        precondition_state: Optional[Dict[str, Any]] = None,
    ) -> EnvelopeCheck:
        """Validate an auto-fix proposal. Returns EnvelopeCheck with allowed + violations.

        Args:
            proposal: the proposed auto-fix
            recent_fix_count_for_dept: how many auto-fixes have been applied
                to this dept in the rate-limit window (used for rate-limiting)
            precondition_state: e.g. {"drift_signal_present_for_days": 9}
        """
        violations: List[EnvelopeViolation] = []
        precondition_state = precondition_state or {}

        # ---- HARD RULE: PHI rules NEVER auto-fixed --------------------------
        rule = self._rules_by_id.get(proposal.rule_id)
        if rule and rule.get("phi") is True:
            violations.append(EnvelopeViolation(
                reason="phi_rule_forbidden",
                detail=(
                    f"Rule {proposal.rule_id} is marked phi=true; "
                    "auto-fix permanently forbidden by hard-coded validator."
                ),
            ))
            # Short-circuit: PHI block trumps everything
            return EnvelopeCheck(allowed=False, violations=violations)

        # ---- HARD RULE: deny patterns NEVER loosened ------------------------
        if rule and self._is_deny_pattern(rule):
            violations.append(EnvelopeViolation(
                reason="deny_pattern_forbidden",
                detail=(
                    f"Rule {proposal.rule_id} pattern matches deny/*; "
                    "auto-fix forbidden."
                ),
            ))
            return EnvelopeCheck(allowed=False, violations=violations)

        # ---- envelope rule_pattern check -----------------------------------
        allowed_fixes = self._envelope.get("allowed_auto_fixes", []) or []
        matched_envelope = self._find_matching_envelope_entry(
            allowed_fixes, proposal.field_path
        )
        if matched_envelope is None:
            violations.append(EnvelopeViolation(
                reason="rule_not_in_envelope",
                detail=(
                    f"Field '{proposal.field_path}' not covered by any "
                    f"allowed_auto_fixes pattern in envelope."
                ),
            ))
            return EnvelopeCheck(allowed=False, violations=violations)

        # ---- bounds check --------------------------------------------------
        bounds = matched_envelope.get("bounds", {})
        v = self._check_bounds(proposal, bounds)
        if v:
            violations.append(v)

        # ---- preconditions check -------------------------------------------
        requires = matched_envelope.get("requires", []) or []
        for req in requires:
            for key, expected in req.items():
                actual = precondition_state.get(key)
                if not self._meets_precondition(key, expected, actual):
                    violations.append(EnvelopeViolation(
                        reason="preconditions_unmet",
                        detail=f"precondition '{key}'={expected} unmet (actual={actual})",
                    ))

        # ---- rate limit check ----------------------------------------------
        rate_limit = self._envelope.get("rate_limits", {}) or {}
        max_per_dept = rate_limit.get("max_per_dept_per_window", 5)
        if recent_fix_count_for_dept >= max_per_dept:
            violations.append(EnvelopeViolation(
                reason="rate_limit_exceeded",
                detail=(
                    f"Dept already has {recent_fix_count_for_dept} auto-fixes "
                    f"in current window (max={max_per_dept})."
                ),
            ))

        return EnvelopeCheck(
            allowed=(len(violations) == 0),
            violations=violations,
        )

    @staticmethod
    def _is_deny_pattern(rule: Dict[str, Any]) -> bool:
        sev = rule.get("severity", "")
        if sev == "BLOCK":
            return True
        pattern = rule.get("rule_pattern", "")
        return fnmatch.fnmatch(pattern, "deny/*")

    @staticmethod
    def _find_matching_envelope_entry(
        allowed: List[Dict[str, Any]],
        field_path: str,
    ) -> Optional[Dict[str, Any]]:
        for entry in allowed:
            pattern = entry.get("rule_pattern", "")
            if fnmatch.fnmatch(field_path, pattern):
                return entry
        return None

    @staticmethod
    def _check_bounds(
        proposal: AutoFixProposal,
        bounds: Dict[str, Any],
    ) -> Optional[EnvelopeViolation]:
        """Returns a violation if proposal.proposed_value is out of bounds."""
        proposed = proposal.proposed_value
        current = proposal.current_value
        # Only numeric bounds supported in v0.7
        if not isinstance(proposed, (int, float)):
            return None
        lo = bounds.get("min")
        hi = bounds.get("max")
        max_delta = bounds.get("max_delta_per_run")
        if lo is not None and proposed < lo:
            return EnvelopeViolation(
                reason="out_of_bounds",
                detail=f"proposed {proposed} < min {lo}",
            )
        if hi is not None and proposed > hi:
            return EnvelopeViolation(
                reason="out_of_bounds",
                detail=f"proposed {proposed} > max {hi}",
            )
        if max_delta is not None and isinstance(current, (int, float)):
            if abs(proposed - current) > max_delta:
                return EnvelopeViolation(
                    reason="out_of_bounds",
                    detail=f"|delta {proposed - current}| > max_delta_per_run {max_delta}",
                )
        return None

    @staticmethod
    def _meets_precondition(key: str, expected: Any, actual: Any) -> bool:
        # Special handling for known precondition keys
        if key == "drift_signal_present_for_days":
            if not isinstance(expected, (int, float)):
                return False
            if not isinstance(actual, (int, float)):
                return False
            return actual >= expected
        if key == "phi_class_not_high":
            # if expected: True, then actual phi class must be != "high".
            # The caller sends actual=True to mean "we have verified phi_class is NOT high".
            # We send actual=<phi_class string> when we want the validator to check directly.
            if expected is True:
                if actual is True:
                    return True  # caller-asserted not-high
                if actual == "high":
                    return False
                return True  # any non-"high" string or False is OK
            return actual == expected
        # Default: equality
        return actual == expected


def load_envelope(envelope_path: str) -> Dict[str, Any]:
    with open(envelope_path) as f:
        return yaml.safe_load(f) or {}


def load_rules(rules_path: str) -> Dict[str, Any]:
    with open(rules_path) as f:
        return yaml.safe_load(f) or {}
