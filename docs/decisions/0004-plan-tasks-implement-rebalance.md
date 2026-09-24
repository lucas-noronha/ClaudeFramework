---
doc_type: adr
id: 0004
status: proposed
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~1750 tokens
---

# ADR 0004 — Rebalance `/plan`/`/tasks`; make `/implement` a dependency-aware orchestrator with per-task review

Like ADR 0001–0003, this documents a decision about *this framework's
own* tooling (kept as a worked example). Unlike ADR 0003, this one is
independent of whether `superpowers` (or any plugin) is installed at
all — it's a correction to what this framework's own commands do.

## Context

ADR 0001 split the pipeline into `/spec → /plan → /tasks → /implement
→ /review`, but didn't pin down precisely which command owns "decide
the technical approach" versus "decide the checklist" versus "who
executes and reviews." In this framework's actual implementation,
`/plan` only ever ran a complexity triage plus a conditional ADR (via
`architect`, structural tier only) — its own file said outright that
trivial/standard tiers need no technical plan. The real sequencing and
dependency work happened inside `/tasks` instead.

Checked against the two concrete references this framework already
leans on: **GitHub's Spec Kit**, cited in ADR 0001's own rationale,
defines `/plan` as "where implementation detail belongs" (tech stack,
architecture, design decisions) and `/tasks` as purely mechanical,
dependency-ordered sequencing of an already-decided plan — "no new
planning occurs" there. **Anthropic's own Claude Code best practices**
describe planning as a distinct phase before implementation, separate
from task sequencing. Neither matches what this framework's `/plan`
and `/tasks` actually did — the technical judgment had drifted one
stage later than where both references put it.

Separately, `/implement` only ever handled one task per invocation: a
human had to manually re-run it per task, manually run `/review`
afterward, and manually decide when two tasks were safe to run in
parallel (per `docs/workflow/parallel-work.md`). Nothing enforced a
review pass before a task's checkbox got marked done.

## Options considered

- **Leave `/plan`/`/tasks` as-is.** Simplest, but keeps a real mismatch
  with the reference model this framework cites, and quietly pushes
  technical judgment into a command (`/tasks`) whose own file describes
  it as pure decomposition.
- **Merge `/plan` and `/tasks` into one command.** Matches "where does
  the thinking happen" but breaks the checkbox-based task tracking
  multiple hooks depend on (`spec_status_sync.py`), and removes the
  ability to stop after just the technical plan for a human to sanity
  check before committing to a task breakdown.
- **Rebalance responsibility without merging commands, and turn
  `/implement` into an orchestrator (chosen).** Keeps every existing
  command name, artifact, and hook contract; moves *what happens
  inside* `/plan`, `/tasks`, and `/implement` to match the reference
  model and close the parallel-dispatch/auto-review gap.

## Decision

- **`/plan`** now produces an actual technical plan, proportional to
  the tier `triage` assigns:
  - **Trivial**: unchanged — record the tier, nothing else. Writing a
    plan for a one-file, no-new-rule change is overengineering.
  - **Standard**: a short plan (what changes, which files/modules,
    approach in a few sentences, real risk points) written directly by
    whoever runs `/plan` — not delegated to a subagent, since neither
    `triage` nor any other role in this stage carries the judgment or
    the `Skill` tool for it.
  - **Structural**: `architect` still assesses cross-module impact and
    drafts an ADR if needed (unchanged); the same short-plan artifact
    as standard is then written on top of architect's decision — this
    is where this pipeline's deepest planning effort concentrates.
  - Both standard and structural additionally get an explicit **scope
    check**: if the natural implementation approach touches something
    the spec never asked for, that's flagged back rather than silently
    folded into the plan.
  - Both standard and structural also get two short checklists,
    written at the same time as the plan, both derived from and
    numbered against the spec's own "Functional requirements" and
    "Acceptance criteria" (FR-NN / AC-NN) — not invented free-floating:
    a **Definition of Done** (build/tests pass, `reviewer` approved,
    every referenced acceptance criterion satisfied, plus anything
    feature-specific — a migration verified against real data, a
    feature flag confirmed off by default) and a **Test plan** (one
    line per unit test this feature will end up with, phrased as a
    plain scenario — "rejects the request when X is missing" — each
    tagged with the FR/AC it backs). This is what makes the whole
    feature legible as a short list of phrases before any code exists,
    and it's what `coder`'s test-first pass and `reviewer`'s checklist
    both check against instead of inventing test coverage ad hoc.
- **`/tasks`** goes back to being purely mechanical: it consumes
  `/plan`'s technical plan and produces the same small,
  `/implement`-sized checkbox breakdown as before, but every task must
  now state an explicit **Depends on** field (`none` or specific task
  numbers) — not only when the task touches both layers, as before —
  and, when `/plan` wrote a Test plan, which of its entries this task
  is responsible for. No new technical judgment happens in this
  command: it distributes the Test plan's entries across tasks, it
  doesn't invent new ones.
- **`/implement`** gains an **orchestration mode**, alongside its
  existing single-task mode (unchanged): given a spec instead of one
  task, it reads `/tasks`'s dependency annotations, computes
  dependency-ready "waves," and dispatches every task in a wave to its
  own `quickfix`/`coder` subagent call in parallel — one isolated
  context per task, never the rest of the wave or the orchestration
  history. Once a task's build/test gate is green, a **coder**-tier
  task additionally gets an automatic `reviewer` pass — **explicitly
  scoped to that task's own file list** (`coder` reports exactly which
  files it touched; `/implement` hands that list to `reviewer` as the
  review's scope) — before its checkbox is marked (a `quickfix`-tier
  task skips this — see the cost-tiering rationale below); a returned
  finding goes back to `coder` for one re-review round, matching
  `reviewer`'s existing single-pass principle. A task whose gate or
  review can't converge stops the sweep and gets reported, rather than
  letting a later wave build on an unresolved failure. The explicit
  scope isn't cosmetic: orchestration mode runs several tasks in
  parallel, uncommitted, in the same working tree, so a bare `git diff`
  at that point spans every in-flight task, not just the one being
  reviewed — `reviewer` (and any `code-review`/`pr-review-toolkit`/
  `requesting-code-review` complementary pass it invokes) must never
  fall back to computing its own diff.
- **`/review`** (standalone) is unchanged in mechanism and stays for a
  final, whole-feature pass across the cumulative diff — it catches
  cross-task integration issues a per-task review can't see, and it's
  still how you review hand-edited code outside the pipeline. It
  complements the new per-task pass, it isn't replaced by it.

## Rationale

Matches the reference model this framework already claims alignment
with (Spec Kit's `/plan`/`/tasks` split, Anthropic's plan-before-code
phasing), closes a real capability gap (no parallel dispatch, no
automatic per-task review, all manual today), and does both without
introducing a new primitive — ADR 0001's split (subagents = roles,
commands = sequencing) still holds; this only corrects which command
does which part of the sequencing.

## Consequences

- `/plan` gets real work to do for standard-tier specs where it
  previously did nothing but classify — accepted, since "no plan for
  standard" was the actual mismatch being corrected; effort stays
  proportional to the tier, not uniform.
- `/implement`'s orchestration mode issues more subagent calls per
  invocation (up to one `coder`/`quickfix` + one `reviewer` per task,
  dispatched in parallel waves) — a real token-cost increase per spec,
  traded for less manual re-invocation and earlier, per-task bug
  catching instead of one catch-all review at the end.
- `/tasks`'s stricter dependency annotation means a spec written before
  this ADR won't have an explicit `Depends on` field on every task.
  `/implement`'s orchestrator treats a missing or unclear annotation as
  "depends on everything before it" (safe, sequential) — it never
  infers parallel-safety from a task's content alone.
- `reviewer` must always be handed an explicit scope (a file list for a
  per-task pass, the whole diff for `/review`) rather than computing
  its own — a real risk this ADR has to guard against explicitly, since
  orchestration mode's parallel, uncommitted waves mean a bare `git
  diff` would span multiple in-flight tasks at once, not just the one
  being reviewed. This applies to any complementary plugin `reviewer`
  invokes too (`code-review`, `pr-review-toolkit`,
  `requesting-code-review`) — none of them get to widen the scope back
  out on their own.
- `docs/workflow/model-tiering.md` is unchanged and stays authoritative
  — the orchestrator routes each task to whatever tier `triage` already
  assigned it; it never flattens every task to one model, and it never
  spends a `reviewer` (mid-tier) pass on `quickfix`-tier (cheapest
  tier) work.
- `docs/workflow/parallel-work.md`'s manually-triggered parallel
  dispatch pattern stays useful for cases outside a single spec's own
  task list (e.g., two different specs' tasks at once) — `/implement`'s
  orchestration mode automates the common case that doc used to
  describe as a manual step, it doesn't remove the manual option.
- A spec written before this ADR has unnumbered acceptance criteria and
  no Test plan at all. `/plan` can't retroactively number a spec's
  `AC-NN`s on its own — treat a pre-existing spec missing this
  numbering as a signal to add it by hand (or via `/spec` on a fresh
  copy) before `/plan` runs, not something to silently skip past.

## References

`docs/decisions/0001-tooling-agents-commands-skills.md`,
`docs/decisions/0003-superpowers-sdd-wrapping.md`,
`docs/workflow/model-tiering.md`, `docs/workflow/parallel-work.md`,
`docs/product/requirements-template.md`,
`.claude/commands/plan.md`, `.claude/commands/tasks.md`,
`.claude/commands/implement.md`, `.claude/commands/review.md`,
`.claude/agents/{triage,architect,coder,quickfix,reviewer}.md`
