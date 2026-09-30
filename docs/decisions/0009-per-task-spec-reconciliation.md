---
doc_type: adr
id: 0009
status: accepted
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~800 tokens
---

# ADR 0009 — `reviewer` reconciles spec vs. diff per task, not as a separate pass

Like ADR 0001–0008, this documents a decision about *this framework's
own* tooling (kept as a worked example).

## Context

Nothing recorded whether an implemented task actually matched what its
spec claimed, once the code existed — the "spec drift" problem GitHub
Spec Kit (`/speckit.reconcile`) and OpenSpec (`/opsx:sync`) both added
standalone commands for. Raised directly by comparing this framework
against both for large-scale maturity. `reviewer` already reads a
task's diff per coder-tier task inside `/implement`'s orchestration
mode (ADR 0004) — the cheapest point to also record this, per direct
instruction, rather than adding a new command or stage.

## Options considered

- **New standalone `/reconcile` command, run after the fact.** Rejected
  on direct instruction — `reviewer` already reads the diff per task; a
  separate pass would re-read the same diff a second time for no added
  benefit, and an optional extra command is the kind of step that gets
  skipped in practice.
- **Whole-feature-only, inside `/review`.** Rejected — loses per-task
  precision (a spec with 8 tasks gets one coarse pass instead of 8
  precise ones), and `/review`'s whole-feature pass already carries the
  Definition of Done check; better to keep it a completeness check over
  entries already written, not the place they're first written.
- **Extend `reviewer`'s existing per-task pass to append reconciliation
  entries to the spec's own "## Reconciliation" section, keyed by the
  task's own `Tests:` `FR-NN`/`AC-NN` tags; `/review`'s whole-feature
  pass checks completeness (chosen).**

## Decision

For a coder-tier, per-task review, after deciding Approved/Returned,
`reviewer` reads the task's `Tests:` tags from the spec's "## Tasks"
section and appends one line per tag to "## Reconciliation" — matches
spec, or diverged with a one-clause reason — plus one line for any
change in the diff untied to a declared tag. Append-only, never
rewriting another task's entry. Informational, not a gate: it doesn't
replace the Approved/Returned verdict. `reviewer` gains `Edit` tool
access, scoped to this one write. At whole-feature scope,
`reviewer` additionally checks that every `FR-NN`/`AC-NN` the spec
claims has at least one "## Reconciliation" entry — a tag with none at
all is a finding (`Returned`), not silently passed.

## Rationale

Reuses context `reviewer` already has (the task's diff, the spec path)
instead of adding a stage. Keeps `FR-NN`/`AC-NN` as the single
traceability key already load-bearing for Test plan coverage (ADR
0004), instead of inventing a second numbering scheme for drift.

## Consequences

- `reviewer`'s tool list grows (`Edit`) — a wider blast radius than
  before (`Read`, `Grep`, `Glob`, `Bash`, `Skill` only); scoped
  narrowly (append-only, to the one spec file) to keep it proportionate.
- Reconciliation is necessarily partial mid-sweep — expected, not a
  bug; only meaningful once `/review`'s completeness check runs.
- **Known gap, not solved here**: this only covers drift caught during
  a spec's own `/implement` sweep. Once a spec reaches `implemented`,
  nothing re-checks it if a later, unrelated change edits the same code
  and invalidates an earlier entry — an on-demand reconciliation pass
  closer to Spec Kit's own `/speckit.reconcile` (callable any time
  against already-`implemented` specs) remains a real gap for a
  codebase whose specs live long enough to drift after the fact. Left
  as a candidate for a future ADR.

## References

`.claude/agents/reviewer.md`, `.claude/commands/implement.md`,
`.claude/commands/review.md`, `docs/product/requirements-template.md`,
`docs/decisions/0004-plan-tasks-implement-rebalance.md`
