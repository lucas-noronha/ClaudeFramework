---
doc_type: spec
id: 0004
status: implemented
area: adoption-modes
relates_to: [0001]
resumo: How does a Claude Code session opened inside a git worktree get the whole framework (hooks, commands, project routing, state) in every adoption mode?
naoResponde: Where worktrees are placed (the per-machine worktrees root already shipped) or how /implement decides to isolate a spec (framework ADR 0005).
context_budget: ~1500 tokens
tier: structural
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

