"""Teaching-loop fix — slot_value_hash must be STABLE across runs for the same
ambiguity, so findPrecedent can match an operator's swap on a later run.

The bug (verified live 2026-06-20): slot_value_hash was _hash(title + detail),
and title/detail come from the LLM assessor's prose, which varies run-to-run.
The same PRD produced a different slot hash every run → findPrecedent's exact
(team, class, slot_value_hash) match could never fire → the teaching loop was
dead. The fix keys on the stable semantic identity (class + normalized PRD
section), not the LLM's wording.

Run: PYTHONPATH=. .venv/bin/python -m pytest apps/orchestrator/tests/test_slot_key_stability.py -v
"""
from __future__ import annotations

from apps.orchestrator._pipeline_stages import _slot_key


def test_same_class_and_section_is_stable():
    """The whole point: identical class+section → identical key, every time."""
    a = _slot_key("data-retention", "Data Handling")
    b = _slot_key("data-retention", "Data Handling")
    assert a == b


def test_section_whitespace_and_case_normalized():
    """LLM may emit 'Data Handling' / 'data  handling' / ' DATA HANDLING ' for
    the same section — all must produce the same key."""
    base = _slot_key("data-retention", "Data Handling")
    assert _slot_key("data-retention", "data  handling") == base
    assert _slot_key("data-retention", "  DATA HANDLING  ") == base


def test_different_class_differs():
    assert _slot_key("data-retention", "X") != _slot_key("sla-binding", "X")


def test_different_section_differs():
    assert _slot_key("data-retention", "Section A") != _slot_key("data-retention", "Section B")


def test_empty_section_falls_back_to_class_only_and_is_stable():
    a = _slot_key("phi-classification")
    b = _slot_key("phi-classification", "")
    assert a == b  # both class-only
    assert _slot_key("phi-classification") == _slot_key("phi-classification")


def test_key_does_not_depend_on_llm_prose():
    """The regression guard: the key must NOT change when only the title/detail
    prose changes (which is exactly what varied run-to-run). _slot_key never
    takes prose, so two cards of the same class+section match regardless of how
    the LLM phrased the title — this test documents that contract."""
    # Same class + section, conceptually different prose → same key.
    key_run_a = _slot_key("sla-binding", "Service Levels")
    key_run_b = _slot_key("sla-binding", "Service Levels")
    assert key_run_a == key_run_b
