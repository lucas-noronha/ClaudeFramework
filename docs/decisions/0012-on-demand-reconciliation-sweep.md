---
doc_type: adr
id: 0012
status: proposed
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~800 tokens
---

# ADR 0012 — `/reconcile`: an on-demand fidelity sweep for a spec already `implemented`

Like ADR 0001–0011, this documents a decision about *this framework's
own* tooling (kept as a worked example).

## Context

ADR 0009 gave `reviewer` a per-task reconciliation pass, but named its
own limit plainly: it only catches drift **during** a spec's own
`/implement` sweep. Nothing revisits a spec once it's `implemented` if
later, unrelated work touches the same code and quietly invalidates an
earlier reconciliation entry — the exact gap GitHub Spec Kit
(`/speckit.reconcile`) and OpenSpec (`/opsx:sync`) cover with a
standalone, callable-anytime command. Raised directly as the follow-up
ADR 0009 flagged as a candidate.

A real constraint shapes the design: this framework doesn't persist a
file manifest per task (`/tasks` records layer/module/dependencies/
tests, not a file list — the file list only ever exists transiently in
`coder`'s end-of-turn report, handed straight to `reviewer` and never
written down). So `/reconcile`, running long after the fact, can't
diff "what changed since implementation" the way the per-task pass
does — there's no reliable stored pointer to diff against.

## Options considered

- **Diff-based, like the per-task pass** — reconstruct "files this spec
  touched" from git log (commit messages mentioning the spec ID) or
  blame. Rejected — depends on a commit-message convention this
  framework doesn't enforce anywhere; would silently produce an
  incomplete sweep on any project that doesn't happen to follow it,
  which is worse than an honest "can't verify."
- **Fresh compliance check against current code state, not a diff
  (chosen).** Re-derive from the spec's own pointers (its "Impact on
  existing architecture" section, its `area` tag, `docs/architecture/`)
  which code the spec's capability actually lives in today, and judge
  each `FR-NN`/`AC-NN` against what's there now — the same kind of
  judgment `reviewer` already makes for `/review`'s Definition of Done
  check, just anchored on current state instead of a diff.
- **A new dedicated subagent.** Rejected — `reviewer` already owns the
  "## Reconciliation" section's format and write access (ADR 0009); a
  second agent writing to the same section risks format drift between
  the two, for no real benefit over adding one more scope type to the
  one that already exists.

## Decision

New command `/reconcile <spec path>`. Requires `status: implemented`
(stop and point elsewhere for `draft`/`approved`/`abandoned`). Delegates
to `reviewer` with a third, new scope type — **sweep scope** — distinct
from per-task and whole-feature-diff: no file list, no build/test gate
prerequisite, reads the spec's requirements plus its own architectural
pointers, judges current code state FR-by-FR/AC-by-AC, and appends a
dated `### Sweep — {{DATE}}` block to "## Reconciliation" — never
edited or removed by a later sweep, so the section accumulates a
history instead of holding one mutable verdict. Never blocks, never
auto-fixes; purely diagnostic, reported straight to the user.

## Rationale

Reuses `reviewer`'s existing ownership of the Reconciliation format
(ADR 0009) instead of a parallel mechanism. Choosing "fresh check" over
"diff" trades precision for honesty given the missing-file-manifest
constraint above — an unreliable diff that silently misses files is
worse than a sweep that's explicit about checking current state, which
degrades gracefully (worst case: "couldn't verify" on a requirement
whose code isn't findable from the spec's own pointers) rather than
failing silently.

## Consequences

- No automatic trigger — a spec sitting in `implemented` is only
  re-checked when someone runs `/reconcile` on it. This framework adds
  no scheduling of its own; a project that wants periodic sweeps runs
  this on a cadence through whatever scheduling mechanism it already
  has (cron, a CI job, a scheduled agent), not something this ADR
  builds.
- A sweep's accuracy is bounded by how well the spec's "Impact on
  existing architecture" and `area` actually point at where the code
  lives — a spec that never filled that section in gives `reviewer`
  less to anchor on, and more findings will legitimately come back
  "couldn't verify" rather than a false "still matches."
- `reviewer`'s body grows a third scope type — kept as a clearly
  separate section from the other two (per-task, whole-feature) so a
  caller can't confuse which one applies.
- Sweeps accumulate indefinitely in a long-lived spec's
  "## Reconciliation" section with no pruning — acceptable for now
  since each sweep is short (one line per FR/AC), revisit if this ever
  actually bloats a spec past its `context_budget`
  (`context_budget_check.py` will nudge if so).

## References

`.claude/commands/reconcile.md`, `.claude/agents/reviewer.md`,
`docs/decisions/0009-per-task-spec-reconciliation.md`
