---
description: Mechanically breaks a spec's technical plan into small, ordered, dependency-annotated tasks ready for /implement, distributing the plan's Test plan entries across them. No new technical judgment happens here.
argument-hint: path to the spec (docs/product/specs/NNNN-name/ or NNNN-name.md)
---

Before anything else in this command: apply the `project-registration`
skill's check — it resolves where this session's `docs/` and `CLAUDE.md`
actually live (registering the project first if it isn't yet), and in
the common case costs one check and changes nothing.

If the spec at $ARGUMENTS is `status: abandoned`, stop and warn instead
of breaking a dropped feature into tasks.

Language: write free text in {{LANGUAGE}}; frontmatter keys, enumerated values, the file names `spec.md`, `plan.md`, `tasks.md` and `reconciliation.md`, `## Tasks`/`## Reconciliation`, the reconciliation outcome phrases and `Approved`/`Returned` stay English.

Resolve $ARGUMENTS (a path, a folder or an `NNNN`) with
`python "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/_spec_layout.py" resolve <arg>`
(framework ADR 0024). For a **folder** spec, read `plan.md` (written by
`/plan` — for a standard/structural spec an actual technical plan; see
framework ADR 0004) and only the FR/AC ids of `spec.md`, to number the
tasks against; read `tier` from `spec.md`'s frontmatter. For a **legacy**
single-file spec, read the file including its "Technical plan" section.
A **lite** spec already carries its own inline `## Tasks`: don't run
`/tasks` on it.

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

**Each task carries its own context** (FR-07 of framework spec 0006), so
the agent that implements it never has to load the whole plan. Under each
task's checkbox line, add indented plain sub-bullets — never a checkbox,
and never starting with `[`, so they don't change the box count:

- one sub-bullet per Test plan line the task's `Tests:` field names, with
  that line's **full text** copied from `plan.md`;
- for a task of a **structural** spec, one more sub-bullet with the
  excerpt of `plan.md`'s approach that applies to it (or its heading or
  step number plus a short excerpt).

Write the list by layout:

- **Folder spec**: write `tasks.md` next to `spec.md`, with the minimal
  frontmatter (`doc_type: spec-tasks`, `spec: NNNN`, `summary`,
  `context_budget` estimated from the file's real size; never `status`) and a `## Tasks` heading. Touch no
  other file.
- **Legacy single-file spec**: append the same "## Tasks" section to that
  file, as before (the sub-bullets apply too). Create no folder.

One checkbox per task (`- [ ] 1. ... — Depends on: ... — Tests: ...`) —
`/implement` checks its box when a task finishes, and a hook flips the
spec's `status` to `implemented` automatically once every box in this
section is checked, so the checkbox format isn't cosmetic. Don't
implement anything at this stage.
