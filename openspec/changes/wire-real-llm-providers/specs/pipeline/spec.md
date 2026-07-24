# Spec delta: wire-real-llm-providers / pipeline

## ADDED Requirements

### Requirement: The pipeline MUST support keyless model-provider auth
The Azure OpenAI provider MUST support keyless authentication via Managed
Identity when no API key is configured, using a credential scoped to Cognitive
Services. API keys MUST NOT be required to run real model calls.

#### Scenario: real model call with no API key
- **GIVEN** the orchestrator has a Managed Identity granted the OpenAI User role
- **AND** no `AOAI_API_KEY` is set
- **WHEN** a stage invokes the AOAI provider
- **THEN** the call MUST authenticate with a Managed-Identity bearer token
- **AND** the model response MUST be used as real (non-synthetic) stage output

### Requirement: Live-provider enforcement MUST be independent of the auth profile
A dedicated flag MUST force fail-closed behavior on provider errors without
requiring the production execution profile, so a demo can run real providers while
keeping `AUTH_MODE=disabled`.

#### Scenario: real providers with demo auth
- **GIVEN** `REQUIRE_LIVE_PROVIDERS` is enabled and `AUTH_MODE=disabled`
- **WHEN** a provider call fails after bounded retry
- **THEN** the stage MUST fail closed with no synthetic fallback
- **AND** the demo principal MUST still be permitted (auth is not locked down)
