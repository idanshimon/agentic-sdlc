"""Context-scoped PHI-001 enforcement: the rule flags cleartext LOGGING of
patient identifiers, not their legitimate use as domain field/param names.

Regression guard for the fix that made security/v0.1.0/PHI-001 usable by real
healthcare teams (a real eligibility service unavoidably names a `patient_id`
field; a blanket token match blocked 100% of real code)."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "scripts"))
import enforce_bundles as eb  # noqa: E402


def _phi001_rule() -> eb.CIRule:
    root = pathlib.Path(__file__).resolve().parents[3] / "standards-bundles"
    rules = eb.select_ci_rules_from_file(
        root / "security" / "v0.1.0" / "rules.yaml",
        dept="security", version="v0.1.0",
        force_all_block_patterns=True,
    )
    phi = [r for r in rules if r.rule_id == "PHI-001"]
    assert phi, "PHI-001 must be CI-eligible"
    return phi[0]


def test_phi001_blocks_cleartext_logging():
    rule = _phi001_rule()
    blocked = [
        "logger.info(f'patient {mrn} updated')",
        "logging.debug('DOB=' + str(dob))",
        "logger.info(f'checked {patient_id}')",
        "print(f'SSN is {ssn}')",
        "log.error(f'lookup failed for MRN {mrn}')",
    ]
    for line in blocked:
        assert rule.matches_line(line), f"should BLOCK: {line}"


def test_phi001_allows_legitimate_domain_usage():
    rule = _phi001_rule()
    allowed = [
        "    patient_id: str = Field(...)",          # Pydantic field
        "def check_eligibility(mrn: str) -> bool:",   # function param
        "        self.mrn = mrn",                      # assignment
        "class EligibilityRequest(BaseModel):",       # model decl
        "logger.info('eligibility complete', extra={'request_id': rid})",  # PHI-free log
    ]
    for line in allowed:
        assert not rule.matches_line(line), f"should PASS: {line}"


def test_phi001_allows_redacted_logging():
    rule = _phi001_rule()
    allowed = [
        "logger.info(f'patient {patient_id_redacted()} updated')",
        "logger.info(f'patient {_redact(mrn)} updated')",
        "logger.info(f'checked {mask(patient_id)}')",
        "logger.info(f'checked {hash_id(ssn)}')",
    ]
    for line in allowed:
        assert not rule.matches_line(line), f"redacted should PASS: {line}"


def test_phi001_matches_its_own_declared_test_cases():
    """The rule's own test_cases block is the contract — enforce it."""
    import yaml
    root = pathlib.Path(__file__).resolve().parents[3] / "standards-bundles"
    doc = yaml.safe_load((root / "security" / "v0.1.0" / "rules.yaml").read_text())
    spec = next(r for r in doc["rules"] if r["id"] == "PHI-001")
    rule = _phi001_rule()
    for case in spec.get("test_cases", []):
        want_block = case["expect"] == "BLOCK"
        got = rule.matches_line(case["input"])
        assert got == want_block, (
            f"PHI-001 test_case mismatch: {case['input']!r} "
            f"expected {case['expect']}, got {'BLOCK' if got else 'PASS'}"
        )
