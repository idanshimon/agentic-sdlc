# Tasks: config editing plane

## 1. Agent→bundle wiring (#2)

- [x] 1.1 `agent_bundles.py` — parse `.github/agents/*.agent.md` frontmatter
- [x] 1.2 Validate declared subscriptions against real `standards-bundles/<dept>` dirs (strip inline comments, reject prose like `all (read-only)`)
- [x] 1.3 `bundles_for_stage(stage)` mapping stage → agent → bundles
- [x] 1.4 `LedgerEntry.bundle_refs` field on the orchestrator model
- [x] 1.5 Stamp `bundle_refs` at the autopilot decision write site
- [x] 1.6 Stamp `bundle_refs` at the per-card approve write site
- [x] 1.7 Tests: parser, validation, stage mapping (9 tests)

## 2. Governed PR write-back core (#3)

- [x] 2.1 `config_writer.py` with `write_config_pr(rel_path, content, commit_message, pr_title, ...)`
- [x] 2.2 `_validate_path` allowlist (`.github/agents`, `standards-bundles`, `prompts`); refuse absolute + `..` escapes
- [x] 2.3 GitHub REST flow: GET base ref → POST branch → GET file sha → PUT contents → POST pull
- [x] 2.4 Token resolution `CONFIG_GH_TOKEN` / `GH_TOKEN` / `GITHUB_TOKEN`; clean 422 when absent
- [x] 2.5 `FileNotFoundError → ConfigWriteError` mapping (no 500 from a missing binary)
- [x] 2.6 Tests: path boundary, dry-run, no-token degradation, mocked REST happy path (11 tests)

## 3. Save endpoints

- [x] 3.1 `POST /api/config/agents/save`
- [x] 3.2 `POST /api/config/bundles/save` (PR-only)
- [x] 3.3 `POST /api/config/prompts/save` (next-version draft)
- [x] 3.4 `POST /api/config/reload` (agents/prompts only)
- [x] 3.5 Endpoint tests in dry-run mode (8 tests)

## 4. UI editors

- [x] 4.1 `VersionedEditor.onPullRequest` hook — local save + open PR, honest toasts
- [x] 4.2 Agents editor wired to `saveAgentConfig` (was localStorage)
- [x] 4.3 Bundles page "Edit rules" editor (was read-only) with governance banner
- [x] 4.4 Prompt Library in-app editor (next-version draft → PR)
- [x] 4.5 `orchestrator.ts` client methods: save{Agent,Bundle,Prompt}Config + reloadConfig

## 5. Deploy + verify

- [x] 5.1 `GH_TOKEN` Container App secret on the orchestrator
- [x] 5.2 Verify a real PR opens from a save (proven: PR opened + closed via REST)
- [x] 5.3 Orchestrator + UI deployed; endpoints return real PR URLs or honest 422
- [x] 5.4 Full suite green (orchestrator + vitest)
