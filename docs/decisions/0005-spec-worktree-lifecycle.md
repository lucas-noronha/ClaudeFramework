---
doc_type: adr
id: 0005
status: proposed
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~1150 tokens
---

# ADR 0005 — Tie a spec's implementation to its own worktree, closing with a pushed branch + PR

Like ADR 0001–0004, this documents a decision about *this framework's
own* tooling (kept as a worked example).

## Context

ADR 0004 gave `/implement`'s orchestration mode per-task subagent
isolation and an explicitly scoped `reviewer` pass, which is enough
when one spec's sweep runs alone in one session. It does not help with
two things the isolated-subagent design was never meant to solve:
running **two different specs'** `/implement` sweeps at the same time
(they'd race on the same working tree and the same deterministic
build/test gate), and keeping a single large spec's cumulative diff
against `{{MAIN_INTEGRATION_BRANCH}}` from growing long and hard to
review. `.claude/commands/worktree.md` already exists precisely for
git-level isolation, and `docs/workflow/parallel-work.md` already
documents a `task/<short-name>` branch-naming convention that assumes
one worktree per spec — but nothing actually connects `/plan`/`/tasks`/
`/implement` to that convention; it's manual, and easy to forget.

A concrete constraint shapes every option here, not a vague one:
`/worktree`'s own file already explains why it hands off to a
**separate** Claude Code session instead of `cd`-ing in place — this
framework's hooks (`.claude/settings.json`) are wired to
`${CLAUDE_PROJECT_DIR}`, fixed at session start. A session that just
`cd`s into a worktree wouldn't move where the deterministic build/test
gate, `spec_status_sync.py`, or the decision/spec index hooks actually
look — they'd keep acting on the original checkout. `/implement`'s
orchestration mode inherits this exact constraint now that it's the
thing actually driving implementation work, not just `/worktree`.

## Options considered

- **Leave worktree usage entirely manual (status quo).** Simplest, but
  doesn't scale to running several sweeps at once, and the
  `task/<short-name>` convention stays a documentation-only suggestion
  nothing checks.
- **Have `/implement` create *and use* the worktree in the same
  session** (create, then `cd`, then keep orchestrating). Rejected —
  breaks the hook-targeting constraint above: the deterministic gate
  and the spec-tracking hooks would keep silently acting on the
  original checkout, not the isolated one, which is worse than no
  isolation at all because it *looks* isolated.
- **`/implement` checks for / offers a spec-scoped worktree, then hands
  off to a new session there (chosen).** Reuses `/worktree`'s already
  proven, hook-safe pattern instead of inventing a riskier same-session
  relocation. Triggered from the point where it actually matters
  (starting a real implementation sweep) instead of left for the user
  to remember to run `/worktree` first.

## Decision

- **`/implement` orchestration mode** gains a first step, before wave
  computation:
  - Check `git worktree list` for a worktree whose branch is
    `task/<spec-short-name>` (the convention `parallel-work.md` already
    documents, now load-bearing instead of just descriptive).
  - If the current session's working directory **is** that worktree:
    proceed directly — nothing else about ADR 0004's design changes.
  - If it doesn't exist yet: ask (`AskUserQuestion`) whether to isolate
    this spec's implementation in its own worktree before starting.
    Worth it specifically when the user wants to run this sweep
    concurrently with other work, or wants a clean, spec-scoped diff
    and PR at the end — suggest yes by default for standard/structural
    tiers, genuinely optional for trivial. If yes: create it using
    `/worktree`'s own steps exactly (branch `task/<spec-short-name>`,
    pinned to `origin/{{MAIN_INTEGRATION_BRANCH}}` — never re-derive
    that logic here, reference it), then **stop** and tell the user to
    open a new session there and re-run `/implement` from inside it —
    the same hand-off `/worktree` already uses. If no: proceed in the
    current working tree exactly as ADR 0004 already specifies.
  - If a worktree already exists for this spec but the **current**
    session isn't in it: warn and point at the existing path — don't
    silently proceed in the wrong tree, which is exactly the
    look-isolated-but-isn't case this ADR exists to avoid.
- **`/worktree`** gains one added rule: when isolating a whole spec (as
  opposed to an ad hoc one-off task), name `$ARGUMENTS` after the
  spec's own short-name, so the branch and the spec filename
  (`docs/product/specs/NNNN-<short-name>.md`) match exactly — this is
  what lets `/implement` find the right worktree mechanically instead
  of guessing.
- **Granularity stops at the spec, deliberately.** A task never gets a
  worktree of its own, even for an unusually large or risky one — a
  dispatched `coder` subagent runs inside the orchestrating session, so
  the same `${CLAUDE_PROJECT_DIR}` constraint above applies to it too;
  only a genuinely separate Claude Code session, opened by a human,
  gets a worktree's hooks wired correctly, and multiplying that
  hand-off per task would add more session-juggling overhead than the
  isolation is worth. Every task in a spec's sweep keeps sharing that
  spec's one worktree, isolated from its siblings only at the
  subagent-context level ADR 0004 already provides — that's enough:
  the actual goal (several *specs* running at once, without racing on
  the same working tree) is fully met at the spec level alone.
- **Closing a spec's worktree**: `/review`'s Approved path, when run
  from inside a spec's own worktree, now explicitly offers (confirmed,
  never automatic — pushing and opening a PR are both visible to
  others) to push the branch and open a PR, naming
  `superpowers:finishing-a-development-branch` (already referenced
  there) as the discipline behind how to integrate. Declining, or not
  being in a spec worktree at all, leaves `/review`'s behavior exactly
  as ADR 0004 already specifies.

## Rationale

Reuses `/worktree`'s already-proven, hook-safe hand-off instead of a
same-session relocation this framework's own hook design can't
actually support; makes `parallel-work.md`'s existing naming convention
load-bearing instead of decorative; delivers concurrent per-spec
`/implement` sweeps and a closed loop to PR without touching ADR 0001's
sequencing guarantee or ADR 0004's per-task mechanics — this sits one
level above both, at the git/session boundary.

## Consequences

- Isolating a spec costs at least one extra session hand-off (create,
  then reopen elsewhere) — the same cost `/worktree` already asks for,
  paid only when the user opts in, never forced.
- A spec implemented without its own worktree (declined, or not worth
  it for a small one) works exactly as ADR 0004 describes — this adds
  an option, it doesn't require one.
- Two specs can now safely run `/implement` sweeps at the same time,
  each in its own worktree/session — the actual capability being
  added — but the user opens those sessions themselves; nothing here
  spawns them automatically.
- `/tasks`'s "Depends on" annotations still govern parallelism *within*
  one spec's own sweep (ADR 0004); worktrees are the *between-specs*
  isolation layer — a different axis, not a replacement. A single task
  never gets its own worktree, no matter how large — that would trade
  a small amount of extra isolation for a session hand-off per task,
  which isn't a trade this framework makes.
- The PR hand-off assumes a `gh`-authenticated remote, same assumption
  `/worktree` already makes about `origin`; a project without GitHub
  degrades this to "push the branch and open a PR through whatever your
  remote's own tooling is."

## References

`docs/decisions/0001-tooling-agents-commands-skills.md`,
`docs/decisions/0004-plan-tasks-implement-rebalance.md`,
`docs/workflow/parallel-work.md`, `.claude/commands/worktree.md`,
`.claude/commands/implement.md`, `.claude/commands/review.md`
