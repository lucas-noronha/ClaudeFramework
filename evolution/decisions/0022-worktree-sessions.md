---
doc_type: adr
id: 0022
status: accepted
date: 2026-10-04
supersedes: null
superseded_by: null
context_budget: ~2000 tokens
---

# ADR 0022 — A linked worktree is its main checkout's project, with per-checkout state

Like ADR 0001–0021, this documents a decision about *this framework's
own* tooling. **Amends** ADR 0013, 0015 and 0017 (a session's project
comes from the registry *or*, failing that, from git's worktree link),
ADR 0013/0015 (state-file paths gain a per-checkout scope), ADR
0011/0020 (metrics are attributed per checkout) and ADR 0005
(`/worktree` makes the new worktree framework-ready). It supersedes
none of them: each keeps its rule for a main checkout.

## Context

Spec 0004. ADR 0005's parallel work depends on a separate session
opened inside the spec's worktree. Project identity, though, is "this
machine's `CLAUDE_PROJECT_DIR` is a key in `projects.local.json`" (ADR
0013, exact match), and a worktree's path is never a key:

- **Mode C**: the registration gate (ADR 0017) stays closed, so every
  hook is a silent no-op, including the build/test gate. Then
  `project-registration` offers to register the worktree as a second
  project.
- **Mode B**: the three links are never committed, so a fresh worktree
  has no `.claude`, `docs` or `CLAUDE.md`. Even with the links,
  routing misses.
- **Mode A**: works, but metrics go to the worktree's own gitignored
  log. `/metrics` never sees them, and they are deleted with the
  worktree.
- **Modes B/C**: parallel sessions share one `session-handoff.md` per
  subtree and overwrite each other's notes. ADR 0020 attributes events
  to "the most recently started open feature", so two features in
  flight get flagged as overlapped instead of being separated.

## Options considered

- **`/worktree` writes a registry alias per worktree.** Rejected. The
  entry goes stale on `git worktree remove`/prune, because nothing
  removes it. It also misses worktrees made by hand, and Claude Code's
  own `--worktree` ones under `.claude/worktrees/`.
- **Identity by path under the configured worktrees root**
  (`<root>/<repo folder>/<x>` → repo). Rejected. Two repos with the
  same folder name are ambiguous, re-running Domain 7 orphans older
  worktrees, and worktrees outside the root are missed.
- **`git rev-parse --git-common-dir` on every hook call.** Rejected.
  It spawns a subprocess on every hook event, several times per hook,
  when two small file reads give the same answer.
- **Read git's own link files, with no subprocess (chosen).**

## Decision

1. **Identity fallback** in `_registered_subtree`. The exact lookup
   runs first, as today, and an explicit entry always wins. With no
   entry, walk up from `CLAUDE_PROJECT_DIR` to the nearest `.git`. If
   it is a *file*:
   - Read `gitdir: <path>`, which is absolute or relative to the
     worktree root.
   - Read `<gitdir>/commondir`, which is relative to gitdir.
   - The main checkout is the common dir's parent, but **only if the
     common dir is that parent's `.git` directory**.
   - Look up `<main>/<same subpath>` in the registry, with the same
     normalization and Windows case-folding.

   Files are read as UTF-8. Anything unexpected means no fallback, and
   today's behaviour: a `.git` file without `commondir` (submodule,
   `--separate-git-dir`), a bare or renamed common dir, or an
   unreadable file. One resolver also replaces `_main_checkout()`'s
   subprocess. The gate, routing, config, `describe` and
   `project-registration` all inherit the fallback. `describe` gains
   `worktree`: the admin name, the main checkout, and the branch read
   from `<gitdir>/HEAD`. It reports this even when the lookup misses.
2. **State scopes.** `state_file_path` distinguishes *checkout* state
   (the session handoff) from *project* state (the metrics log). In a
   main checkout, both paths are unchanged. In a linked worktree:
   - The handoff goes to `<subtree>/.worktree-state/<admin name>/` in
     modes B/C, and stays in `<worktree>/.claude/` in mode A.
   - Metrics go to the subtree log in modes B/C, and to
     `<main>/.claude/pipeline-metrics.jsonl` in mode A.

   `<admin name>` is the gitdir's basename. Git keeps it unique per
   repo, which a folder name isn't. The dot prefix keeps the folder out
   of census and other doc scanners. Other state files keep today's
   resolution.
3. **Metrics per checkout.** `log_event` stamps `checkout: <admin
   name>` on every event from a linked worktree. `metrics.py` keeps one
   open-feature stack per checkout and keys features by `(checkout,
   feature)`. An event with no `checkout` field belongs to the main
   checkout.
4. **Mode B links.** `.claude/scripts/link_worktree.py <worktree>` mirrors
   whichever of `.claude`, `docs` and `CLAUDE.md` exist as links at
   each registered path inside the main checkout (the root or a
   monorepo subpath) to the same subpath in the worktree:
   - **Link targets** come from the main checkout's *resolved* target.
     For a hard-linked `CLAUDE.md`, that is `<subtree>/CLAUDE.md`,
     verified as the same file. Raw relative link text is never
     copied, because the worktree sits at another depth.
   - **Fallback chain**: symlink, then junction (directories) or hard
     link (`CLAUDE.md`), as in Domain 5.
   - **Excludes**: adds root-anchored patterns (`/<subpath>/docs`, …)
     to `<common dir>/info/exclude`, idempotently.
   - **No-op** when the main checkout has no such links (modes A/C).
   - **`--repair`** walks `git worktree list --porcelain` and recreates
     missing or stale links.

   `/worktree` runs the script after `git worktree add`. In mode A it
   offers to copy `.claude/settings.local.json`, and never forces it.
5. **Per-machine config.** `local_framework_config()` falls back to
   `<main>/.claude/framework.local.json`.
6. **Safety net.** With a worktrees root set, Domain 7 offers
   `<worktrees_root>/CLAUDE.md`, append-only and confirm-first like
   Domain 5 step 10. It tells a session with missing links to stop and
   run `--repair`. In mode B, Domain 7 also validates that the root can
   hold the links. The session brief opens with the repo and branch of
   a worktree session.

## Rationale

Git already records on disk which repo a worktree belongs to. That is
the only signal that doesn't depend on who created the worktree or
where. Checking for an explicit entry first keeps every existing
mapping authoritative. Splitting state by owner (a handoff belongs to
one working tree, a metrics log to one project) is ADR 0013's move,
one level finer.

## Consequences

- **Main checkouts**: no change (NFR-01). Old events with no
  `checkout` field read as main.
- **Per-hook cost**: a walk-up of `stat`s and two reads, and only when
  there is no exact entry. Memoize per process, because one hook
  resolves several times.
- **Silent misses**: failing open means a path-form mismatch (git
  recorded the main checkout through another symlink, short-name or
  MSYS form than the registry key) silently leaves a mode C worktree
  ungated, as today. `describe`'s `worktree` field is the diagnostic.
- **`.worktree-state/` grows forever**: one folder per worktree ever
  used, never cleaned. An admin name reused after removal inherits the
  old handoff note, and any feature it never finished. It needs
  `docs/*/.worktree-state/` in `.gitignore.framework-additions` and
  `evolution/.worktree-state/` in this repo's own `.gitignore`.
- **Concurrent appends to the shared log**: one log now takes appends
  from several sessions. On Windows a CRT append is seek-then-write,
  not atomic, so a collision can lose or merge a line. The reader skips
  bad lines, but a lost `feature_started`/`feature_finished`
  misattributes events. Take a short advisory lock around the append,
  and fail open on timeout.
- **`/implement` starts a feature twice**: step 0 runs `metrics.py
  start` *before* step 1's worktree hand-off, so a feature is started
  in the main checkout and again in the worktree, and the main one
  stays open. Step 0 must move after step 1.
- **Hard links are volume-bound**: junctions reach any local NTFS
  volume, but `CLAUDE.md` needs symlinks or the AI-repo's volume. In
  mode B this reverses Domain 7 step 3's "may be on another drive". A
  hard link also detaches silently when an editor saves by replacing
  the file, and nothing runs `--repair` automatically.
- **Claude Code's own worktrees in mode B**: `--worktree` creates
  `<repo>/.claude/worktrees/<name>`. In mode B that `.claude` is the
  shared link, so every target repo's checkout lands inside
  `<ai-repo>/.claude/worktrees/`. There it is untracked, synced when the
  AI-repo is in OneDrive, and mirroring a `.claude` link into it would
  create a directory cycle. Identity still resolves, but the script
  must refuse a worktree that resolves inside the AI-repo, and
  `.claude/worktrees/` joins `.gitignore.framework-additions`.
  `/worktree` stays the supported path. Redirecting these worktrees
  through a `WorktreeCreate` hook is left for later.
- **Out of scope, accepted**: mode A spec-number collisions across
  branches, moving or removing worktrees, and bare or separate-git-dir
  layouts beyond failing open.

## References

`evolution/product/specs/0004-worktree-sessions.md`,
`evolution/decisions/0005-spec-worktree-lifecycle.md`,
`evolution/decisions/0011-pipeline-metrics.md`,
`evolution/decisions/0013-multi-project-ai-repo.md`,
`evolution/decisions/0015-unified-docs-tree-and-layered-constitution.md`,
`evolution/decisions/0017-user-level-install-mechanics.md`,
`evolution/decisions/0020-proportional-pipeline-cost.md`,
`.claude/hooks/_project_paths.py`, `.claude/hooks/_pipeline_metrics.py`,
`.claude/scripts/metrics.py`, `.claude/commands/worktree.md`,
`.claude/commands/implement.md`, `.claude/commands/setup-framework.md`
