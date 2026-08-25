# Spec delta: ship-operator-grade-pipeline-workflow / ledger-insights-ui-decisions

## ADDED Requirements

### Requirement: Decisions page MUST surface prompt chain attribution on every entry

Every ledger entry rendered on `/decisions` (both card view and table-row drilldown) MUST display a `<PromptChainBadge>` showing which prompt produced the decision. The badge MUST be clickable, routing to the `/prompts` catalog page.

The badge MUST support three render variants:
- `inline` — compact one-liner for dense layouts
- `card` — multi-line for DecisionCard footer (prompt_id, version, owner persona color-coded, git_sha truncated, matched scope name)
- `full` — visual chain walk (team → persona → global) with matched scope highlighted and rejection reasons inline for unmatched scopes

#### Scenario: decision card surfaces chain badge with click-through

- **GIVEN** a decision entry written after Phase 2.6 with `prompt_resolution_path` populated
- **WHEN** the operator views the entry on `/decisions`
- **THEN** the DecisionCard MUST render the chain badge in card variant below the bundle citations
- **AND** the badge MUST display the matched prompt_id, version, owner persona, git_sha, and matched scope name
- **AND** clicking the badge MUST navigate to `/prompts`

#### Scenario: expanded table row shows full inheritance walk

- **GIVEN** the decision-table view expanded for a row with chain pinned
- **WHEN** the operator inspects the "Prompt resolution" section in the drilldown
- **THEN** the panel MUST render every scope the resolver considered (team, persona, global)
- **AND** the matched scope MUST be visually highlighted (success-color ring + bold prompt_id)
- **AND** unmatched scopes MUST display their rejection reason as italic text

### Requirement: Decisions page MUST support filtering by team

The `<DecisionTable>` FilterBar MUST include a Team filter dropdown alongside Stage / Actor / PHI / Runtime kind / Has-teaching-signal filters. The dropdown options MUST be derived from the distinct `team_id` values in the current entry set (no hardcoded team list).

Selecting a team MUST filter the visible rows to only entries belonging to that team. Clear filters MUST reset the team filter to "" (all teams).

#### Scenario: team filter scopes the visible decisions

- **GIVEN** a `/decisions` view with entries from both `cardiology` and `team-demo` teams
- **WHEN** the operator selects `cardiology` in the Team filter dropdown
- **THEN** the table MUST render only entries where `team_id === "cardiology"`
- **AND** the filter count badge MUST increment by 1
- **AND** clicking "Clear filters" MUST reset the team filter and restore all rows
