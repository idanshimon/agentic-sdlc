"""Tests for replay scoring — the disagreement metric.

The critical tests here are the ones that assert the metric REFUSES to report a
number. A governance metric that fabricates confidence from thin data is worse
than no metric, because it gets believed.
"""
from __future__ import annotations

from apps.orchestrator.replay import (
    ReplayCase,
    ReplayPolicy,
    cases_from_ledger,
    score_replay,
)


def _case(cls="scope-resolution", actual="Use OAuth2.", proposed=None, auto=True, scored=True):
    return ReplayCase(
        entry_id="e", ambiguity_class=cls, team_id="team-x",
        actual=actual, proposed=proposed, autopiloted=auto, scored=scored,
    )


# ── policy is configuration, never hardcoded ──────────────────────────────

def test_policy_defaults_are_conservative():
    p = ReplayPolicy()
    assert p.min_samples >= 5
    assert p.disagreement_ceiling <= 0.10


def test_policy_is_read_from_bundle_rules():
    p = ReplayPolicy.from_bundle([
        {"id": "REPLAY-MIN-SAMPLES", "defaults": {"min_samples": 12}},
        {"id": "REPLAY-CEILING", "defaults": {"disagreement_ceiling": 0.25}},
    ])
    assert p.min_samples == 12
    assert p.disagreement_ceiling == 0.25


def test_per_class_ceiling_overrides_global():
    p = ReplayPolicy.from_bundle([
        {"id": "G", "defaults": {"disagreement_ceiling": 0.5}},
        {"id": "P", "ambiguity_class": "phi-classification",
         "defaults": {"disagreement_ceiling": 0.0}},
    ])
    assert p.ceiling_for("phi-classification") == 0.0
    assert p.ceiling_for("naming-convention") == 0.5


def test_phi_locked_rules_become_invariants_automatically():
    """An invariant declared for ENFORCEMENT must also be an invariant for
    autonomy scoring, or the two definitions drift apart silently."""
    p = ReplayPolicy.from_bundle([
        {"id": "PHI-001", "ambiguity_class": "phi-classification", "phi_locked": True},
    ])
    assert p.is_invariant("phi-classification")


def test_malformed_bundle_values_fall_back_rather_than_crash():
    p = ReplayPolicy.from_bundle([
        {"id": "X", "defaults": {"min_samples": "not-a-number",
                                 "disagreement_ceiling": None}},
    ])
    assert p.min_samples == ReplayPolicy().min_samples


# ── the metric must refuse to lie ─────────────────────────────────────────

def test_insufficient_samples_reports_none_not_a_flattering_zero():
    r = score_replay([_case(proposed="Use OAuth2.")] * 2)
    c = r.classes["scope-resolution"]
    assert c.autopilot_disagreement_rate is None
    assert c.verdict == "INSUFFICIENT"


def test_unscored_cases_are_not_counted_as_agreements():
    """The failure mode that makes a disagreement metric useless."""
    r = score_replay([_case(proposed=None) for _ in range(10)])
    c = r.classes["scope-resolution"]
    assert c.scored == 0
    assert c.agreements == 0
    assert c.verdict == "UNSCORED"


def test_agreement_and_disagreement_are_counted():
    cases = [_case(proposed="Use OAuth2.") for _ in range(8)]
    cases += [_case(proposed="Use SAML.") for _ in range(2)]
    r = score_replay(cases)
    c = r.classes["scope-resolution"]
    assert c.agreements == 8
    assert c.disagreements == 2
    assert abs(c.autopilot_disagreement_rate - 0.2) < 1e-9


def test_high_disagreement_recommends_revocation():
    cases = [_case(proposed="Use SAML.") for _ in range(6)]
    r = score_replay(cases)
    assert r.classes["scope-resolution"].verdict == "REVOKE AUTONOMY"
    assert len(r.classes_to_revoke()) == 1


def test_clean_record_earns_autonomy():
    r = score_replay([_case(proposed="Use OAuth2.") for _ in range(6)])
    assert r.classes["scope-resolution"].verdict == "AUTONOMY EARNED"


def test_invariant_never_earns_autonomy_however_well_it_scores():
    p = ReplayPolicy(invariant_classes=frozenset({"phi-classification"}))
    cases = [_case(cls="phi-classification", proposed="Use OAuth2.") for _ in range(50)]
    r = score_replay(cases, p)
    assert r.classes["phi-classification"].verdict == "INVARIANT — HUMAN ALWAYS"


def test_gated_errors_do_not_count_against_autopilot():
    """A wrong SUGGESTION caught by a human is the system working."""
    cases = [_case(proposed="Use SAML.", auto=False) for _ in range(6)]
    r = score_replay(cases)
    c = r.classes["scope-resolution"]
    assert c.disagreements == 6
    assert c.autopilot_disagreements == 0


def test_comparison_normalises_whitespace_and_case_only():
    r = score_replay([_case(actual="Use OAuth2.", proposed="use  oauth2.")] * 6)
    assert r.classes["scope-resolution"].agreements == 6
    # ...but does NOT fuzzy-match different answers into agreement.
    r2 = score_replay([_case(actual="Use OAuth2.", proposed="Use OAuth2 with PKCE.")] * 6)
    assert r2.classes["scope-resolution"].agreements == 0


# ── ledger pairing must key on card_id, not slot_value_hash ───────────────

def test_pairs_on_card_id_not_slot_value_hash():
    """slot_value_hash is class-level on live data; pairing on it compares
    unrelated questions and reports ~100% disagreement."""
    entries = [
        {"id": "1", "card_id": "card-A", "slot_value_hash": "shared",
         "ambiguity_class": "scope-resolution", "confidence_source": "human",
         "resolution_text": "Use OAuth2.", "created_at": "2026-01-01T00:00:00"},
        {"id": "2", "card_id": "card-A", "slot_value_hash": "shared",
         "ambiguity_class": "scope-resolution", "confidence_source": "autopilot",
         "resolution_text": "Use OAuth2.", "created_at": "2026-01-02T00:00:00"},
        # Different question, same hash — must NOT be compared against card-A.
        {"id": "3", "card_id": "card-B", "slot_value_hash": "shared",
         "ambiguity_class": "scope-resolution", "confidence_source": "autopilot",
         "resolution_text": "Retain logs 7 years.", "created_at": "2026-01-03T00:00:00"},
    ]
    cases = cases_from_ledger(entries)
    assert len(cases) == 1
    assert cases[0].entry_id == "2"
    assert score_replay(cases).classes["scope-resolution"].disagreements == 0


def test_cards_without_a_human_ruling_yield_no_ground_truth():
    entries = [
        {"id": "1", "card_id": "card-A", "ambiguity_class": "x",
         "confidence_source": "autopilot", "resolution_text": "Guess.",
         "created_at": "2026-01-01T00:00:00"},
    ]
    assert cases_from_ledger(entries) == []


def test_replay_never_mutates_input_entries():
    """Replay is a read-only projection over the audit substrate."""
    entries = [
        {"id": "1", "card_id": "c", "ambiguity_class": "x",
         "confidence_source": "human", "resolution_text": "A",
         "created_at": "2026-01-01T00:00:00"},
        {"id": "2", "card_id": "c", "ambiguity_class": "x",
         "confidence_source": "autopilot", "resolution_text": "A",
         "created_at": "2026-01-02T00:00:00"},
    ]
    import copy
    before = copy.deepcopy(entries)
    score_replay(cases_from_ledger(entries))
    assert entries == before
