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
   framework ADR 0005); a mismatched name
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
5. Resolve where the worktree goes — never hardcode it:
   ```
   python "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/_project_paths.py" worktree-path $ARGUMENTS
   ```
   It prints `<worktrees root>/<repo folder name>/$ARGUMENTS` when this
   machine has a worktrees root (chosen in `/setup-framework`), else the
   sibling `../$ARGUMENTS`. If that path already exists, stop and say
   so — never reuse or overwrite a folder you didn't just create.
6. Create the worktree there explicitly from the remote reference, never
   relying on whatever default branch the tool auto-detects (git creates
   any missing parent folders):
   ```
   git worktree add "<path from step 5>" -b task/$ARGUMENTS origin/{{MAIN_INTEGRATION_BRANCH}}
   ```
7. Mirror the framework links into the worktree (mode B; framework ADR 0022):
   ```
   python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/link_worktree.py" "<path from step 5>"
   ```
   It prints a JSON report and applies by default (`--dry-run` only
   previews). It's a no-op in modes A and C; in mode B it mirrors the
   main checkout's `.claude`, `docs` and `CLAUDE.md` links into the new
   worktree, so a session opened there loads the framework's hooks,
   commands and project docs, and it adds root-anchored lines to the
   repo's shared `info/exclude` (framework spec 0004). Per-worktree
   state such as the handoff is handled by the hooks themselves, not by
   this script. On exit 1 (conflict or refusal), relay the report to the
   user as is and stop there — don't delete or move anything to
   "fix" it. Exit 2 means `git worktree list` failed; say so. For a
   worktree created before this step existed, run the same script with
   `--repair` instead of the path.
8. In mode A only, offer — never force — to copy
   `.claude/settings.local.json` into the new worktree (it's per-machine
   and gitignored, so a fresh worktree lacks it). Ask with
   AskUserQuestion; copy only on a yes, and never overwrite a file that
   already exists in the worktree.
9. Report the created path and remind the user to open a separate
   Claude Code session inside it (`cd "<path>" && claude`) — that
   spec's `/implement` should run in that session, not the current one.
   This isn't just convenience: this framework's hooks are wired to
   whichever session's `${CLAUDE_PROJECT_DIR}` started them, so only a
   session actually opened in the new worktree gets its build/test gate
   and spec-tracking hooks working correctly there.

Isolation stops at the spec — a single task never gets a worktree of
its own, no matter how large. Every task in a spec's `/implement` sweep
shares this one worktree, isolated from its siblings only at the
subagent-context level (see
framework ADR 0004) — that's
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
