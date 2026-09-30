---
description: Mechanically breaks a spec's technical plan into small, ordered, dependency-annotated tasks ready for /implement, distributing the plan's Test plan entries across them. No new technical judgment happens here.
argument-hint: path to the spec (docs/product/specs/NNNN-name.md)
---

Before anything else in this command: apply the `project-registration`
skill's check — it resolves where this session's `docs/` and `CLAUDE.md`
actually live (registering the project first if it isn't yet), and in
the common case costs one check and changes nothing.

If the spec at $ARGUMENTS is `status: abandoned`, stop and warn instead
of breaking a dropped feature into tasks.

Read the spec at $ARGUMENTS, including its "Technical plan" section
(written by `/plan` — for a standard/structural spec this is now an
actual technical plan, not just a complexity tier; see
`docs/decisions/0004-plan-tasks-implement-rebalance.md`).

Generate a numbered list of tasks, each small enough to fit a single
`/implement` call — if a task looks too big, split it into two. This is
pure decomposition of the plan `/plan` already produced: don't make a
new technical judgment call here. If the plan doesn't answer a question
a task needs, that's a gap to send back to `/plan`, not to improvise.

Each task must indicate:

- Affected layer (backend, frontend, or both) and module(s)/feature(s)
- Whether it touches a shared data resource, a new table, or sensitive
  data (so `coder` knows which skills to apply)
- **Depends on**: `none`, or the specific task number(s) that must
  finish first — state this for every task, not only when it touches
  both layers. `/implement`'s orchestration mode reads this field
  directly to decide what's safe to run in parallel; a missing or
  vague dependency note makes it default to "depends on everything
  before it" (safe, sequential), so be explicit whenever a task
  genuinely shares no state with another (see
  `../../docs/workflow/parallel-work.md`).
- **Tests**: if `/plan` wrote a Test plan, which of its entries this
  task is responsible for (by their `FR-NN`/`AC-NN` tag) — distribute
  every entry across exactly one task each, don't leave one uncovered
  and don't duplicate one across two tasks. If `/plan` didn't write a
  Test plan (trivial tier), omit this field.

Append the list to the spec itself, in a "## Tasks" section, one
checkbox per task (`- [ ] 1. ... — Depends on: ... — Tests: ...`) —
`/implement` checks its box when a task finishes, and a hook flips the
spec's `status` to `implemented` automatically once every box in this
section is checked, so the checkbox format isn't cosmetic. Don't
implement anything at this stage.
