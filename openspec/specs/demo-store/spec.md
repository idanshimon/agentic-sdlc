# demo-store Specification

## Purpose
TBD - created by archiving change fix-demo-store-renderer-oom. Update Purpose after archive.
## Requirements
### Requirement: Demo run store SHALL memoize JSON.parse by raw-string identity

The demo run loader MUST cache the most recently parsed store object keyed
on the raw localStorage string. Subsequent reads with an unchanged raw
string MUST return the cached object without invoking `JSON.parse`. Any
write through `saveStore` or `clearDemoRuns` MUST invalidate or refresh
the cache so that the next read sees the new state.

#### Scenario: Repeated reads with no writes parse only once

- **GIVEN** the demo run store contains one or more runs
- **WHEN** `listDemoRuns()` is called three times in succession with no
  intervening writes
- **THEN** `JSON.parse` is invoked at most once across the three reads

#### Scenario: A write between reads forces a re-parse

- **GIVEN** `listDemoRuns()` has been called once and the cache is primed
- **WHEN** the underlying localStorage value is replaced with a different
  serialized store
- **AND** `listDemoRuns()` is called again
- **THEN** the new run is reflected in the returned list

#### Scenario: Corrupted JSON does not throw

- **GIVEN** localStorage holds a malformed JSON string for the demo store
  key
- **WHEN** `listDemoRuns()` is called
- **THEN** the call returns an empty array without raising

### Requirement: Demo run store SHALL cap retained runs at 10 via LRU eviction

The store MUST retain at most ten demo runs at rest in localStorage.
On every write that would exceed the cap, the oldest runs by
`updated_at` MUST be evicted before serialization. When the browser
rejects a write with `QuotaExceededError`, the store MUST drop the
oldest half of runs and retry the write once before giving up silently.

#### Scenario: Starting more than ten runs evicts the oldest

- **GIVEN** an empty demo store
- **WHEN** `startDemoRun("vitals")` is invoked fifteen times in rapid
  succession
- **THEN** `listDemoRuns()` returns at most ten runs
- **AND** the ten most recently started runs are the survivors

### Requirement: clearDemoRuns SHALL wipe both localStorage and the in-process cache

The `clearDemoRuns` operation MUST remove the localStorage key AND reset
the in-process memoization cache so that subsequent reads in the same
tab observe the empty state immediately.

#### Scenario: Reading after clear returns empty

- **GIVEN** the demo store contains at least one run AND `listDemoRuns()`
  has been called to prime the cache
- **WHEN** `clearDemoRuns()` is invoked
- **THEN** the next `listDemoRuns()` returns an empty array
- **AND** the next `getDemoRun(<previous-id>)` returns undefined
- **AND** the next `listDemoLedgerEntries()` returns an empty array

### Requirement: Topbar SHALL expose a one-click Reset Demo affordance when Demo Mode is active

When `NEXT_PUBLIC_DEMO_MODE=1` is set, the topbar MUST render a Reset
Demo button adjacent to the DEMO MODE pill. Activation MUST prompt the
operator with a confirmation, on confirm MUST call `clearDemoRuns`,
display a toast, and reload the page. The button MUST carry a
descriptive `title` and `aria-label`.

#### Scenario: Reset button clears state and reloads

- **GIVEN** Demo Mode is active and the demo store holds at least one run
- **WHEN** the operator activates the Reset button and confirms the prompt
- **THEN** `clearDemoRuns` is invoked
- **AND** a success toast is shown
- **AND** the page is reloaded shortly after

