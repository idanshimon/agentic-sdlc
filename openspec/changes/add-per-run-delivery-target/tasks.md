# Tasks: per-run delivery target

## 1. Honesty fixes (safe now — do not prejudge Q1-Q3) — DONE

> Found while fixing 1.1: `github_app_installation_id` was ALSO undeclared, read the same way by
> `_resolve_installation_id`. Both GitHub settings were phantoms — `Settings` had no GitHub fields
> at all. Declared both, with no built-in default, matching the `storage_account_url` posture
> already in the file: the reference repo stays tenant-neutral and an unset value fails loudly
> rather than delivering generated code to a plausible-looking repository nobody chose.

- [x] 1.1 Declare `github_default_target_repo` in the orchestrator config model with a real
      default and validation, replacing the implicit attribute read in `_resolve_target_repo`
- [x] 1.2 Raise an explicit, actionable error when no target resolves — naming the team, the
      resolution order tried, and the config key to set — instead of `AttributeError` at the
      deliver stage after all expensive work is done
- [x] 1.3 Add `target_repo` as a typed field on `LedgerEntry`, so delivery destination is
      queryable rather than embedded in the `rationale` f-string
- [x] 1.4 Populate it at the deliver site; keep the prose rationale for humans
- [x] 1.5 Backward-compat: entries without `target_repo` remain valid and are reported as
      unknown, never as empty-string
- [x] 1.6 Test: a team with no override and no default fails at RUN CREATION, not at deliver

## 2. Resolve the open questions (blocked on Idan)

- [ ] 2.1 **Q1** — declare vs inherit for the PRD path
- [ ] 2.2 **Q2** — is the delivery target part of gate classification?
      **Blocks 3.x.** Precedent is already accumulating and `accuracy_score` is now promoted;
      a target-blind precedent key cannot be retroactively split by target.
- [ ] 2.3 **Q3** — fail closed at run creation on a missing App installation, or at delivery?

## 3. Per-run target (after Q1-Q3)

- [ ] 3.1 `target_repo` as a first-class field on the run, resolved at creation
- [ ] 3.2 Resolution order: explicit run request -> team override -> configured default
- [ ] 3.3 Record the PROVENANCE of the resolution (request / team / default), not just the value
- [ ] 3.4 `POST /api/run` accepts an optional target
- [ ] 3.5 Run view and settings show the resolved target and where it came from
- [ ] 3.6 Test: the two entry paths (dev PR inherit, PRD declare) both land correctly

## 4. Docs

- [ ] 4.1 `docs/onboarding-and-operation.md` — state the two entry paths explicitly. The journey
      doc currently describes the PRD path without saying where its output goes.
- [ ] 4.2 Document the required delivery-target ref protection (6d.2a from the substrate change):
      what a customer must configure, and `scan_ref_protection` to verify they did
