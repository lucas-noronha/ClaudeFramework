---
doc_type: spec-tasks
spec: 0004
summary: The ordered task list, one checkbox per task.
context_budget: ~1100 tokens
---

## Tasks

Layers here are framework layers: **hooks/scripts** (Python, tested) and
**commands/docs** (prose read by agents). No task touches sensitive data
or a new table. The only shared resource is the per-project metrics log
(task 3).

- [x] 1. **Resolver** — hooks/scripts: `.claude/hooks/_project_paths.py`. Add the memoized linked-worktree resolver (`gitdir` → `commondir`, common dir must be `.git`; admin name, main checkout, subpath, branch from `<gitdir>/HEAD`). Make it the registry fallback in `_registered_subtree`, trying normalized and realpath forms. Replace `_main_checkout()`'s subprocess. Give `local_framework_config()` and `get_worktrees_root(project_dir=None)` the `<main>/.claude/` fallback. Add `worktree` to `describe`. New test file `tests/test_worktree_sessions.py`. Shared resource: registry, read-only. — Depends on: none — Tests: T02, T03, T04, T05, T06, T07, T08, T17
- [x] 2. **State scopes** — hooks/scripts: `state_file_path(project_dir, filename, scope=None)` in `_project_paths.py` (`None` keeps today's resolution, `"checkout"` → `.worktree-state/<admin>/` in B/C or `<worktree>/.claude/` in A, `"project"` → `<main>/.claude/` for a mode A worktree). Wire `session_handoff.py` and `session_brief.py`'s handoff read to `checkout`. — Depends on: 1 — Tests: T09
- [x] 3. **Metrics per checkout** — hooks/scripts plus one command: `_pipeline_metrics.py` (scope `project`, `checkout: <admin>` stamp, advisory append lock that fails open), `scripts/metrics.py` (scope `project`, one open-feature stack per checkout, features keyed by `(checkout, feature)`, a missing `checkout` counts as main), `commands/implement.md` (step 0's feature markers move after step 1's worktree check). Shared resource: the metrics log. — Depends on: 2 — Tests: T10, T11, T12
- [x] 4. **Mode B link script** — hooks/scripts: new `.claude/scripts/link_worktree.py <worktree> | --repair`, stdlib only, per framework ADR 0022 §4. Resolved targets (hard-linked `CLAUDE.md` taken from `<subtree>/CLAUDE.md`, verified as the same file); symlink → junction or hard link fallback; links at every registered path inside the main checkout; root-anchored, idempotent `info/exclude`; no-op without links; refuses a worktree inside the AI-repo. — Depends on: 1 — Tests: T13, T14, T15, T16
- [x] 5. **`/worktree` integration and gitignore lines** — commands/docs: `commands/worktree.md` runs `link_worktree.py` after `git worktree add`, and in mode A offers (never forces) copying `.claude/settings.local.json`. Add `docs/*/.worktree-state/` and `.claude/worktrees/` to `.gitignore.framework-additions`, and `evolution/.worktree-state/` to this repo's `.gitignore`. — Depends on: 4 — Tests: none (prose; checked by `reviewer`)
- [x] 6. **Session brief names the worktree** — hooks/scripts: `session_brief.py` opens with the repo and branch when the session is a linked worktree, and is unchanged otherwise. — Depends on: 2 — Tests: T19
- [x] 7. **Domain 7 safety net** — commands/docs: in `commands/setup-framework.md` Domain 7, the mode B check that the root can hold the links (same volume as the AI-repo, or symlinks available — reversing "may be on another drive" for mode B), and the optional `<worktrees_root>/CLAUDE.md` bootstrap note (append-only, confirm-first, tells the session to stop and run `link_worktree.py --repair`). Close-out lines updated. — Depends on: 4 — Tests: none (AC-08 prose, checked by `reviewer`)
- [x] 8. **Mode C end to end** — hooks/scripts tests: an installed copy ships `link_worktree.py`, and the installed hooks open the registration gate and fire the build/test gate in a worktree of a registered repo. Fix the installer only if the test shows a gap. — Depends on: 1, 4 — Tests: T01, T18
- [x] 9. **Docs** — commands/docs: `docs/workflow/parallel-work.md` (worktree sessions work in every mode, the `--repair` path, and Claude Code's own worktrees in mode B), `.claude/README.md` rows (`link_worktree.py`, `/worktree`), and a `CHANGELOG.md` entry citing framework spec 0004 / framework ADR 0022. — Depends on: 3, 5, 6, 7, 8 — Tests: none
