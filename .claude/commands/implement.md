---
description: Implements one task, or orchestrates every remaining task in a spec — offering to isolate the spec in its own worktree first, routing each task to quickfix/coder by complexity, running independent tasks in parallel, auto-reviewing coder-tier work before checking it off.
argument-hint: task number/description, or a spec path to run every remaining task
---

Before anything else in this command: apply the `project-registration`
skill's check — it resolves where this session's `docs/` and `CLAUDE.md`
actually live (registering the project first if it isn't yet), and in
the common case costs one check and changes nothing. Once, here, before
either mode below branches — both need a resolved project either way.

Two settings from this project's config change what follows (they live
in `project-config.json`, or the optional `.claude/project-config.json`
in mode A; absent means the default):

- **`review_policy`** (ADR 0020): `per-task` (default) runs `reviewer`
  on every coder-tier task as step 6 describes; `final-only` skips every
  per-task review, so the whole-feature `/review` is the only review
  pass; `structural-only` keeps the per-task review only when the spec's
  tier is structural. The final `/review` runs under every policy, and
  so does the build/test gate.
- **`census.enabled`** (ADR 0019): turns on step 8.

Two modes, based on $ARGUMENTS.

## Single-task mode — $ARGUMENTS names one task

1. If the task's complexity isn't already known (e.g. recorded by
   `/plan`), delegate a quick classification to the `triage` subagent.
2. **Trivial** → delegate to `quickfix` (cheaper model, same
   expectation of tests alongside the change).
3. **Standard/structural** → delegate to `coder`.
4. Pass only the specific task and the source spec's path — never the
   whole repository nor other tasks from the same spec, so the
   subagent's own context stays scoped to exactly this task.
5. After the subagent finishes, the project's build/lint/test hook
   runs automatically. If it fails, return the result to the subagent
   before considering the task done.
6. Once green, if `review_policy` calls for a per-task review here (see
   above — otherwise skip to step 7, and reconciliation entries for this
   task are left to the final `/review`): for a **coder**-tier task, delegate a review to
   `reviewer`, handing it the exact file list `coder` reported at the
   end of step 3 as the review's scope — never "the current diff" left
   for `reviewer` to compute itself. This isn't optional phrasing: this
   framework's own working tree can hold several tasks' uncommitted
   changes at once during orchestration mode, so a scope-less `git
   diff` would pull in work that isn't this task's. As part of this same
   pass, `reviewer` also appends reconciliation entries to the spec's
   own "## Reconciliation" section for this task's declared `FR-NN`/
   `AC-NN` tags (see `docs/decisions/0009-per-task-spec-reconciliation.md`)
   — nothing extra to orchestrate here, it's the same call. A
   **quickfix**-tier task skips review (and therefore reconciliation)
   entirely — per `docs/workflow/model-tiering.md`, don't spend a
   `reviewer` pass on a single-file trivial fix. If `reviewer` returns
   findings, send them to `coder`, which applies `receiving-code-review`
   discipline (see `plugin-awareness`) before re-implementing;
   re-review once more (same explicit file-list scope), then proceed
   either way.
7. Check the corresponding box (`- [ ]` → `- [x]`) in the spec's
   "## Tasks" section. A hook flips the spec's own `status` to
   `implemented` once every task box in the section is checked — never
   set that status by hand.
8. **Census projects only** (`census.enabled`): update every
   architecture doc this task made untrue (the subagent's report names
   them; keep to describing, no inventory counts), then record the
   change for the next `/update-docs`:
   `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/census.py" ledger add-pending --spec <spec id> --task <task number> --files <the task's src/tests files> --docs <docs updated>`.
   Never touch the watermark: that is `/update-docs`' job, once the
   change has actually landed on the integration branch.

When single-task mode is called on its own (not from orchestration
mode), wrap it in the feature markers described in orchestration mode's
step 0, using the task's spec id.

## Orchestration mode — $ARGUMENTS names a spec, not one task

If the spec is `status: abandoned`, stop and warn instead of
implementing a dropped feature.

Runs every remaining (unchecked) task in that spec's "## Tasks" section
to completion, respecting the dependency graph `/tasks` recorded (see
`docs/decisions/0004-plan-tasks-implement-rebalance.md`):

0. **Feature markers** (ADR 0020): before the first wave run
   `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/metrics.py" start --feature <spec id> --lane <fast if the spec has lite: true, else full> --tier <the spec's tier>`,
   and after the last one (or when the sweep stops) `metrics.py finish
   --feature <spec id>`. They let `/metrics` attribute subagents, gate
   runs and reviewer verdicts to this feature.

1. **Worktree check** (see
   `docs/decisions/0005-spec-worktree-lifecycle.md`): run `git worktree
   list` and look for a branch named `task/<spec-short-name>` (matching
   this spec's own filename slug).
   - If the **current** session's working directory already is that
     worktree: continue to step 2, nothing else changes.
   - If it doesn't exist yet: ask (`AskUserQuestion`) whether to isolate
     this spec's implementation in its own worktree before starting —
     worth it if you'll run other specs' `/implement` at the same time,
     or want a clean, spec-scoped diff and PR at the end. Suggest yes by
     default for standard/structural tiers, genuinely optional for
     trivial. If yes: create it using `/worktree`'s own steps (branch
     `task/<spec-short-name>`, pinned to
     `origin/{{MAIN_INTEGRATION_BRANCH}}`), then **stop** — tell the
     user to open a new Claude Code session there and re-run
     `/implement` on this same spec from inside it. Don't try to
     continue the sweep from this session: this framework's hooks
     (build/test gate, spec tracking) are wired to *this* session's
     `${CLAUDE_PROJECT_DIR}`, not the new worktree. If no: continue to
     step 2 in the current working tree.
   - If a worktree already exists for this spec but this session isn't
     in it: **warn and stop** — point at the existing worktree path
     instead of silently sweeping in the wrong tree, where the
     build/test gate and spec-tracking hooks would be checking the
     wrong files entirely.
2. Read the "## Tasks" section; parse each unchecked task's **Depends
   on** field. Treat a missing or unclear dependency note as "depends
   on every earlier task" — never infer parallel-safety from a task's
   content alone.
3. Compute the next **wave**: every unchecked task whose dependencies
   are already checked off.
4. Dispatch the whole wave in one turn — one subagent call per task, in
   parallel, not sequential — each following single-task mode above
   (steps 1–8) in full, including its own build/test gate and, for
   coder-tier tasks, its own `reviewer` pass. Every task gets its own
   isolated subagent context: only that task's text and the spec path,
   never the other tasks in the wave or the orchestration history —
   this is what keeps a multi-task sweep from polluting any one
   subagent's context, and it's also why the main session stays cheap:
   it only ever sees each subagent's summary, never its intermediate
   work. This is the *only* isolation a task gets — a task never gets a
   worktree of its own; every task in this sweep shares the one
   worktree from step 1 (see
   `docs/decisions/0005-spec-worktree-lifecycle.md`).
5. If `superpowers` is enabled this session, invoke its
   `dispatching-parallel-agents`/`subagent-driven-development` skills
   to structure this wave dispatch, and `executing-plans` for running
   the spec's task list through to completion. If it isn't enabled,
   apply the same discipline directly (absorbed fallback, see
   `plugin-awareness`): never dispatch two tasks in the same wave that
   touch the same file or contract, even if `/tasks` didn't flag it —
   re-verify before dispatching, don't trust the annotation blindly if
   something about two "independent" tasks looks off.
6. Once a wave finishes (every task in it checked off), recompute the
   next wave from what's now checked and repeat until every task in the
   section is checked.
7. If a task fails its build/test gate twice, or a `reviewer` finding
   can't be resolved after one re-review, **stop the sweep** and report
   it plainly — don't let a later wave build on top of an unresolved
   failure.
8. Report a summary at the end: what was implemented per wave, what ran
   in parallel, any `reviewer` finding surfaced and how it was
   resolved, and any divergence `reviewer` recorded in "## Reconciliation"
   along the way.

`/review` (standalone) still exists for a final, whole-feature pass
across the cumulative diff — it catches cross-task integration issues a
per-task review can't see, and it's how you review hand-edited code
outside this pipeline. It complements the per-task pass above, it isn't
replaced by it.

Either mode: never mention `superpowers` (or any Core plugin) to the
user — report only the outcome.
