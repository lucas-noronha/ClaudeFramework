---
description: Creates a fresh, clean worktree for a whole spec, always based on origin/{{MAIN_INTEGRATION_BRANCH}} (or the local branch, only if it has no pending changes). Use before starting a spec's implementation you want to run isolated, in parallel with other specs or sessions.
argument-hint: the spec's own short-name (e.g. leave-approval-flow), matching docs/product/specs/NNNN-<short-name>.md
---

Goal: guarantee the new worktree never inherits uncommitted work from
another spec in progress. Follow this order, don't skip a step:

1. `$ARGUMENTS` must be the spec's own short-name — the same one in
   `docs/product/specs/NNNN-<short-name>.md` — so the branch
   (`task/<short-name>`) and the spec filename match exactly.
   `/implement`'s orchestration mode looks up the worktree by that
   exact match (see
   `docs/decisions/0005-spec-worktree-lifecycle.md`); a mismatched name
   means it won't find it next time.
2. Run `git fetch origin {{MAIN_INTEGRATION_BRANCH}}` — the source of
   truth is always the remote, never the local state without
   confirming first.
3. Run `git status --porcelain` on the local
   `{{MAIN_INTEGRATION_BRANCH}}` branch. If there's any pending change
   (even unrelated to this spec), **stop and warn the user** — don't
   proceed assuming "it's unrelated anyway".
4. Compare `git rev-parse {{MAIN_INTEGRATION_BRANCH}}` with
   `git rev-parse origin/{{MAIN_INTEGRATION_BRANCH}}`. If they diverge,
   prefer `origin/{{MAIN_INTEGRATION_BRANCH}}` as the base — never a
   potentially stale local branch.
5. Create the worktree explicitly from the remote reference, never
   relying on whatever default branch the tool auto-detects:
   ```
   git worktree add ../$ARGUMENTS -b task/$ARGUMENTS origin/{{MAIN_INTEGRATION_BRANCH}}
   ```
6. Report the created path and remind the user to open a separate
   Claude Code session inside it (`cd ../$ARGUMENTS && claude`) — that
   spec's `/implement` should run in that session, not the current one.
   This isn't just convenience: this framework's hooks are wired to
   whichever session's `${CLAUDE_PROJECT_DIR}` started them, so only a
   session actually opened in the new worktree gets its build/test gate
   and spec-tracking hooks working correctly there.

Isolation stops at the spec — a single task never gets a worktree of
its own, no matter how large. Every task in a spec's `/implement` sweep
shares this one worktree, isolated from its siblings only at the
subagent-context level (see
`docs/decisions/0004-plan-tasks-implement-rebalance.md`) — that's
enough, and avoids a session hand-off per task.

Don't use subagent `isolation: worktree` or the automatic `--worktree`
flag for this flow — their base-branch behavior isn't guaranteed to be
`origin/{{MAIN_INTEGRATION_BRANCH}}` specifically. This command exists
precisely so you don't depend on that. If `superpowers` is enabled,
its `using-git-worktrees` skill covers the same underlying discipline
(isolate before parallel work) — it names the same goal, it doesn't
replace the steps above, since only this command guarantees the
`origin/{{MAIN_INTEGRATION_BRANCH}}` base. See
`../../docs/workflow/parallel-work.md` for how to track what's running
across several worktrees at once.
