# Proposal: security bundle v0.2.0 — enterprise control coverage

> **Status:** DRAFT (proposed)
> **Capability:** standards-bundles (security)
> **Bundle:** `standards-bundles/security/v0.2.0/rules.yaml`
> **Supersedes:** `security/v0.1.0` (remains pinned until this is approved and rolled)
> **Reviewers required:** per `security/v0.1.0` roster — `@security-leadership`

## Why

`security/v0.1.0` covers the healthcare-regulated core well: five PHI rules, two
secret rules, SBOM, and an auth-resolution gate. Every rule carries a rationale,
enforcement surface, and test cases. That is a solid base and none of it is
wrong.

It is, however, scoped to *data handling*. An enterprise security review asks a
broader set of questions that the bundle currently cannot answer, so the
pipeline cannot enforce them and the ledger cannot evidence them:

1. **Identity and access are unaddressed.** `SECRET-002` requires Managed
   Identity for connection strings, but nothing constrains what that identity is
   *allowed to do*. Over-privileged role assignment is the most common finding
   in enterprise reviews and is invisible to the current rule set.
2. **Supply chain stops at SBOM generation.** `SBOM-001` requires an SBOM to be
   produced; nothing requires it to be *acted on*. A generated SBOM with a
   critical CVE currently passes.
3. **Network posture is unconstrained.** No rule prevents a service being
   exposed on a public endpoint, which is the single control most likely to be
   raised by a regulated customer's architecture review board.
4. **No dependency provenance.** Nothing prevents an agent adding an unpinned or
   unvetted third-party package during codegen — the highest-frequency path by
   which an agentic pipeline introduces risk.
5. **Cryptography is asserted, not bounded.** `PHI-002` mandates TLS 1.2+ for
   PHI in transit; there is no floor for non-PHI traffic and no constraint on
   algorithm choice.

These are not hypothetical gaps. They are the standard sections of an enterprise
security questionnaire, and an agentic SDLC that claims decisions are governed
should be able to *show the rule that governed them*.

## What changes

A new `security/v0.2.0` bundle: all nine `v0.1.0` rules carried forward
unchanged, plus seven new rules. Strictly additive — no existing rule id,
severity, or pattern is modified, so no currently-passing artifact starts
failing on a rule it already satisfied.

| New rule | Severity | Gap closed |
|---|---|---|
| `IAM-001` | BLOCK | Managed Identity must hold least-privilege built-in roles; `Owner`/`Contributor` at subscription scope is refused |
| `IAM-002` | WARN | Role assignments must be scoped to a resource group or narrower, never subscription-wide |
| `SUPPLY-001` | BLOCK | SBOM must be *scanned*; critical/high CVEs block the build rather than merely being listed |
| `SUPPLY-002` | BLOCK | Dependencies must be version-pinned; no floating tags or unpinned installs |
| `NET-001` | BLOCK | Services handling PHI must not expose a public ingress; private endpoint or VNet-internal only |
| `NET-002` | WARN | Egress should be explicitly allow-listed rather than default-open |
| `CRYPTO-001` | BLOCK | TLS 1.2+ floor for *all* traffic, and deprecated algorithms (MD5, SHA-1, DES, RC4) are refused |

### Why these severities

`BLOCK` is reserved for controls where a violation is unambiguous and
mechanically detectable — a subscription-scoped `Owner` assignment, an unpinned
dependency, a public ingress on a PHI service. `WARN` is used where the correct
answer is context-dependent and a human should judge: egress allow-listing is
right for most services and wrong for a deliberate public API, so blocking it
would train operators to route around the bundle.

That distinction matters more than the rule count. A bundle that blocks
everything gets disabled.

### Pinning and rollout

`PINS.yaml` is **not** changed by this proposal. Every team stays on
`security: v0.1.0` until the change is approved. On approval, the intended
rollout is:

1. Pin one canary team to `v0.2.0` for 7 days.
2. Pipeline Doctor watches block-rate and false-positive metrics.
3. Auto-PR opens to either promote all teams or revert the canary.

This is the canary path already described in `PINS.yaml`; this proposal does not
invent new rollout machinery.

## Impact

- **Bundle:** new directory `standards-bundles/security/v0.2.0/`. `v0.1.0` is
  untouched and remains the pinned version for every team.
- **CI:** `scripts/enforce_bundles.py` picks up the new rules automatically via
  `ci_checks_default: true`; each new pattern rule ships with test cases so the
  enforcement lane can verify it matches its own fixtures.
- **Agents:** `.github/agents/*.agent.md` subscribing to `security` inherit the
  new rules only once their team's pin moves. No agent file changes required.
- **Runtime:** none until a pin moves. Approval alone changes no behavior.

## Risks

- **False positives on `SUPPLY-002`.** Lockfile-managed ecosystems express pins
  differently; the rule is scoped to direct install invocations rather than
  attempting to parse every manifest format. Canary week is specifically to
  measure this.
- **`NET-001` may be too broad for internal-only tooling.** Mitigated by scoping
  the rule to services classified as PHI-handling rather than all services.
- **Rule-count inflation.** Seven new rules is a ~78% increase. The canary
  metrics should be read as "did block-rate rise without a matching rise in real
  findings" — if so, the answer is to demote rules to WARN, not to widen the
  exceptions.
