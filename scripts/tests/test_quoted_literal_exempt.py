"""Tests for `quoted_literal_exempt` — the DESCRIBES-vs-COMMITS distinction.

Motivating defect: a repo-wide scan produced 24 BLOCK violations of which ZERO
were real leaks. 23 were tests/fixtures and the one "production" hit was the
prose "Logging policy for MRN field unclear." Worst of all, PHI-001 blocked its
OWN test suite — test_phi001_context_scoped.py's fixture line is the literal
"logger.info(f'patient {mrn} updated')".

A gate with a 100% false-positive rate trains people to route around it, which
kills enforcement more thoroughly than having no gate.

The security posture under test is asymmetric and deliberate: a MISSED real leak
is catastrophic, a false positive is merely expensive. So every ambiguous case
here must resolve to BLOCK, and the adversarial cases below matter more than the
happy path.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from enforce_bundles import CIRule, _is_inside_string_literal  # noqa: E402

PHI_PATTERN = r"(?i)(?<![\w(])\b(MRN|patient_id|SSN|DOB)\b(?!\s*\()"
PHI_CONTEXT = (
    r"(?i)\b(logger|logging|log|print)\b|\.(info|debug|warning|warn|error"
    r"|critical|exception|write)\s*\(|sys\.std(out|err)"
)


def _rule(*, exempt: bool) -> CIRule:
    return CIRule(
        dept="security",
        version="v0.1.0",
        rule_id="PHI-001",
        title="Patient identifiers may not appear in cleartext logs",
        pattern=PHI_PATTERN,
        phi=True,
        context_pattern=PHI_CONTEXT,
        quoted_literal_exempt=exempt,
    )


# ---------------------------------------------------------------------------
# The core distinction
# ---------------------------------------------------------------------------

def test_real_logging_call_still_blocks_when_exemption_is_on():
    """THE load-bearing test. The exemption must never excuse an actual leak."""
    assert _rule(exempt=True).matches_line('logger.info(f"patient {MRN} updated")')


def test_quoted_example_is_exempt():
    """A string literal describing a violation is data, not a logging call."""
    line = """    text: 'logger.info(f"patient {MRN} updated record")',"""
    assert not _rule(exempt=True).matches_line(line)


def test_same_quoted_example_blocks_when_exemption_is_off():
    """Opt-in only: behaviour is unchanged for rules that don't set the flag."""
    line = """    text: 'logger.info(f"patient {MRN} updated record")',"""
    assert _rule(exempt=False).matches_line(line)


# ---------------------------------------------------------------------------
# Regression: the real lines that were false-positived
# ---------------------------------------------------------------------------

def test_phi001_no_longer_blocks_its_own_test_fixture():
    """test_phi001_context_scoped.py:31 — the rule blocked its own test suite."""
    fixture = '        "logger' + ".info(f'patient {mrn} updated')\","
    assert not _rule(exempt=True).matches_line(fixture)


def test_ui_placeholder_attribute_is_exempt():
    """phi/page.tsx:63 — a UI placeholder teaching what a violation looks like."""
    assert not _rule(exempt=True).matches_line(
        """            placeholder='Try: logger.info(f"patient {MRN} updated")'"""
    )


def test_prose_ambiguity_card_is_exempt():
    """_pipeline_stages.py:451 — the sole "production" hit was English prose."""
    assert not _rule(exempt=True).matches_line(
        '                title="Logging policy for MRN field unclear",'
    )


def test_test_dict_fixture_is_exempt():
    """test_review_verdict.py:52 — a fake file body inside a test dict."""
    fixture = '        {"svc.py": "logger' + ".info(f'patient {MRN} seen')\\n\"},"
    assert not _rule(exempt=True).matches_line(fixture)


# ---------------------------------------------------------------------------
# Adversarial — evasion attempts must FAIL CLOSED
# ---------------------------------------------------------------------------

def test_unterminated_quote_does_not_exempt():
    """Quote-stuffing is the obvious evasion. An open literal is never exempt."""
    assert _is_inside_string_literal('x = "', 5) is False
    assert _rule(exempt=True).matches_line('logger.info(f"patient {MRN} updated")  # "')


def test_trailing_quote_after_the_match_does_not_exempt():
    """Only the match POSITION counts, never mere presence of quotes."""
    assert _rule(exempt=True).matches_line(
        """logger.info(f"patient {MRN} seen")  # see 'the docs'"""
    )


def test_comment_marker_before_real_code_does_not_exempt():
    line = """logger.info(f"{MRN}")  # 'logger.info(MRN)'"""
    assert _rule(exempt=True).matches_line(line)


def test_string_closes_before_the_match():
    """Literal ends, then real code follows on the same line — must block."""
    line = """x = "harmless"; logger.info(f"patient {MRN}")"""
    assert _rule(exempt=True).matches_line(line)


def test_phi001_lookbehind_blind_spot_is_preexisting_not_caused_here():
    """DOCUMENTS A KNOWN GAP IN PHI-001 — see KNOWN-ISSUES.

    PHI-001's `pattern` opens with `(?<![\\w(])`, so a bare identifier sitting
    immediately after an opening paren is never matched. With a space before the
    identifier the lookbehind is broken and the rule fires. See the assertions
    below for both shapes.

    That lookbehind exists to stop `patient_id(` function CALLS from matching,
    but it also blinds the rule to the single most natural way to write the
    leak. This is independent of `quoted_literal_exempt` — it predates it and is
    unaffected by it. Pinned here so the gap is visible and cannot regress
    silently; fixing the pattern requires an OpenSpec change (phi_locked).
    """
    assert not _rule(exempt=False).matches_line("logger.info(patient_id)")
    assert _rule(exempt=False).matches_line("logger.info( patient_id )")


def test_escaped_quote_does_not_open_a_literal():
    r"""A \" is an escaped character, not a string delimiter."""
    assert _is_inside_string_literal(r'print(\"x\") ; logger.info(MRN)', 30) is False


# ---------------------------------------------------------------------------
# _is_inside_string_literal unit behaviour
# ---------------------------------------------------------------------------

def test_index_inside_single_quotes():
    assert _is_inside_string_literal("a = 'hello world'", 8) is True


def test_index_inside_double_quotes():
    assert _is_inside_string_literal('a = "hello world"', 8) is True


def test_index_inside_backticks():
    """JS template literals are the common TS/TSX fixture carrier."""
    assert _is_inside_string_literal("const a = `hello world`", 14) is True


def test_index_in_bare_code_is_not_inside():
    assert _is_inside_string_literal("logger.info(patient_id)", 12) is False


def test_index_after_a_closed_literal_is_not_inside():
    assert _is_inside_string_literal("""x = "done"; more_code""", 14) is False


def test_nested_opposite_quotes_are_literal_content():
    """A " inside a '...' does not close the ' literal."""
    line = """text: 'logger.info(f"patient {MRN}")'"""
    idx = line.index("MRN")
    assert _is_inside_string_literal(line, idx) is True


def test_default_is_off():
    """Absent the flag, a rule keeps its exact prior blast radius."""
    assert CIRule(
        dept="security", version="v0.1.0", rule_id="X", title="t", pattern="x"
    ).quoted_literal_exempt is False


def test_rule_without_context_pattern_is_never_exempted():
    """Spec scenario: no sink -> no identifiable "act" -> never exempt.

    A rule that opts in but is not sink-scoped cannot express DESCRIBES-vs-
    COMMITS, so it must fall back to plain pattern matching rather than guess.
    """
    rule = CIRule(
        dept="security",
        version="v0.1.0",
        rule_id="PHI-001",
        title="t",
        pattern=PHI_PATTERN,
        context_pattern=None,
        quoted_literal_exempt=True,
    )
    assert rule.matches_line("""x = "a quoted MRN mention" """)
