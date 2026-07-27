# Talking points — governed AI development

_Speaker-facing. Not customer-facing. Read `CONCEPT-BRIEF.md` for what you send
them; this is what you say._

Every number here is from the live system and was verified, not estimated. If a
number moves, fix it here before the next conversation — a stale figure in this
file is worse than no figure, because you will say it with confidence.

---

## The 30-second version

> Your teams are adopting AI coding agents right now. GitHub tells you what
> changed, Purview tells you where data went, Foundry tells you what it cost.
> None of them tell you **why an agent chose what it chose, and which version of
> your policy governed that choice.** We make that one queryable record — and we
> make your standards the thing that enforces it, not a wiki nobody reads.

## The three claims, and the evidence for each

Lead with evidence. The category is saturated with assertions.

| Claim | Evidence you can show live |
|---|---|
| Policy actually binds | **12 runs refused at the merge gate**, each citing `security/v0.1.0/PHI-001`; one had 38 blockers |
| Invariants actually hold | **38 PHI decisions, 38 by a human, 0 by the agent** — the autonomy matrix cannot open that class |
| The system actually learns | **16 precedent pairs** on the lineage graph: a human ruling, and the later agent decision that reused it |

## The reframe that wins the room

When they see a wall of blocked runs, the instinct is *"your AI is unreliable."*
Get there first:

> "Twelve of those did not fail. They were **refused** — the agent wrote patient
> identifiers into a log line and the standards layer stopped the merge and named
> the rule. A pipeline that never blocks anything isn't a safe pipeline, it's an
> unmeasured one."

Then show the run card citing `PHI-001`. That single screen is the product.

Corollary worth saying out loud, because it demonstrates you thought past the
demo: *"That's why the dashboard says 'blocked by policy', not 'failed'. Retry
is right for a defect and wrong for a policy block — retrying re-runs the same
generator against the same rule and blocks again."*

## The credibility move: volunteer a limit

Do this early, unprompted. It buys everything you say afterwards.

> "We shipped a rule marked BLOCK with no scanner behind it — `SBOM-001`
> reported clean because nothing was ever scanned. We found it, fixed it, and
> bundles now require any BLOCK rule to declare the mechanism that enforces it.
> The class of error matters more than the instance: **an audit artifact
> pretending to be a control** is the failure mode to watch for, in our product
> and in everyone else's."

Then the four standing caveats, stated plainly: identity not enforced end-to-end
(auth is off on the demo, team boundaries are advisory); delivery not wired for
every path; precedent thin at 16 pairs; the 45% autonomy number needs the
disagreement rate beside it to mean anything.

## The question that separates us from the field

If you only land one differentiator, land this:

> "Every vendor will show you an autonomy percentage. Ask them the follow-up:
> **when your agent decided alone, how often was it wrong?** If they can't
> answer, the autonomy number measures how much the agent was *allowed* to do —
> not whether it should have been. A rising autonomy rate with a rising
> disagreement rate looks like success on every chart and loses your trust in one
> incident."

Ours answers it, and refuses to answer when the sample is too small: below the
floor a class returns `INSUFFICIENT`, never 0%. Unscored decisions return
`UNSCORED` rather than being counted as the agent having been right.

## Where the ideas come from — say the quiet part

> "Standards are authored per department and **pinned per team**, so security
> owns security rules and a team adopts a version on a canary. Thresholds live
> in those versioned bundles, not in our code — changing what counts as
> acceptable divergence is a governed standards change with a canary week, not a
> redeploy by us."

That is the line that turns this from a tool into an operating model.

## Objection handling

**"We already have branch protection / CodeQL / CODEOWNERS."**
> Good — keep them, we don't replace them. Those enforce *what* passes. They
> can't tell you which version of your PHI policy was in force when an agent
> decided to log an identifier, or that the same question was ruled on by a human
> three weeks ago. Gates are a pass/fail bit; this is the reasoning behind it.

**"Isn't this just prompt engineering with extra steps?"**
> A prompt is advice. A BLOCK rule with a declared mechanism is a control. We
> deliberately refuse to let a model be the mechanism — if the only thing
> checking the agent is another model asked "did you overstep?", nothing is
> checking it.

**"How is this different from an audit log?"**
> An audit log records what happened. This records *why*, bound to the rule
> version in force, and then **reuses** that reasoning — a human ruling becomes
> precedent the agent applies next time. The log is a byproduct; the loop is the
> product.

**"What happens when your rules are wrong?"**
> Two loops. Fast: a human ruling becomes precedent immediately, so the next run
> needs one fewer human. Slow: the doctor detects drift and opens a
> standards-change proposal for your committee, canaried on one team for a week
> before it goes wide. Neither loop lets the system quietly relax a PHI rule.

## What NOT to do

- **Don't demo the economics trend chart.** Precedent hits are 0 on 10 of 11
  days. It's honest but it reads as "precedent never gets reused." Use the
  lineage graph instead — same idea, real data.
- **Don't promise end-to-end delivery.** Lead with the audit story. Some runs
  end at `Delivery blocked — synthetic provider output`.
- **Don't quote the autonomy number alone.** It's the number we tell people to
  be suspicious of. Quoting it unaccompanied undercuts our own argument.
- **Don't call blocked runs failures.** You will confuse the one thing you came
  to prove.

## Numbers, current as of the last verification

| Figure | Value |
|---|---|
| Ledger entries | 229 (216 cite the autonomy policy that governed them) |
| Rule-version binding on ledger rows | `bundle_refs` empty — **not yet**; live at the gate, not on the row |
| Runs blocked by policy | 12, all citing `security/v0.1.0/PHI-001` |
| Largest single block | 38 blockers on one run |
| PHI decisions / autopiloted | 38 / **0** |
| Precedent pairs | 16 |
| Autonomy earned | 45% — never quote without the disagreement rate |
| Standards bundles | 5 across security · privacy · architect · finops |
