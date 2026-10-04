---
doc_type: adr
id: 0003
status: accepted
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~950 tokens
---

# ADR 0003 — Wrap `superpowers`' skills across the whole SDD lifecycle, not just `coder`/`reviewer`

Like ADR 0001 and 0002, this documents a decision about *this
framework's own* tooling (kept as a worked example) — whether to adopt
`superpowers` at all remains the reader's own call, gated the same way
ADR 0002 already gates every Core plugin.

## Context

ADR 0002 introduced the absorbed+complementary pattern and scoped
`superpowers`'s complementary invocation to `coder` only
(test-driven-development, systematic-debugging), on the reasoning that
"`/spec`/`/plan` stay the framework's own sequencing — this doesn't
replace them." Hands-on use of `superpowers` since then shows its value
isn't limited to the implementation step: its `brainstorming` skill
measurably speeds up turning a rough idea into a solid spec, and
several of its other skills (`writing-plans`,
`verification-before-completion`, `requesting-code-review`/
`receiving-code-review`, `using-git-worktrees`,
`finishing-a-development-branch`, `dispatching-parallel-agents`/
`subagent-driven-development`/`executing-plans`) map directly onto
stages this framework already has (`/spec`, `/plan`, `/implement`,
`/review`, `/worktree`) that currently get no complementary pass at
all. Leaving the wrapping scoped to `coder`/`reviewer` wastes the
plugin's value everywhere else in the pipeline once it's installed, and
pushes the user toward invoking `superpowers` directly for those
stages — which plugin-awareness's own stated principle ("the user
interacts with this framework's own commands only") says shouldn't
happen.

This ADR only decides *which stage invokes which skill*, once
`docs/decisions/0004-plan-tasks-implement-rebalance.md` has already
decided what each stage's own job is. Read that one first if the
mapping below looks off relative to an earlier draft of this ADR — an
earlier version of this file mapped `writing-plans` to `/tasks`, before
ADR 0004 corrected `/tasks` back to pure mechanical decomposition and
moved real technical planning to `/plan`, matching GitHub Spec Kit (the
reference ADR 0001 already cites): `/plan` is "where implementation
detail belongs," `/tasks` does no new planning.

## Options considered

- **Leave as-is.** Simplest, but underuses an installed plugin at every
  stage except implement/review, and contradicts the "commands only"
  principle the moment a user reaches for `superpowers` by hand at
  spec/plan/tasks time.
- **Replace `/spec`, `/plan`, `/tasks` with `superpowers`'s own
  equivalents.** Maximum reuse, but breaks ADR 0001's guarantee that
  commands are the only sequencing authority — `superpowers`'s skills
  trigger on relevance, not fixed sequence — and this framework's own
  commands produce artifacts (the requirements template, the
  stakeholder-language validation file, the `## Tasks` checkbox format)
  that hooks (`spec_status_sync.py`, `spec_index.py`) structurally
  depend on. A generic skill can't be trusted to reproduce that shape.
- **Extend the absorbed+complementary pattern (chosen).** Every SDD
  command/agent keeps being the sequencing authority and keeps
  producing this framework's own artifacts. When `superpowers` is
  enabled, the command's own step additionally invokes the matching
  skill as a complementary pass — exactly the mechanism ADR 0002
  already established for `coder`/`reviewer`, just applied to the
  stages it previously excluded. The absorbed-discipline fallback
  (written prose, no plugin needed) stays the floor either way.

## Decision

- `/spec` invokes `superpowers:brainstorming` as its own step 1 when
  enabled, before filling the requirements template — the framework's
  template/file-naming/status conventions stay authoritative over
  whatever `brainstorming` produces on its own.
- `/plan` invokes `superpowers:writing-plans` to draft the actual
  technical plan for standard/structural tiers (per ADR 0004) — trivial
  stays plan-free. `/tasks` invokes no `superpowers` skill: per ADR
  0004 it's pure mechanical decomposition of `/plan`'s own output, and
  inventing a plugin-backed step there would just reopen the mismatch
  ADR 0004 fixed.
- `/implement`'s orchestration mode (ADR 0004) invokes
  `superpowers:dispatching-parallel-agents`/`subagent-driven-development`
  when structuring a wave of parallel task dispatches, and
  `superpowers:executing-plans` when running the spec's task list
  through to completion in the current session.
- `coder` additionally invokes `superpowers:receiving-code-review` when
  acting on a `reviewer` "Returned" verdict, and
  `superpowers:verification-before-completion` before considering any
  task done — alongside the test-driven-development/
  systematic-debugging/`code-simplifier` passes ADR 0002 already wired
  in. `quickfix` gains the same `verification-before-completion`
  discipline absorbed only (written prose, not an invocation) — it
  carries no `Skill` tool, deliberately kept cheap per ADR 0002, and
  this decision doesn't reopen that.
- `/review` invokes `superpowers:requesting-code-review` as part of its
  own delegation step, and its Approved path names
  `superpowers:finishing-a-development-branch` as the next step for
  deciding how to integrate — this framework has no merge/finish
  command of its own to hold that discipline otherwise.
- `/worktree` keeps its own origin-pinned steps authoritative (per its
  existing note that it exists precisely so isolation doesn't depend on
  a tool's own default base-branch behavior); it now names
  `superpowers:using-git-worktrees` as the same underlying discipline
  when the plugin is enabled, without substituting for the steps.
- `docs/workflow/plugin-integrations.md`'s `superpowers` row is
  rewritten to list every stage above instead of only `coder`, so
  `/setup-framework`'s Domain 2 (which pulls its one-line description
  straight from that table) surfaces the expanded scope to the user
  during install, without any new install-time logic.
- `/spec`, `/plan` (its own writing-plans step, not the `architect`
  delegation), and `/implement`'s orchestration logic carry this
  instruction inline in their own command bodies rather than through
  `plugin-awareness`'s `applies_to` tagging, since that mechanism is
  scoped to subagents and this work runs directly in the main thread
  with no subagent to hold it.

## Rationale

Keeps ADR 0001's guarantee (commands are the only sequencing authority)
and ADR 0002's guarantee (absorbed discipline is the floor, installing
anything is optional and user-gated) exactly as they were — this
decision only widens which stages get the complementary pass, using
the identical mechanism already in production for `coder`/`reviewer`.
No new pattern for a future reader to learn.

## Consequences

- More files now name `superpowers` skills by name, all under the same
  "invoke as a complementary pass when enabled, never mention it to the
  user, absorbed fallback otherwise" convention — more surface area to
  update if `superpowers` ever renames one of these skills, traded
  against the reuse the plugin actually delivers once installed.
- Declining to install `superpowers` remains a fully valid outcome:
  every stage's written-out steps are unchanged and sufficient on their
  own, per ADR 0002's existing guarantee.
- `docs/workflow/plugin-integrations.md`'s table needs updating first
  whenever the mapping in this ADR changes — it's the single source
  `/setup-framework` reads from, not a duplicate to keep in sync by
  hand.

## References

`docs/decisions/0002-plugin-integration.md`,
`docs/decisions/0004-plan-tasks-implement-rebalance.md`,
`docs/workflow/plugin-integrations.md`,
`.claude/skills/plugin-awareness/SKILL.md`,
`.claude/commands/spec.md`, `.claude/commands/plan.md`,
`.claude/commands/tasks.md`, `.claude/commands/implement.md`,
`.claude/commands/review.md`, `.claude/commands/worktree.md`,
`.claude/agents/coder.md`, `.claude/agents/quickfix.md`,
`docs/workflow/parallel-work.md`
