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

- **`review_policy`** (framework ADR 0020): `per-task` (default) runs `reviewer`
  on every coder-tier task as step 6 describes; `final-only` skips every
  per-task review, so the whole-feature `/review` is the only review
  pass; `structural-only` keeps the per-task review only when the spec's
  tier is structural. The final `/review` runs under every policy, and
  so does the build/test gate.
- **`census.enabled`** (framework ADR 0019): turns on step 8.

**Resolve the spec first** (framework ADR 0024). Both layouts exist — the
legacy single file and the spec folder (`spec.md` + `plan.md` +
`tasks.md` + `reconciliation.md`), plus the one-file lite spec. $ARGUMENTS
may name a task, a number `NNNN`, a folder or a file; resolve the spec with
`python "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/_spec_layout.py" resolve <path|folder|NNNN>`
(pass an absolute path, a folder name or `NNNN` — a relative path resolves
against the current directory).
Its JSON gives the layout (`legacy`, `folder` or `lite`), the id, the
spec's files, the status file, the **tasks target** (`tasks.md`, or the
single file's "## Tasks"), the **reconciliation target** (`reconciliation.md`,
or the single file's "## Reconciliation") and the **branch short name**.
Use those values everywhere below instead of assuming a path.

Two modes, based on $ARGUMENTS.

## Single-task mode — $ARGUMENTS names one task

1. If the task's complexity isn't already known (e.g. recorded by
   `/plan`), delegate a quick classification to the `triage` subagent.
2. **Trivial** → delegate to `quickfix` (cheaper model, same
   expectation of tests alongside the change).
3. **Standard/structural** → delegate to `coder`.
4. Pass only the task's full text (its `- [ ] N.` line plus its indented
   sub-bullets, read from the tasks target) and the path of the spec's
   `spec.md` (the single file in the legacy and lite layouts) — never the
   whole repository, other tasks from the same spec, `tasks.md` as a
   whole, `reconciliation.md` or `plan.md` (framework ADR 0024). The
   subagent may open `plan.md` only if the task text is insufficient. This
   keeps its context scoped to exactly this task. **Every** task prompt
   (to `coder`, `quickfix` and `reviewer`, in both modes) also repeats the
   git rule: inside a subagent git is read-only (`status`, `diff`, `log`,
   `show`, `rev-parse`, `ls-files`, `check-ignore`, `blame`, `grep`,
   `cat-file`, `describe`, and `branch`/`tag`/`worktree list`/`stash list`
   only as listings); never revert the tree to check a baseline — use
   `git show HEAD:<path>` or `git diff -- <paths>`; a command outside the
   list is reported so the main session runs it (framework spec 0007).
5. After the subagent finishes, the project's build/lint/test hook
   runs automatically. If it fails, return the result to the subagent
   before considering the task done. The subagent "finishes" when its
   completion notification arrives, not when its hand-back report does:
   the gate runs *after* the hand-back, for as long as the build/test
   command takes, so never stop a subagent between the two — stopping it
   kills its gate. Don't count on the gate's exit 2 to send the failure
   back by itself (some harnesses don't resume a subagent that ended
   through a hand-back): read the task's gate result with
   `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/metrics.py" gates`
   (its `agent_id` is the id the Agent tool returned) and, on a failure,
   run the build/test command once yourself for the output and send its
   tail to that same subagent (resume it by id), as one returned failure.
6. Once green, if `review_policy` calls for a per-task review here (see
   above — otherwise skip to step 7, and reconciliation entries for this
   task are left to the final `/review`): for a **coder**-tier task, delegate a review to
   `reviewer`, handing it the exact file list `coder` reported at the
   end of step 3 as the review's scope — never "the current diff" left
   for `reviewer` to compute itself. This isn't optional phrasing: this
   framework's own working tree can hold several tasks' uncommitted
   changes at once during orchestration mode, so a scope-less `git
   diff` would pull in work that isn't this task's. Hand it also the
   reconciliation target path from the resolver (`reconciliation.md`, or
   the single file's "## Reconciliation" section) as the place its entries
   belong — but `reviewer` does not edit it in a per-task review. As part
   of this same pass it returns, for this task's declared `FR-NN`/`AC-NN`
   tags (see framework ADR 0009), its reconciliation lines in its final
   message under a line reading exactly `Reconciliation:`, after the
   verdict and any `Advisory:`/`Rule may be stale:`/`Constitution
   conflict:` lines. The coordinator (this session, never a subagent)
   appends those lines verbatim, with Edit, one reply at a time, to the
   resolver's reconciliation target — `reconciliation.md`, or the
   `## Reconciliation` section of a legacy or lite file — so parallel
   reviewers never write the same file at once. A
   **quickfix**-tier task skips review (and therefore reconciliation)
   entirely — per `docs/workflow/model-tiering.md`, don't spend a
   `reviewer` pass on a single-file trivial fix. If `reviewer` returns
   findings, send them to `coder`, which applies `receiving-code-review`
   discipline (see `plugin-awareness`) before re-implementing;
   re-review once more (same explicit file-list scope), then proceed
   either way.
7. Look the spec up again by its id with the resolver (a migration to the
   folder layout may have moved it during a sweep — framework ADR 0024),
   then check the corresponding box (`- [ ]` → `- [x]`) in the tasks
   target. A hook flips the spec's own `status` (in the status file) to
   `implemented` once every task box is checked — never set that status
   by hand.
8. **Census projects only** (`census.enabled`): update every
   architecture doc this task made untrue (the subagent's report names
   them; keep to describing, no inventory counts), then record the
   change for the next `/update-docs`:
   `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/census.py" ledger add-pending --spec <spec id> --task <task number> --files <the task's src/tests files> --docs <docs updated>`.
   Never touch the watermark: that is `/update-docs`' job, once the
   change has actually landed on the integration branch.

When single-task mode is called on its own (not from orchestration
mode), wrap it in the feature markers described in orchestration mode's
step 1b, using the task's spec id.

## Orchestration mode — $ARGUMENTS names a spec, not one task

If the spec is `status: abandoned`, stop and warn instead of
implementing a dropped feature.

Runs every remaining (unchecked) task in that spec's "## Tasks" section
to completion, respecting the dependency graph `/tasks` recorded (see
framework ADR 0004):

1. **Worktree check** (see
   framework ADR 0005): run `git worktree
   list` and look for a branch named `task/<branch short name>` (the
   resolver's value: the spec's slug without the number, `quick-` kept
   for quick specs).
   - If the **current** session's working directory already is that
     worktree: continue to step 1b, nothing else changes.
   - If it doesn't exist yet: ask (`AskUserQuestion`) whether to isolate
     this spec's implementation in its own worktree before starting —
     worth it if you'll run other specs' `/implement` at the same time,
     or want a clean, spec-scoped diff and PR at the end. Suggest yes by
     default for standard/structural tiers, genuinely optional for
     trivial. If yes: create it using `/worktree`'s own steps (branch
     `task/<branch short name>`, pinned to
     `origin/{{MAIN_INTEGRATION_BRANCH}}`), then **stop** — tell the
     user to open a new Claude Code session there and re-run
     `/implement` on this same spec from inside it. Don't try to
     continue the sweep from this session: this framework's hooks
     (build/test gate, spec tracking) are wired to *this* session's
     `${CLAUDE_PROJECT_DIR}`, not the new worktree. If no: continue to
     step 1b in the current working tree.
   - If a worktree already exists for this spec but this session isn't
     in it: **warn and stop** — point at the existing worktree path
     instead of silently sweeping in the wrong tree, where the
     build/test gate and spec-tracking hooks would be checking the
     wrong files entirely.
1b. **Feature markers** (framework ADR 0020): once the worktree check lets
   the sweep continue here (never before it: a session that stops to hand
   off to a worktree must not open a feature that the worktree's own
   `/implement` would open again), before the first wave run
   `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/metrics.py" start --feature <spec id> --lane <fast if the spec has lite: true, else full> --tier <the spec's tier>`,
   and after the last one (or when the sweep stops) `metrics.py finish
   --feature <spec id>`. They let `/metrics` attribute subagents, gate
   runs and reviewer verdicts to this feature.
2. Read the tasks target (`tasks.md`, or the single file's "## Tasks"
   section); parse each unchecked task's **Depends
   on** field. Treat a missing or unclear dependency note as "depends
   on every earlier task" — never infer parallel-safety from a task's
   content alone.
3. Compute the next **wave**: every unchecked task whose dependencies
   are already checked off. **Before dispatching it**, run the pre-wave
   delete/rename check (framework spec 0007, ADR 0025): read each wave
   task's text for a file it deletes or renames, search the other tasks
   of the same wave for references to that path, and split any pair you
   find across waves — the referencing task goes first, the deleting or
   renaming one waits for the next wave. Then mark the wave:
   `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/metrics.py" wave-start --feature <spec id>`.
4. Dispatch the whole wave in one turn — one subagent call per task, in
   parallel, not sequential — each following single-task mode above
   (steps 1–8) in full, including its own build/test gate and, for
   coder-tier tasks, its own `reviewer` pass. Every task gets its own
   isolated subagent context: only that task's full text and the `spec.md` path,
   never the other tasks in the wave or the orchestration history —
   this is what keeps a multi-task sweep from polluting any one
   subagent's context, and it's also why the main session stays cheap:
   it only ever sees each subagent's summary, never its intermediate
   work. This is the *only* isolation a task gets — a task never gets a
   worktree of its own; every task in this sweep shares the one
   worktree from step 1 (see
   framework ADR 0005).
5. If `superpowers` is enabled this session, invoke its
   `dispatching-parallel-agents`/`subagent-driven-development` skills
   to structure this wave dispatch, and `executing-plans` for running
   the spec's task list through to completion. If it isn't enabled,
   apply the same discipline directly (absorbed fallback, see
   `plugin-awareness`): never dispatch two tasks in the same wave that
   touch the same file or contract, even if `/tasks` didn't flag it —
   re-verify before dispatching, don't trust the annotation blindly if
   something about two "independent" tasks looks off.
6. Once every subagent of a wave has stopped (its completion
   notification arrived — step 5; with many subagents, don't track this
   from memory: `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/metrics.py" pending`
   lists each `coder`/`quickfix` whose hand-back arrived but whose gate
   hasn't landed, with how long it has waited — one waiting past the
   gate hook's timeout lost its gate, so run the build/test command for
   it yourself), run
   `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/metrics.py" gates`:
   it prints, as JSON, the latest `gate_run` per `agent_id` in this
   checkout since the last `wave-start`. A gate that failed while other
   subagents were editing (`concurrent` > 0) may have failed on someone
   else's half-finished files, so give it **one re-run**: run the
   project's build/test command once yourself. If it passes, those
   concurrent failures are cleared. If it fails, attribute the failing
   output to tasks by the file lists they reported and return it to
   those tasks. A solo final failure (`concurrent` absent or 0) is
   returned to its task as is, the way step 5 says. Then, once every task in the wave is
   checked off, recompute the next wave from what's now checked and
   repeat until every task in the section is checked.
7. If a task fails its build/test gate twice, or a `reviewer` finding
   can't be resolved after one re-review, **stop the sweep** and report
   it plainly — don't let a later wave build on top of an unresolved
   failure. Only failures *returned to a task* count toward "twice": a
   concurrent failure that step 6's re-run cleared is not one.
8. Report a summary at the end: what was implemented per wave, what ran
   in parallel, any `reviewer` finding surfaced and how it was
   resolved, and any divergence `reviewer` returned and you recorded in
   the reconciliation target along the way.

`/review` (standalone) still exists for a final, whole-feature pass
across the cumulative diff — it catches cross-task integration issues a
per-task review can't see, and it's how you review hand-edited code
outside this pipeline. It complements the per-task pass above, it isn't
replaced by it.

Either mode: never mention `superpowers` (or any Core plugin) to the
user — report only the outcome.
