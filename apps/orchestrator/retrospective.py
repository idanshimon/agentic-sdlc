"""Retrospective runner — task 5.1.

Ties the pieces together into something a schedule can invoke:

    ledger entries -> replay (measure) -> accuracy_compute (promote) -> report

## Boundaries this preserves

`replay.py` refuses to write to the Decision Ledger, on the grounds that
inventing rows to make a metric look populated would corrupt the audit
substrate. `accuracy_compute.py` holds the same line. This module is the
caller, and it holds it too: **it computes and reports, it does not persist.**

Writing promoted scores back is a separate, deliberate step (task 5.2's write
path) that must go through the ledger's own append-only contract with a real
actor attribution. A retrospective that quietly mutated precedent rows would be
exactly the silent, unattributable agent action this whole project exists to
prevent.

So this runner is safe to schedule immediately: worst case it reports.

## Reproducibility

An auditor asking "which runs did this retrospective examine?" must get an
answer. The seed is derived from the window identifier when not supplied, so
the same window always samples the same runs, and the seed is carried in the
report.

## Honest reporting

A class replay cannot measure is reported UNSCORED with `accuracy_score=None`,
never `0.0`. That distinction is the entire point of the preceding two commits
and it does not get quietly dropped at the reporting layer.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Optional

from .accuracy_compute import (
    PromotionState,
    ScoreUpdate,
    apply_decay,
    compute_accuracy_update,
    select_sample,
)

DEFAULT_SAMPLE_SIZE = 25


def _seed_for_window(window_id: str) -> int:
    """Deterministic seed from a window identifier.

    Reproducible across processes and machines — `hash()` is not, because
    Python randomizes string hashing per interpreter.
    """
    digest = hashlib.sha256(window_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


@dataclass(frozen=True)
class RetrospectiveReport:
    window_id: str
    seed: int
    population: int
    sampled: int
    sampled_run_ids: list[str]
    updates: list[ScoreUpdate] = field(default_factory=list)

    @property
    def scored(self) -> list[ScoreUpdate]:
        return [u for u in self.updates if u.accuracy_score is not None]

    @property
    def unscored(self) -> list[ScoreUpdate]:
        return [u for u in self.updates if u.accuracy_score is None]

    @property
    def granting_autonomy(self) -> list[ScoreUpdate]:
        return [u for u in self.updates if u.grants_autonomy]

    def to_dict(self) -> dict[str, Any]:
        return {
            "window_id": self.window_id,
            "seed": self.seed,
            "population": self.population,
            "sampled": self.sampled,
            "sampled_run_ids": self.sampled_run_ids,
            "updates": [
                {**asdict(u), "state": u.state.value, "grants_autonomy": u.grants_autonomy}
                for u in self.updates
            ],
        }

    def to_markdown(self) -> str:
        """Operator-readable summary.

        Leads with what changed and what it means, not with a table of floats.
        """
        lines = [
            f"### Retrospective — `{self.window_id}`",
            "",
            f"Examined **{self.sampled} of {self.population}** completed runs "
            f"(random sample, seed `{self.seed}` — rerun with this seed to reproduce).",
            "",
        ]

        if not self.updates:
            lines.append("_No decision classes were measurable in this window._")
            return "\n".join(lines)

        lines += ["| class | score | samples | state | may autopilot |",
                  "|---|---|---|---|---|"]
        for u in sorted(self.updates, key=lambda x: x.ambiguity_class):
            score = "—" if u.accuracy_score is None else f"{u.accuracy_score:.2f}"
            lines.append(
                f"| `{u.ambiguity_class}` | {score} | {u.sample_count} | "
                f"{u.state.value} | {'yes' if u.grants_autonomy else 'no'} |"
            )

        if self.unscored:
            names = ", ".join(f"`{u.ambiguity_class}`" for u in self.unscored)
            lines += [
                "",
                f"**Unscored:** {names}. Replay could not compute a disagreement "
                "rate for these — recorded as unmeasured, not as a zero score.",
            ]

        lines += [
            "",
            "_This retrospective reports only. Promoted scores are not written to "
            "the Decision Ledger by this job._",
        ]
        return "\n".join(lines)


def run_retrospective(
    *,
    window_id: str,
    runs: Iterable[dict],
    class_scores: Iterable[Any],
    priors: Optional[dict[str, ScoreUpdate]] = None,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: Optional[int] = None,
    periods_unread: Optional[dict[str, int]] = None,
) -> RetrospectiveReport:
    """Fold one window's replay measurements into promoted accuracy scores.

    `class_scores` are `replay.ClassScore` objects for the sampled runs.
    `priors` carries each class's previous `ScoreUpdate`, which is what makes
    two-stage promotion possible across retrospectives.
    """
    runs = list(runs)
    resolved_seed = seed if seed is not None else _seed_for_window(window_id)
    sample = select_sample(runs, size=sample_size, seed=resolved_seed)
    sampled_ids = [str(r.get("run_id", "")) for r in sample]

    priors = priors or {}
    periods_unread = periods_unread or {}
    updates: list[ScoreUpdate] = []

    for cs in class_scores:
        cls = getattr(cs, "ambiguity_class", "") or ""
        update = compute_accuracy_update(cs, prior=priors.get(cls))
        unread = periods_unread.get(cls, 0)
        if unread:
            update = apply_decay(update, periods_unread=unread)
        updates.append(update)

    return RetrospectiveReport(
        window_id=window_id,
        seed=resolved_seed,
        population=len(runs),
        sampled=len(sample),
        sampled_run_ids=sampled_ids,
        updates=updates,
    )


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint for the scheduled workflow.

    Reads a JSON payload (runs + class scores) on stdin or from `--input`, and
    emits the report as JSON and Markdown. Kept dependency-free so the workflow
    needs no secret and no cloud access.
    """
    import argparse
    import sys

    ap = argparse.ArgumentParser(description="Run an accuracy retrospective (reports only).")
    ap.add_argument("--window-id", required=True)
    ap.add_argument("--input", help="JSON file; defaults to stdin")
    ap.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--markdown", action="store_true", help="emit Markdown instead of JSON")
    args = ap.parse_args(argv)

    raw = open(args.input).read() if args.input else sys.stdin.read()
    payload = json.loads(raw or "{}")

    class _CS:
        def __init__(self, d: dict):
            self.ambiguity_class = d.get("ambiguity_class", "")
            self.autopiloted = int(d.get("autopiloted", 0) or 0)
            self.autopilot_disagreements = int(d.get("autopilot_disagreements", 0) or 0)

        @property
        def autopilot_disagreement_rate(self):
            if self.autopiloted < 2:
                return None
            return self.autopilot_disagreements / self.autopiloted

    report = run_retrospective(
        window_id=args.window_id,
        runs=payload.get("runs", []),
        class_scores=[_CS(d) for d in payload.get("class_scores", [])],
        sample_size=args.sample_size,
        seed=args.seed,
    )

    print(report.to_markdown() if args.markdown else json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
