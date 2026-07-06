"""Phase 3 bundle-rules tests — authorable standards bundles.

Covers the openspec spec scenarios (add-configuration-plane, Requirement
"authorable standards bundles with blast class and PHI lock"):
  - each rule carries blast_class (low|med|high) and phi_locked (bool)
  - phi:true rules are phi_locked by default (can't be silently weakened)
  - a governed edit that would UNLOCK / WEAKEN / DELETE a phi_locked rule is
    refused at save time (the teeth — defense in depth, mirroring the autonomy
    invariant hard-lock)
  - a governed edit that TIGHTENS or ADDS rules is allowed
  - the shipped security bundle parses and its PHI rules are locked

RED first: apps/orchestrator/bundle_rules.py does not exist yet.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from apps.orchestrator import bundle_rules as br


SECURED = """
metadata:
  bundle: security
  version: 0.1.0
rules:
  - id: PHI-001
    title: No PHI in logs
    phi: true
    severity: BLOCK
    rationale: HIPAA Safe Harbor.
  - id: SBOM-001
    title: SBOM at build
    phi: false
    blast_class: low
    severity: BLOCK
    rationale: Supply chain.
  - id: STYLE-001
    title: Naming convention
    phi: false
    blast_class: med
    severity: WARN
    rationale: Consistency.
"""


# ---- parsing / schema -------------------------------------------------------

def test_loads_rules_with_blast_class_and_phi_locked(tmp_path):
    b = br.load_bundle_from_text(SECURED)
    assert b.dept == "security"
    assert set(b.rules) == {"PHI-001", "SBOM-001", "STYLE-001"}
    sbom = b.rules["SBOM-001"]
    assert sbom.blast_class == "LOW"        # normalized low -> LOW
    assert sbom.phi_locked is False
    assert sbom.severity == "BLOCK"


def test_phi_true_rule_is_phi_locked_by_default():
    b = br.load_bundle_from_text(SECURED)
    phi = b.rules["PHI-001"]
    assert phi.phi is True
    # a PHI rule is locked even though the YAML never said phi_locked: true
    assert phi.phi_locked is True


def test_blast_class_defaults_to_med_when_absent():
    b = br.load_bundle_from_text(SECURED)
    # PHI-001 omits blast_class -> defaults MED
    assert b.rules["PHI-001"].blast_class == "MED"


def test_invalid_blast_class_rejected():
    bad = """
metadata: { bundle: security, version: 0.1.0 }
rules:
  - id: X-1
    title: t
    blast_class: catastrophic
    severity: BLOCK
    rationale: r
"""
    with pytest.raises(ValueError):
        br.load_bundle_from_text(bad)


# ---- governance teeth: validate_bundle_edit ---------------------------------

def test_edit_that_deletes_a_phi_locked_rule_is_refused():
    existing = br.load_bundle_from_text(SECURED)
    proposed = br.load_bundle_from_text("""
metadata: { bundle: security, version: 0.1.0 }
rules:
  - id: SBOM-001
    title: SBOM at build
    severity: BLOCK
    rationale: r
""")
    with pytest.raises(br.PhiLockViolation) as ei:
        br.validate_bundle_edit(existing, proposed)
    assert "PHI-001" in str(ei.value)


def test_edit_that_downgrades_a_phi_locked_rule_severity_is_refused():
    existing = br.load_bundle_from_text(SECURED)
    proposed = br.load_bundle_from_text("""
metadata: { bundle: security, version: 0.1.0 }
rules:
  - id: PHI-001
    title: No PHI in logs
    phi: true
    severity: WARN
    rationale: r
""")
    with pytest.raises(br.PhiLockViolation):
        br.validate_bundle_edit(existing, proposed)


def test_edit_that_flips_phi_locked_false_is_refused():
    existing = br.load_bundle_from_text(SECURED)
    proposed = br.load_bundle_from_text("""
metadata: { bundle: security, version: 0.1.0 }
rules:
  - id: PHI-001
    title: No PHI in logs
    phi: false
    phi_locked: false
    severity: BLOCK
    rationale: r
""")
    with pytest.raises(br.PhiLockViolation):
        br.validate_bundle_edit(existing, proposed)


def test_edit_that_tightens_a_non_locked_rule_is_allowed():
    existing = br.load_bundle_from_text(SECURED)
    # STYLE-001 WARN -> BLOCK (tightening) is fine
    proposed = br.load_bundle_from_text(SECURED.replace(
        "    title: Naming convention\n    phi: false\n    blast_class: med\n    severity: WARN",
        "    title: Naming convention\n    phi: false\n    blast_class: med\n    severity: BLOCK",
    ))
    # no raise
    br.validate_bundle_edit(existing, proposed)


def test_edit_that_adds_a_new_rule_is_allowed():
    existing = br.load_bundle_from_text(SECURED)
    proposed = br.load_bundle_from_text(SECURED + """
  - id: NEW-001
    title: brand new
    severity: BLOCK
    rationale: r
""")
    br.validate_bundle_edit(existing, proposed)


def test_edit_may_strengthen_lock_on_a_previously_unlocked_rule():
    existing = br.load_bundle_from_text(SECURED)
    # STYLE-001 gains phi_locked: true — strengthening is always allowed
    proposed = br.load_bundle_from_text(SECURED.replace(
        "    title: Naming convention\n    phi: false\n    blast_class: med\n    severity: WARN",
        "    title: Naming convention\n    phi: false\n    phi_locked: true\n    blast_class: med\n    severity: WARN",
    ))
    br.validate_bundle_edit(existing, proposed)


# ---- shipped bundles --------------------------------------------------------

def test_shipped_security_bundle_loads_and_phi_rules_locked():
    repo_root = Path(__file__).resolve().parents[3]
    b = br.load_bundle("security", "v0.1.0", bundles_dir=repo_root / "standards-bundles")
    # every phi:true rule must be phi_locked
    phi_rules = [r for r in b.rules.values() if r.phi]
    assert phi_rules, "security bundle should have PHI rules"
    assert all(r.phi_locked for r in phi_rules)
