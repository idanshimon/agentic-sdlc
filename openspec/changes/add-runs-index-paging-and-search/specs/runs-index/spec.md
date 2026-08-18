# runs-index — paging, search and honest counts

## MODIFIED Requirements

### Requirement: The runs index MUST be navigable beyond the first page

The runs list endpoint MUST accept an `offset` parameter and MUST return the
requested page, so every run in the scanned window is reachable from the UI.

#### Scenario: The next page returns different runs

- **GIVEN** more runs exist than fit in one page
- **WHEN** the client requests the same limit at the next offset
- **THEN** a full page of runs MUST be returned
- **AND** it MUST share no run with the previous page

#### Scenario: Paging covers every run exactly once

- **GIVEN** a set of runs spanning several pages
- **WHEN** every page is requested in turn
- **THEN** each run MUST appear exactly once across the collected pages

#### Scenario: Newest-first order holds across page boundaries

- **GIVEN** two consecutive pages of runs
- **WHEN** their items are concatenated in page order
- **THEN** the result MUST remain sorted newest-first

#### Scenario: An offset past the end is empty, not an error

- **GIVEN** an offset beyond the number of matching runs
- **WHEN** the page is requested
- **THEN** the response MUST succeed with an empty item list
- **AND** it MUST still report the true total

### Requirement: The runs index MUST report a total distinguishable from the page size

The response MUST include the number of runs matching the active filters, not
only the number returned in the current page.

A count that reports only the page size cannot be distinguished from a complete
census, so an operator cannot tell a slice from the whole.

#### Scenario: Total exceeds the page when more runs exist

- **GIVEN** more matching runs than the page size
- **WHEN** the first page is requested
- **THEN** the item count MUST equal the page size
- **AND** the reported total MUST equal the number of matching runs

#### Scenario: A saturated scan window is reported as a floor

- **GIVEN** more runs in the container than the scan window can read
- **WHEN** runs are listed
- **THEN** the response MUST report that the result is truncated
- **AND** the UI MUST NOT present the total as a complete count

#### Scenario: An unsaturated window is not marked truncated

- **GIVEN** a container whose runs all fit inside the scan window
- **WHEN** runs are listed
- **THEN** the response MUST NOT report truncation

### Requirement: Run search MUST evaluate the whole window, not the current page

Free-text search MUST be applied server-side across the scanned window before
paging, and MUST NOT be implemented by filtering only the rows already returned
to the client.

Filtering the fetched page would report an empty result for a run that exists
beyond it. An empty result that looks authoritative is worse than an error,
because the operator concludes the run does not exist.

#### Scenario: A match beyond the first page is found

- **GIVEN** a run matching the query that sits beyond the first page
- **WHEN** that query is searched
- **THEN** the matching run MUST be returned

#### Scenario: The total reflects matches, not the corpus

- **GIVEN** a search matching exactly one run out of many
- **WHEN** the search is performed
- **THEN** the reported total MUST be the number of matches

#### Scenario: A non-matching search returns nothing

- **GIVEN** a query matching no run
- **WHEN** the search is performed
- **THEN** the result MUST be empty
- **AND** it MUST NOT fall back to returning unfiltered runs

#### Scenario: An empty search result is distinct from an empty corpus

- **GIVEN** runs exist but none match the active search
- **WHEN** the list renders
- **THEN** it MUST indicate that no runs matched the search
- **AND** it MUST NOT present the first-run onboarding state
