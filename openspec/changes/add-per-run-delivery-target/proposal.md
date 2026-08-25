# Per-run delivery target

## Why

The system has **two entry paths**, and only one of them can say where the work
should land.

| Path | Entry | What names the target today |
|---|---|---|
| **Dev PR** | a developer pushes; workflows fire | the repo they pushed to — inherited, correct |
| **PRD / change request** | `POST /api/run` | nothing. It is resolved from the team. |

`_resolve_target_repo(team_id, config)` reads
`delivery_overrides[team_id].target_repo`, falling back to
`config.github_default_target_repo`. That is a **one-target-per-team ceiling**.
It serves the dev-PR shape correctly and gives the PRD shape nowhere to speak.

A customer deploying this runs one orchestrator across many products. "Build
this and deliver it *there*" is the ordinary case for the PRD path, and today
"there" is a property of the team, permanently, decided at configuration time by
someone who is not the person submitting the run.

Two defects fall out of the same root, both instances of the pattern this
codebase keeps finding in itself — *the system knows something and does not
record it as a fact*:

1. **`github_default_target_repo` is undeclared.** It is read in
   `_resolve_target_repo` and defined nowhere in the config model. A team with no
   override hits an attribute that may not exist — a silent `AttributeError` at
   delivery time, after all the expensive work is done.
2. **The target is not queryable.** It survives only inside a prose f-string on
   the delivered ledger entry:
   `rationale=f"deliver_provider=github; target={target_repo}; ..."`. The system
   cannot answer *"which runs delivered to repo X"*, and the target is invisible
   in the run **before** delivery, when it still matters. For a product whose
   entire claim is auditable rows rather than recollection, *where the code went*
   must not be prose.

## What changes

- `target_repo` becomes a **first-class field on the run**, resolved once at run
  creation and visible from that moment — not discovered at the deliver stage.
- Resolution order: **explicit run request → team override → configured default**,
  with an explicit, actionable error when none resolves.
- `github_default_target_repo` is **declared** in the config model with a real
  default and validation, not an implicit attribute read.
- The delivered ledger entry carries `target_repo` as a **typed field**, so
  delivery destination is queryable alongside every other governed fact.
- Settings and the run view **show the resolved target and where it came from**
  (request / team / default), so an operator can see where a run will land
  before it lands there.

## Impact

- **Affected specs:** `delivery`, `ledger`
- **Affected code:** `apps/orchestrator/stages/deliver_github.py`,
  `apps/orchestrator/models.py`, `apps/orchestrator/config.py`,
  `packages/ledger-core/ledger_core/models.py`, the run API and settings surface
- **Backward compatible.** Existing per-team overrides keep working unchanged;
  the run-level field is optional and falls through to today's behaviour.
- **Docs:** `docs/onboarding-and-operation.md` gains the two entry paths
  explicitly — the journey doc currently describes the PRD path without saying
  where its output goes.

## Open questions

**Q1 — Does a PRD run *declare* its target, or *inherit* one it may override?**
Declaring is explicit and self-documenting but makes every run request longer and
every omission an error. Inheriting keeps the common case quiet but means the
target can be wrong by default and nobody notices until delivery. Leaning
inherit-with-override, because the dev-PR path already inherits and two different
rules for two paths is a worse story than one rule with an escape hatch.

**Q2 — Is the delivery target part of gate classification?**
This is a **governance** question, not plumbing, and it is the reason this change
is filed separately rather than patched in.

Delivering to a production repo and delivering to a sandbox are plausibly
different autonomy tiers. Today's autonomy matrix keys on
`(decision_class × team)`. If the target is governance-relevant, it keys on
`(decision_class × team × target)`, and precedent accumulated against a sandbox
must not silently grant autonomy against production.

Getting this wrong is expensive in a specific way: precedent is already being
recorded, and `accuracy_score` is now computed and promoted. Precedent gathered
under a target-blind key **cannot be retroactively split** by target. If the
answer is yes, the key must change before meaningful precedent accumulates.

**Q3 — May a run target a repo the team has no App installation on?**
Fail closed at run creation with a clear message, or fail at delivery? Failing
early is kinder; failing late is what happens today.

## Sequencing

Deliberately **after** `adopt-github-native-execution-substrate` reaches a
coherent stopping point. That change is 34/100 with every conceptual review
finding closed; interleaving a second architectural concern means neither lands
cleanly.

**Exception:** the two honesty defects above (undeclared config, unqueryable
target) do not prejudge Q1–Q3 and are safe to fix immediately under this
change's first tasks.
