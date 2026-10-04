---
doc_type: spec-plan
spec: 0004
summary: The technical plan: approach, scope check, Definition of Done and Test plan.
context_budget: ~1700 tokens
---

# Technical plan

**Tier:** structural. **ADR:** framework ADR 0022
(`evolution/decisions/0022-worktree-sessions.md`, `proposed`). `/tasks`
and `/implement` wait until it is accepted.

## Approach, in dependency order

1. **Resolver** (`.claude/hooks/_project_paths.py`). Add one memoized
   linked-worktree resolver. It walks up from `CLAUDE_PROJECT_DIR` to the
   nearest `.git`; for a file, it follows `gitdir:` → `commondir`, and
   accepts only a common dir named `.git`. It returns the admin name,
   the main checkout, the subpath and the branch (read from
   `<gitdir>/HEAD`).
   - `_registered_subtree` uses it as a fallback after the exact match.
     It tries the normalized and the realpath forms of
     `<main>/<subpath>`.
   - `_main_checkout()` drops its subprocess and uses the resolver.
   - `local_framework_config()` and `get_worktrees_root(project_dir=None)`
     fall back to `<main>/.claude/`.
   - `describe` gains `worktree` (`null` in a main checkout).
2. **State scopes.** Add `state_file_path(project_dir, filename,
   scope=None)`:
   - `None` keeps today's resolution, so plugin-gap and every other
     caller are unchanged.
   - `"checkout"` is for the handoff. In a worktree it resolves to
     `<subtree>/.worktree-state/<admin>/` (modes B/C) or
     `<worktree>/.claude/` (mode A).
   - `"project"` is for metrics. In a mode A worktree it resolves to
     `<main>/.claude/`.
   - Wire `session_handoff.py` and `session_brief.py` to `checkout`, and
     `_pipeline_metrics.py` and `metrics.py` to `project`.
3. **Metrics.** `log_event` stamps `checkout: <admin>` from a worktree
   and appends under a short advisory lock (`msvcrt.locking` /
   `fcntl.flock`) that fails open. `metrics.py` keeps one open-feature
   stack per checkout and keys features by `(checkout, feature)`.
   `implement.md` moves step 0 (feature markers) after step 1
   (worktree check/hand-off).
4. **Mode B links.** New `.claude/scripts/link_worktree.py <worktree> |
   --repair` (stdlib only), per ADR 0022 §4:
   - Link targets come from the resolved main-checkout targets, with a
     hard-linked `CLAUDE.md` taken from `<subtree>/CLAUDE.md`.
   - Fallback chain: symlink → junction or hard link.
   - It adds root-anchored, idempotent `info/exclude` lines.
   - It is a no-op without links, and refuses a worktree that resolves
     inside the AI-repo.
   - `worktree.md` runs it after `git worktree add`, and in mode A
     offers to copy `settings.local.json`.
5. **Setup, brief, docs.**
   - Domain 7 gains the mode B drive/symlink check (reversing "may be on
     another drive" for mode B) and the optional root `CLAUDE.md` offer.
   - `session_brief.py` opens with the repo and branch of a worktree
     session.
   - Gitignore: add `docs/*/.worktree-state/` and `.claude/worktrees/`
     to `.gitignore.framework-additions`, and `evolution/.worktree-state/`
     to this repo's `.gitignore`.
   - Update `parallel-work.md`, `.claude/README.md` and `CHANGELOG.md`.
   - The installer already ships every `.claude/scripts/*` file. Only a
     test is needed.

## Scope check

None of these are ruled out by the spec. Each one is a required part of
an FR, flagged here rather than folded in silently:

- **The metrics append lock and the `implement.md` reorder** are needed
  for FR-06/AC-04 to hold with parallel sessions.
- **Refusing worktrees inside the AI-repo, plus the `.claude/worktrees/`
  ignore line**, are needed so FR-07 doesn't create a directory cycle or
  commit checkouts into the AI-repo (NFR-03).

Constitution: no conflict. There are no secrets and no new dependencies
(stdlib only, Principle V). The script writes only to the worktree and
to the repo's local `info/exclude` (Principle IV).

## Definition of Done

- [ ] `python -m unittest discover -s tests -t tests` passes, with the
  Test plan below added. Every test that passed before still passes
  unchanged (AC-05).
- [ ] `reviewer` approved.
- [ ] AC-01 to AC-07 are covered by the tests below. AC-08's
  `/setup-framework` prose (FR-10, FR-12) is checked by `reviewer`
  against the spec text.
- [ ] In a main checkout, `describe` output and state paths match
  pre-change values, apart from the new `worktree: null` key (NFR-01).
- [ ] The installer dry run lists `link_worktree.py`, and an installed
  hook opens the gate in a worktree (NFR-04).
- [ ] Framework ADR 0022 is `accepted` before implementation starts.

## Test plan

- T01: mode C — a hook run from a worktree of a registered repo is not
  gated, and the build/test gate fires — AC-01, FR-04
- T02: `describe` in a worktree reports `registered: true`, the main
  checkout's subtree and `worktree` {admin, main, branch} — AC-01, FR-04
- T03: `describe` reports `worktree` even when the main checkout isn't
  registered — FR-04
- T04: a worktree outside the worktrees root resolves the same way —
  AC-02, FR-01
- T05: a monorepo subfolder session (`<wt>/packages/x`) routes to
  `<main>/packages/x`'s entry — AC-02, FR-02
- T06: an explicit registry entry for a worktree path overrides the
  fallback — AC-02, FR-03
- T07: corrupt `.git` file, missing `commondir`, or a common dir not
  named `.git` → today's behaviour, no exception — AC-06, NFR-02
- T08: in a main checkout, `describe` and the state paths are unchanged
  — AC-05, NFR-01
- T09: main checkout plus two worktrees keep three distinct handoff
  files; modes B/C use `.worktree-state/<admin>/` — AC-04, FR-05
- T10: a mode A worktree's metric events land in the main checkout's
  log — AC-04, FR-06
- T11: `metrics.py` attributes two features open in different checkouts
  to the right feature; legacy events with no `checkout` count as main —
  AC-04, FR-06, NFR-01
- T12: N parallel processes appending to one log yield N valid lines —
  FR-06
- T13: `link_worktree.py` in mode B creates working `.claude`, `docs`
  and `CLAUDE.md` links, `git status` stays clean, and the excludes are
  anchored and idempotent — AC-03, FR-07
- T14: `--repair` recreates a deleted link — AC-03, FR-07
- T15: `link_worktree.py` is a no-op in modes A and C — AC-03, FR-07
- T16: `link_worktree.py` refuses a worktree that resolves inside the
  AI-repo — FR-07, NFR-03
- T17: `worktree-path` from inside a mode A worktree honours the main
  checkout's `framework.local.json` — AC-07, FR-09
- T18: the installer installs `link_worktree.py`, and the installed
  resolver opens the gate in a worktree — NFR-04
- T19: the session brief in a worktree names the repo and branch —
  AC-08, FR-11

