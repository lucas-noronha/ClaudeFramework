---
description: Runs a final, whole-feature architecture checklist review over the cumulative diff plus the spec's Definition of Done, delegating to the reviewer subagent. Only after the deterministic gate is green. On approval, offers to push and open a PR when the spec lives in its own worktree.
---

Before anything else in this command: apply the `project-registration`
skill's check — it resolves where this session's `docs/` and `CLAUDE.md`
actually live (registering the project first if it isn't yet), and in
the common case costs one check and changes nothing.

This is the **final, whole-feature** pass — distinct from the
per-task `reviewer` pass `/implement`'s orchestration mode already runs
automatically for coder-tier tasks (see
framework ADR 0004). Run this once
a spec's tasks are all implemented, to catch cross-task integration
issues a per-task review can't see, check the spec's own "Technical
plan → Definition of Done" line by line plus the completeness of its
"## Reconciliation" section (the per-task pass deliberately skips both
— they're feature-level questions; see
framework ADR 0009), or any time you
need to review hand-edited code that never went through `/implement`
at all.

Confirm the build/lint/test hook passed on the current changes (see
the result of the last `/implement` call). If it didn't, stop and
return to `coder` — don't call `reviewer` over code that doesn't even
compile.

If it passed, and `superpowers` is enabled this session, invoke its
`requesting-code-review` skill to make sure the diff and its context
are actually ready for review before delegating — then delegate to
`reviewer`, **explicitly telling it the scope is the whole cumulative
diff** (`git diff` against the base branch, unscoped to any single
task) — that's the one place in this pipeline where that's the
intended, deliberate scope, unlike `/implement`'s per-task pass. Report
the result (approved or returned with specific findings) directly to
the user.

If this project's `review_policy` skipped per-task reviews for this
spec (`final-only`, or `structural-only` on a non-structural spec — see
framework ADR 0020), nothing has written
the spec's "## Reconciliation" entries yet. Tell `reviewer` so: in this
pass it first appends one entry per task and declared `FR-NN`/`AC-NN`,
in the per-task format, and only then checks completeness. A missing
entry is a finding only once it has had the chance to write them.

If the result is **Approved**:

- If `superpowers` is enabled, mention its
  `finishing-a-development-branch` skill as the next step for deciding
  how to integrate — this framework has no merge/finish command of its
  own.
- If the current branch is `task/<spec-short-name>` (this spec is
  running in its own worktree, per
  framework ADR 0005), explicitly offer —
  never do it unasked, pushing and opening a PR are both visible to
  others — to push the branch (`git push -u origin
  task/<spec-short-name>`) and open a PR (`gh pr create`, base
  `{{MAIN_INTEGRATION_BRANCH}}`). If the project has no `gh`/GitHub
  remote, say so and point at pushing the branch as the manual next
  step instead. If the spec isn't in its own worktree, skip this offer
  entirely — there's nothing spec-scoped to push.

If it's **Returned**, send the findings back to `coder`, which applies
`superpowers:receiving-code-review` discipline (or the absorbed
equivalent) before acting on them — see `plugin-awareness`.
