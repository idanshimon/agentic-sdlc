# bundle-ci-enforcement — DESCRIBES-vs-COMMITS semantics

## MODIFIED Requirements

### Requirement: CI rules MUST be able to distinguish describing a violation from committing one

The enforcer MUST NOT report a violation on a line where every occurrence of the
rule's `context_pattern` falls inside a string literal, when that rule declares
`quoted_literal_exempt: true`.

The field MUST default to `false`, so a rule's blast radius never changes without
an explicit, reviewable bundle edit.

The check MUST be evaluated on the position of the **context (sink) pattern**,
never on the position of the primary `pattern` match. In a genuine violation the
matched token is typically inside a quoted format string, so token position
carries no signal about whether the line performs the prohibited act.

#### Scenario: A real logging call is reported even when the rule is exempt-enabled

- **GIVEN** a rule with `quoted_literal_exempt: true` whose `context_pattern`
  matches logging sinks
- **WHEN** the enforcer scans the line `logger.info(f"patient {MRN} updated")`
- **THEN** a violation MUST be reported, because the sink `logger.info(` appears
  as bare code

#### Scenario: A quoted example of a violation is not reported

- **GIVEN** the same rule
- **WHEN** the enforcer scans the line `text: 'logger.info(f"patient {MRN}")',`
- **THEN** no violation is reported, because every sink occurrence lies inside a
  string literal

#### Scenario: A rule without the flag is unaffected

- **GIVEN** a rule that does not declare `quoted_literal_exempt`
- **WHEN** the enforcer scans a line whose sink is inside a string literal
- **THEN** a violation MUST be reported, exactly as before this change

#### Scenario: An unterminated string literal fails closed

- **GIVEN** a rule with `quoted_literal_exempt: true`
- **WHEN** the enforcer scans a line containing an unterminated quote, such that
  a sink would appear to be inside a literal that never closes
- **THEN** the sink MUST be treated as bare code and a violation MUST be
  reported, so that quote-stuffing cannot evade the gate

#### Scenario: A mixed line with any bare sink is reported

- **GIVEN** a rule with `quoted_literal_exempt: true`
- **WHEN** a line contains both a quoted mention of a sink and a real bare sink,
  such as `x = "harmless"; logger.info(f"patient {MRN}")`
- **THEN** a violation MUST be reported, because at least one sink is bare

#### Scenario: A rule with no context_pattern is never exempted

- **GIVEN** a rule that declares `quoted_literal_exempt: true` but no
  `context_pattern`
- **WHEN** the enforcer scans any matching line
- **THEN** a violation MUST be reported, because there is no identifiable act
  whose position can be checked
