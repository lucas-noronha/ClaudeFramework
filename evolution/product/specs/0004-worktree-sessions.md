---
doc_type: spec
id: 0004
status: implemented
area: adoption-modes
relates_to: [0001]
resumo: How does a Claude Code session opened inside a git worktree get the whole framework (hooks, commands, project routing, state) in every adoption mode?
naoResponde: Where worktrees are placed (the per-machine worktrees root already shipped) or how /implement decides to isolate a spec (framework ADR 0005).
context_budget: ~1500 tokens
---

# Worktree sessions — the framework follows the code into every worktree

## Feature name

A session opened inside a worktree of a framework-managed repo behaves exactly like a session
in its main checkout: the same project, hooks, commands and gates, in modes A, B and C.

## Business context

Parallel spec work (framework ADR 0005) depends on opening a **separate session inside the
spec's worktree**. `/worktree` and `/implement` tell the user to do exactly that. Today that
session works in mode A only:

- **Mode B**: the `.claude`, `docs` and `CLAUDE.md` links are never committed, so a fresh
  worktree has none of them. No hooks, no `/implement`, no agents. Even with links, the
  registry has no entry for the worktree's path, so routing fails.
- **Mode C**: commands load (user-level), but the registration gate (0001 FR-03) sees an
  unregistered path. Every hook is a silent no-op, including the build/test gate. Worse,
  `/cfw-implement`'s `project-registration` step would register the worktree as a **second
  project**.
- **Mode A**: works, but a worktree's metrics land in its own gitignored
  `.claude/pipeline-metrics.jsonl`. `/metrics` never sees them, and they are lost with the
  worktree.

Parallel sessions also share per-project state files in modes B/C (one `session-handoff.md`
per subtree), so they overwrite each other's handoff notes. Metrics attribution ("the most
recently started open feature") mixes up two features running at once.

The problem in one sentence: the framework's parallel-work feature is unusable in modes B and
C, and silently unsafe in mode C, because a worktree is not recognized as the repo it belongs
to.

## Functional requirements

- FR-01: A session whose `CLAUDE_PROJECT_DIR` is inside a **linked git worktree** resolves to
  the same project as the repo's main checkout. Identity comes from git's own on-disk link
  files (`<worktree>/.git` → `gitdir` → `commondir`), read without running git. It does not
  depend on where the worktree sits, so `/worktree`'s worktrees, Claude Code's own worktrees
  and hand-made ones all resolve.
- FR-02: The subpath is preserved. A registered `<main>/packages/x` also routes
  `<worktree>/packages/x`.
- FR-03: Precedence: an explicit registry entry for the session's path always wins; the git
  fallback applies only when there is none.
- FR-04: In a user-level install, the registration gate opens for a worktree of a registered
  repo. `project-registration` treats it as registered, so it never offers to register it
  again. The probe (`describe`) reports that the session is a worktree and names its main
  checkout.
- FR-05: Per-checkout session state. The main checkout keeps today's handoff path. A linked
  worktree's handoff goes to a per-worktree location that never collides with the main
  checkout or with another worktree. In modes B/C it lives inside the project subtree,
  gitignored; it is never written into the target repo.
- FR-06: Metrics are one log per project. Every event records the checkout it came from, and
  `/metrics` attributes each event to the open feature **of its own checkout**. In mode A a
  worktree's events go to the main checkout's log.
- FR-07: Mode B — a deterministic script mirrors the main checkout's three framework links
  (`.claude`, `docs`, `CLAUDE.md`) into a worktree, with the same symlink → junction → hard
  link fallback Domain 5 uses. It also adds the three names to the repo's shared
  `info/exclude`, never to a committed file. It is a no-op when the main checkout has no such
  links (modes A and C). A `--repair` mode fixes every worktree listed by
  `git worktree list`.
- FR-08: `/worktree` runs the FR-07 script right after creating a worktree. In mode A it
  offers to copy `.claude/settings.local.json` into the new worktree, and never copies it
  unasked.
- FR-09: Per-machine framework settings (`framework.local.json`, e.g. the worktrees root) are
  found from inside a worktree too, by falling back to the main checkout's `.claude/`.
- FR-10: When a worktrees root is configured, `/setup-framework` offers to write a bootstrap
  `CLAUDE.md` at that root, as the safety net for mode B. Claude Code loads it for every
  session below the root. It tells the session to stop and run the FR-07 repair if the
  framework links are missing. Same append-only, confirm-first discipline as Domain 5
  step 10.
- FR-11: The session brief opens with which repo, and which spec branch, a worktree session
  belongs to.
- FR-12: In mode B, Domain 7 validates that the worktrees root can hold the links: the same
  drive as the AI-repo, or symlinks available. Otherwise it says why and asks again.

## Non-functional requirements

- NFR-01: Every existing setup keeps working unchanged. Sessions in a main checkout resolve
  exactly as before, with the same state paths. Metric events without a checkout field count
  as the main checkout's. No new config is required.
- NFR-02: The worktree lookup costs file reads only, no subprocess, in every hook call. It
  fails open: an unreadable or unexpected git layout degrades to today's behaviour, never to
  a crash or a block.
- NFR-03: Zero footprint is kept. Mode B/C never commit anything to the target repo; the only
  write inside its `.git/` is the `info/exclude` lines from FR-07.
- NFR-04: A user-level install gets all of this through a normal installer upgrade.

## Explicitly out of scope

- Spec-number collisions between branches in mode A (two worktrees can each create the same
  `NNNN`). Low risk, accepted.
- Moving or cleaning up worktrees (`git worktree move`/`remove`).
- Changing where worktrees are placed (already shipped: per-machine worktrees root).
- Bare repositories and `--separate-git-dir` layouts, beyond failing open (NFR-02).

## Roles and permissions involved

A single developer on their own machine. FR-07 and FR-10 write only where that developer's
own setup already writes (their worktree, their worktrees root, the repo's local
`info/exclude`), and only after `/worktree` or `/setup-framework` runs.

## Related specs

- 0001-mode-c-hardening — extends FR-03 (registration gate) and FR-09 (registration probe) to
  linked worktrees of a registered repo.

## Acceptance criteria

- [ ] AC-01: Mode C — in a worktree of a registered repo, hooks run (the build/test gate
  fires), `describe` reports `registered: true` with the main checkout's subtree, and
  registration is not offered. (FR-01, FR-03, FR-04)
- [ ] AC-02: The same holds for a worktree outside the worktrees root and for a monorepo
  subfolder session. An explicit registry entry for a worktree path overrides the fallback.
  (FR-01, FR-02, FR-03)
- [ ] AC-03: Mode B — after `/worktree`, the worktree has working `.claude`, `docs` and
  `CLAUDE.md` links, `git status` there shows none of them, and `--repair` restores a deleted
  link. Nothing is created in modes A/C. (FR-07, FR-08)
- [ ] AC-04: Two worktree sessions plus the main session each keep their own handoff note.
  Two features open in different checkouts are attributed correctly by `/metrics`. A mode A
  worktree's events appear in the main checkout's `/metrics`. (FR-05, FR-06)
- [ ] AC-05: Every pre-existing test passes unchanged, and a main checkout produces the same
  `describe` output and state paths as before this spec. (NFR-01)
- [ ] AC-06: A worktree with a corrupt or unexpected `.git` file degrades to today's
  behaviour, with no exception. (NFR-02)
- [ ] AC-07: From inside a mode A worktree, `worktree-path` honours the main checkout's
  `framework.local.json`. (FR-09)
- [ ] AC-08: Domain 7 offers the root `CLAUDE.md` (FR-10) and validates the drive in mode B
  (FR-12). The session brief names the repo and branch of a worktree session (FR-11).

## Impact on existing architecture

Amends the project-identity rule of framework ADR 0013/0015/0017: a session's project is
resolved from the registry *or, failing that, from git's worktree link*. It adds a
per-checkout dimension to the state-file routing (framework ADR 0013) and to metrics
attribution (framework ADR 0011/0020). Expected to need a new framework ADR at `/plan`.

## Reconciliation

- [task 1] FR-01: matches spec
- [task 1] FR-02: matches spec
- [task 1] FR-03: matches spec
- [task 1] FR-04: matches spec
- [task 1] FR-09: matches spec
- [task 1] AC-01: matches spec
- [task 1] AC-02: matches spec
- [task 1] AC-05: matches spec
- [task 1] AC-06: matches spec
- [task 1] AC-07: matches spec
- [task 1] NFR-01: matches spec
- [task 1] NFR-02: matches spec
- [task 2] FR-05: matches spec
- [task 2] AC-04: matches spec (partial: handoff part; metrics part is task 3)
- [task 4] FR-07: matches spec
- [task 4] AC-03: matches spec (script half; the /worktree call is task 5)
- [task 4] NFR-03: matches spec
- [task 3] FR-06: matches spec
- [task 3] AC-04: matches spec (metrics half; task 2 covers the handoff half)
- [task 3] NFR-01: matches spec (events without `checkout` count as main; a main-only log renders as before)
- [task 5] FR-07: matches spec (`/worktree` runs the link script, handles exit 1/2, names `--repair`)
- [task 5] FR-08: matches spec
- [task 5] AC-03: matches spec (the `/worktree` half; gitignore lines in place)
- [task 6] FR-11: matches spec
- [task 6] AC-08: matches spec (brief part: worktree header names repo and branch; main brief unchanged)
- [task 7] FR-10: matches spec (optional root `CLAUDE.md` note, append-only, confirm-first, tells the session to run `--repair`)
- [task 7] FR-12: matches spec (mode B volume/symlink check; "any drive" reversed for mode B only)
- [task 7] AC-08: matches spec (setup part)
- [task 8] AC-01: matches spec
- [task 8] FR-04: matches spec
- [task 8] NFR-04: matches spec
- [task 9] docs: matches spec

## Technical plan

**Tier:** structural. **ADR:** framework ADR 0022
(`evolution/decisions/0022-worktree-sessions.md`, `proposed`). `/tasks`
and `/implement` wait until it is accepted.

### Approach, in dependency order

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

### Scope check

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

### Definition of Done

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

### Test plan

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
