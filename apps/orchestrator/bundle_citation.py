"""Bundle-citation honesty.

Task 2.1-2.4 of adopt-github-native-execution-substrate.

`bundle_refs` answers "which rule decided this?". Two ways to make that answer
dishonest, both of which this module's helpers prevent:

1. **A hardcoded rule ID.** `deliver_github.py` stamped a literal
   `architect/v0.1.0/SERVICE-CONTAINERIZED-001` on every delivered entry. No
   such rule was evaluated during delivery. An auditor filtering the ledger by
   that rule would find deliveries that never applied it — the citation was
   decoration, and decoration in an audit record is worse than an empty field.

2. **Implying rule-level precision when only the subscription set is known.**
   Stamping a stage's whole `bundle_subscriptions` list reads identically to
   "these rules were evaluated". Usually they weren't; the stage merely
   subscribes to those bundles. The record must be able to say which of the two
   it means.

So a citation carries its own provenance: `rule_evaluated` (this rule was
actually applied to reach the decision) or `subscription` (we know the bundles
in scope, not the rule). Anything else fails closed to `subscription`.
"""
from __future__ import annotations

import re
from typing import Iterable, Literal, Optional

CitationKind = Literal["rule_evaluated", "subscription"]

# <dept>/v<semver>/<RULE-ID>  e.g. security/v0.2.0/PHI-001
_RULE_REF = re.compile(r"^[a-z][a-z0-9_-]*/v\d+\.\d+\.\d+/[A-Z][A-Z0-9-]*$")
# <dept>/v<semver>            e.g. security/v0.2.0
_BUNDLE_REF = re.compile(r"^[a-z][a-z0-9_-]*/v\d+\.\d+\.\d+$")


def is_rule_ref(ref: str) -> bool:
    """True when `ref` names a specific rule, not just a bundle."""
    return bool(_RULE_REF.match(ref or ""))


def is_bundle_ref(ref: str) -> bool:
    """True when `ref` names a bundle version with no rule component."""
    return bool(_BUNDLE_REF.match(ref or ""))


def cite_rules_evaluated(rule_refs: Optional[Iterable[str]]) -> list[str]:
    """Citations for rules that were ACTUALLY evaluated to reach a decision.

    Only well-formed `<dept>/v<x.y.z>/<RULE-ID>` references survive. A bare
    bundle reference is not a rule and is dropped rather than silently promoted
    — claiming rule-level precision we do not have is the exact defect this
    module exists to prevent.
    """
    if not rule_refs:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for ref in rule_refs:
        ref = (ref or "").strip()
        if ref and is_rule_ref(ref) and ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def cite_subscriptions(bundle_refs: Optional[Iterable[str]]) -> list[str]:
    """Citations for the bundles a stage subscribes to.

    Accepts bundle references, and tolerates rule references by reducing them
    to their bundle (`security/v0.2.0/PHI-001` -> `security/v0.2.0`): in a
    subscription context the rule component would overstate what we know.
    """
    if not bundle_refs:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for ref in bundle_refs:
        ref = (ref or "").strip()
        if not ref:
            continue
        if is_rule_ref(ref):
            ref = "/".join(ref.split("/")[:2])
        if is_bundle_ref(ref) and ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def classify_citation(
    refs: Optional[Iterable[str]],
    kind: Optional[str] = None,
) -> tuple[list[str], CitationKind]:
    """Return `(citations, citation_kind)` for a decision entry.

    `kind` may be supplied by the caller when it knows which it has. When it is
    absent or unrecognized we infer, and we fail closed: a set containing any
    non-rule reference is a `subscription`, never `rule_evaluated`. Over-
    claiming is the failure mode with audit consequences; under-claiming is
    merely less useful.
    """
    refs = [r for r in (refs or []) if (r or "").strip()]
    if not refs:
        return [], "subscription"

    if kind == "rule_evaluated":
        evaluated = cite_rules_evaluated(refs)
        if evaluated and len(evaluated) == len(refs):
            return evaluated, "rule_evaluated"
        # Caller claimed rule-level precision but did not supply only rules.
        return cite_subscriptions(refs), "subscription"

    if kind == "subscription":
        return cite_subscriptions(refs), "subscription"

    # Infer. Only an all-rules set earns the stronger claim.
    if all(is_rule_ref(r) for r in refs):
        return cite_rules_evaluated(refs), "rule_evaluated"
    return cite_subscriptions(refs), "subscription"
