"""Tests for the retrospective runner (task 5.1)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from orchestrator.accuracy_compute import PromotionState, compute_accuracy_update
from orchestrator.retrospective import (
    RetrospectiveReport,
    _seed_for_window,
    run_retrospective,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


class _CS:
    def __init__(self, cls, autopiloted=0, disagreements=0):
        self.ambiguity_class = cls
        self.autopiloted = autopiloted
        self.autopilot_disagreements = disagreements

    @property
    def autopilot_disagreement_rate(self):
        if self.autopiloted < 2:
            return None
        return self.autopilot_disagreements / self.autopiloted


def _runs(n):
    return [{"run_id": f"run-{i}"} for i in range(n)]


# --- reproducibility ---------------------------------------------------------

def test_same_window_samples_the_same_runs():
    """An auditor asking 'which runs did you examine?' must get a stable answer."""
    a = run_retrospective(window_id="2026-W34", runs=_runs(80), class_scores=[])
    b = run_retrospective(window_id="2026-W34", runs=_runs(80), class_scores=[])
    assert a.sampled_run_ids == b.sampled_run_ids
    assert a.seed == b.seed


def test_different_windows_sample_differently():
    a = run_retrospective(window_id="2026-W34", runs=_runs(80), class_scores=[])
    b = run_retrospective(window_id="2026-W35", runs=_runs(80), class_scores=[])
    assert a.sampled_run_ids != b.sampled_run_ids


def test_seed_is_process_stable():
    """Must not depend on PYTHONHASHSEED — `hash()` would break reproducibility."""
    out = subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0,'apps');"
         "from orchestrator.retrospective import _seed_for_window;"
         "print(_seed_for_window('2026-W34'))"],
        cwd=REPO_ROOT, capture_output=True, text=True, env={"PYTHONHASHSEED": "1", "PATH": ""},
    )
    assert out.returncode == 0, out.stderr
    assert int(out.stdout.strip()) == _seed_for_window("2026-W34")


def test_explicit_seed_overrides_the_window_derived_one():
    r = run_retrospective(window_id="2026-W34", runs=_runs(50), class_scores=[], seed=99)
    assert r.seed == 99


# --- promotion across retrospectives -----------------------------------------

def test_priors_carry_promotion_across_windows():
    first = run_retrospective(
        window_id="w1", runs=_runs(10), class_scores=[_CS("scope-resolution", 6, 0)])
    assert first.updates[0].state == PromotionState.TENTATIVE
    assert first.updates[0].grants_autonomy is False

    second = run_retrospective(
        window_id="w2", runs=_runs(10),
        class_scores=[_CS("scope-resolution", 6, 0)],
        priors={"scope-resolution": first.updates[0]})
    assert second.updates[0].state == PromotionState.PROMOTED
    assert second.updates[0].grants_autonomy is True


def test_decay_is_applied_per_class():
    base = compute_accuracy_update(_CS("sla-binding", 6, 0), prior=None)
    r = run_retrospective(
        window_id="w2", runs=_runs(10), class_scores=[_CS("sla-binding", 6, 0)],
        priors={"sla-binding": base}, periods_unread={"sla-binding": 2})
    assert r.updates[0].accuracy_score < base.accuracy_score


# --- honest reporting --------------------------------------------------------

def test_unscored_class_is_reported_as_unscored_not_zero():
    r = run_retrospective(window_id="w1", runs=_runs(10), class_scores=[_CS("other", 1, 0)])
    assert r.unscored and r.unscored[0].accuracy_score is None
    assert not r.scored


def test_markdown_names_unscored_classes_explicitly():
    r = run_retrospective(window_id="w1", runs=_runs(10),
                          class_scores=[_CS("other", 1, 0), _CS("sla-binding", 6, 0)])
    md = r.to_markdown()
    assert "Unscored" in md and "`other`" in md
    assert "not as a zero score" in md


def test_markdown_states_it_does_not_write_to_the_ledger():
    r = run_retrospective(window_id="w1", runs=_runs(10), class_scores=[_CS("sla-binding", 6, 0)])
    assert "not written to the Decision Ledger" in r.to_markdown()


def test_markdown_carries_the_seed_for_reproduction():
    r = run_retrospective(window_id="w1", runs=_runs(10), class_scores=[])
    assert str(r.seed) in r.to_markdown()


def test_empty_window_does_not_fabricate_a_report():
    r = run_retrospective(window_id="w1", runs=[], class_scores=[])
    assert r.population == 0 and r.sampled == 0
    assert "No decision classes were measurable" in r.to_markdown()


def test_report_json_roundtrips():
    r = run_retrospective(window_id="w1", runs=_runs(10), class_scores=[_CS("sla-binding", 6, 0)])
    d = json.loads(json.dumps(r.to_dict()))
    assert d["window_id"] == "w1"
    assert d["updates"][0]["state"] == "tentative"


# --- the boundary that must not be crossed -----------------------------------

def test_runner_performs_no_persistence():
    """replay measures, accuracy_compute promotes, this reports. None persist.

    A retrospective that quietly mutated precedent rows would be exactly the
    silent, unattributable agent action this project exists to prevent.
    """
    import inspect

    from orchestrator import retrospective

    src = inspect.getsource(retrospective)
    for forbidden in ("write_entry", "CosmosClient", "upsert_item", "create_item"):
        assert forbidden not in src, f"retrospective must not persist ({forbidden!r})"


# --- CLI ---------------------------------------------------------------------

def test_cli_emits_markdown(tmp_path):
    payload = {
        "runs": [{"run_id": f"r{i}"} for i in range(30)],
        "class_scores": [
            {"ambiguity_class": "sla-binding", "autopiloted": 6, "autopilot_disagreements": 0},
            {"ambiguity_class": "other", "autopiloted": 1, "autopilot_disagreements": 0},
        ],
    }
    f = tmp_path / "in.json"
    f.write_text(json.dumps(payload))
    out = subprocess.run(
        [sys.executable, "-m", "orchestrator.retrospective",
         "--window-id", "2026-W34", "--input", str(f), "--markdown"],
        cwd=REPO_ROOT / "apps", capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert "Retrospective" in out.stdout
    assert "sla-binding" in out.stdout
    assert "Unscored" in out.stdout


def test_cli_emits_valid_json(tmp_path):
    f = tmp_path / "in.json"
    f.write_text(json.dumps({"runs": [], "class_scores": []}))
    out = subprocess.run(
        [sys.executable, "-m", "orchestrator.retrospective",
         "--window-id", "w1", "--input", str(f)],
        cwd=REPO_ROOT / "apps", capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["window_id"] == "w1"
