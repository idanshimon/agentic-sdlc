# Design: enterprise production hardening

## Trust model

### Principal

Every request resolves to a typed principal:

- `subject`: stable user/workload identifier
- `kind`: `human | workload`
- `roles`: operator, persona_owner, standards_reviewer, release_manager, admin, github_workload
- `teams`: authorized team IDs
- `source`: disabled, trusted_headers, entra

The application never trusts actor/team fields from mutation bodies. Compatibility fields may remain accepted temporarily but are ignored when authentication is active.

### Authentication modes

- `disabled`: local tests/development only; creates an explicit development principal. Production startup refuses this mode.
- `trusted_headers`: for Container Apps EasyAuth/reverse proxy; parses signed/validated upstream identity headers.
- `entra`: validates bearer JWT issuer, audience, signature, expiry, and claims.

Authorization lives in route dependencies and domain functions, not UI state.

## Execution profiles

- `production`: provider failures terminate the stage/run; no synthetic output.
- `demo`: synthetic fallback permitted and visibly stamped.
- `test`: deterministic injectable providers permitted.

`CallResult` gains provenance fields (`synthetic`, `provider`, `error_category`). Run state aggregates `contains_synthetic_output`. Deliver refuses when true.

## Durable state machine foundation

RunState gains:

- `version`
- `stage_cursor`
- `pending_gate`
- `gate_version`
- `checkpoint_status`
- `lease_owner`, `lease_expires_at`
- durable PRD input reference/content hash
- artifact manifest reference

A transition command performs compare-and-set on expected version and records one immutable event. In-memory queues and `asyncio.Event` wake local workers but do not decide truth.

Resume algorithm:

1. Load nonterminal runs with expired/no lease.
2. Acquire lease atomically.
3. Validate last checkpoint and required inputs/artifacts.
4. Resume the next incomplete stage or wait on a durable pending gate.
5. Release/renew lease as work proceeds.

## Command idempotency

Mutation commands require `Idempotency-Key` and, where stateful, `If-Match`/expected version. A durable command record maps `(principal, route, idempotency_key)` to request hash and result. Replays return the original result; key reuse with different payload fails.

Gate decisions are immutable events. Effective current decision is derived by card ID and sequence/version. Changes explicitly supersede prior decisions.

## Artifact integrity

CodeGen creates a manifest:

```json
{
  "files": [{"path":"src/main.py","sha256":"...","kind":"implementation"}],
  "producer_stage":"codegen",
  "run_id":"..."
}
```

Review consumes the manifest and records reviewed hashes. Deliver accepts only the same manifest/hashes. A mismatch fails delivery and writes audit evidence.

## Autonomous review dispatch

`POST /api/review-loops` accepts repo, PR number, and head SHA from an authenticated GitHub workload. It computes deterministic `loop_id = sha256(repo|pr|head_sha)`, returns an existing result on replay, fetches exact PR-head files, and runs the existing bounded controller.

Structured loop hops include loop ID, repo, PR, SHA, attempt, tier, verdict reference, disposition, and GitHub URLs. Check-run/comment publication is best-effort evidence; merge remains server-side and only after policy permits it.

## SSE recovery

The client maintains reconnect attempt state. Error closes the old source and schedules a state increment with capped exponential backoff and jitter; the effect creates a new EventSource. Polling remains fallback. Event IDs support dedup/replay when the server emits them.

## GitHub enforcement boundary

Repository files supply CODEOWNERS, Actions, and setup workflow. A verification script reads GitHub APIs and emits pass/fail/unknown for required checks, rulesets, environment protection, action policy, scanning, and runner posture. The repo does not claim these controls are active from files alone.

## Assurance model

A final decision exposes independent dimensions:

- deterministic policy
- build/tests
- dependency/SBOM/secrets/SAST
- semantic cited review
- mandatory human requirements

Overall disposition is the most restrictive result. No generic PASS masks an unexecuted dimension.
