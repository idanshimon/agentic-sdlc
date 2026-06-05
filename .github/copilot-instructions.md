# Copilot instructions for this repository

Read `AGENTS.md` at the repo root first. It is the canonical source.

## Conventions specific to this repo

- **Python**: 3.11, FastAPI, Pydantic v2. Format with `ruff format`. Test with `pytest`.
  Import order: stdlib → third-party → first-party. Never use bare `except:`.
- **TypeScript**: Node 20, strict mode on, ES2022 target. Format with `prettier`.
  Test with `vitest` (UI) and `vitest`/`tsx` for the MCP server.
- **OpenSpec**: every multi-file change proposal lives at
  `openspec/changes/<slug>/{proposal.md,tasks.md,specs/<capability>/spec-delta.md}`.
  Use `openspec validate <slug> --strict` before merging.
- **Tests-first**: write the failing test, watch it fail, write the minimal code,
  watch it pass. See `software-development/test-driven-development` skill if available.

## Style

- Terse code comments. No "AI commentary" comments like `# This function does X`.
- Function/class docstrings use Google style (Args:, Returns:, Raises:).
- Error messages should include actionable context, not just "operation failed".

## Commit messages

- Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Subject ≤72 chars, body explains WHY, not WHAT.
- Reference the OpenSpec change slug in the body when applicable: `Refs: openspec/changes/<slug>`.

## Plan Mode

For any change touching multiple stages, the ledger schema, or any standards bundle,
default to Plan Mode. Ask clarifying questions before writing code.
