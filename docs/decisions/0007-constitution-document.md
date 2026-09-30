---
doc_type: adr
id: 0007
status: accepted
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~750 tokens
---

# ADR 0007 — A constitution document, checked but not hard-enforced

Like ADR 0001–0006, this documents a decision about *this framework's
own* tooling (kept as a worked example).

## Context

This framework had no single artifact for non-negotiable, cross-cutting
principles distinct from `CLAUDE.md` (project-specific glue + index)
or an ADR (a point decision, immutable once accepted). GitHub Spec Kit
fills exactly this role with `.specify/memory/constitution.md`: a
versioned document every spec/plan is checked against before
proceeding, with an explicit amendment procedure rather than silent
edits. Raised directly by comparing this framework against Spec Kit/
OpenSpec/BMAD for large-scale maturity.

## Options considered

- **Fold principles into `CLAUDE.md` directly.** Rejected —
  `CLAUDE.md` is deliberately scoped to project glue and the doc index
  (ADR 0001); nothing in the pipeline currently checks a diff against
  it for compliance, and folding in principles would blur "what is
  this document for" the same way ADR 0001 already warned against for
  Skills vs. commands.
- **One more ADR, titled "Constitution."** Rejected — ADRs are point
  decisions, immutable once accepted (design principle 3); a
  constitution is meant to be amended over the project's life under
  its own governance rule. Different shape of document, doesn't fit
  the ADR contract.
- **Standalone `docs/constitution.md`, versioned (semver), checked by
  the pipeline but not hard-blocked (chosen).** Own frontmatter
  (`version`, `ratified`, `last_amended`), prefilled with a universal
  secure-coding baseline plus an explicit placeholder for
  project-specific principles.

## Decision

`docs/constitution.md`, loaded before `/spec`, `/plan`,
`coder`/`quickfix`, and `reviewer`. Amendments bump `version`/
`last_amended` in the same edit; `constitution_amendment_check.py`
nudges (never blocks — see its own docstring) when content changes
without that. Referenced from `CLAUDE.md`'s Index and conventions.

## Rationale

Matches Spec Kit's own proven pattern instead of inventing a new
primitive. Keeps this framework's existing "hard guard vs. nudge"
split (`adr_immutability_guard.py` blocks because ADR status is
binary and truly frozen; a constitution is expected to change over
time under its own rule, so a hard block would fight legitimate
amendments the same way it would if applied to `CLAUDE.md` itself —
nudge fits the posture `context_budget_check.py`/`frontmatter_check.py`
already established for exactly this kind of "should be true, isn't
worth blocking over" check).

## Consequences

- Decorative unless the stages that are supposed to check it actually
  say so — `/spec`, `/plan`, `coder`/`quickfix`, and `reviewer`'s own
  bodies now reference it explicitly, not left implicit.
- The prefilled Core Principles are a generic secure-coding baseline
  (secrets, logging, input validation, least privilege, dependency
  vetting), not architecture opinions — this is a deliberate exception
  to this framework's "no default architecture pattern shipped"
  stance (root `README.md`): secrets/security hygiene is close to
  universal across projects, unlike monolith-vs-microservices or
  module layout, so shipping a real default here doesn't bake in one
  project's structural opinion the way a prefilled architecture doc
  would.
- No hard technical enforcement exists — an agent can still violate a
  principle in the moment; catching it depends on `reviewer`/`coder`
  actually checking, the same trust model the rest of this pipeline
  already runs on for architecture docs.

## References

`docs/constitution.md`, `.claude/hooks/constitution_amendment_check.py`,
`docs/decisions/0001-tooling-agents-commands-skills.md`
