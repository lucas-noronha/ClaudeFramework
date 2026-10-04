---
doc_type: workflow
scope: parallel-work
status: active
last_updated: {{DATE}}
context_budget: ~750 tokens
related: [../../.claude/commands/worktree.md, feature-development-guide.md]
---

# Running more than one task at once

## Isolating a whole spec: `/worktree`, now offered automatically

`/implement <spec-path>` (orchestration mode) now checks for a spec's
own worktree itself and offers to create one before starting, per
framework ADR 0005 — you don't have to
remember to run `/worktree` by hand first, though you still can. Either
way it always starts from `origin/{{MAIN_INTEGRATION_BRANCH}}` (or the
local branch, only if it has no pending changes), never from a dirty
state, and the branch is named `task/<spec-short-name>` — matching that
spec's own filename slug is a rule now, not just a convention, since
`/implement` looks the worktree up by that exact name. Open a
**separate** Claude Code session inside the generated worktree and run
`/implement` on the same spec from there — that's what actually lets
you run several specs' sweeps at the same time, each in its own
worktree/session, without them colliding on the same working tree or
the same deterministic build/test gate.

Where the worktree lands is a per-machine choice made in
`/setup-framework`: with a worktrees root configured it's
`<worktrees root>/<repo folder name>/<short-name>`, otherwise the
sibling `../<short-name>`. Worth setting when the repo sits in a synced
folder (OneDrive, Dropbox), where every build output in every worktree
would otherwise sync too.

Isolation stops at the spec, deliberately — a single task never gets a
worktree of its own, no matter how large. Every task in a spec's
`/implement` sweep shares that one worktree, isolated from its siblings
only at the subagent-context level (framework ADR 0004 already provides this);
splitting further would trade a session hand-off per task for isolation
this framework doesn't think is worth that cost. The actual goal —
several *specs* running at once without racing on the same working
tree — is already fully met at the spec level alone.

## Worktree sessions in every adoption mode

A worktree session works in modes A, B and C (framework ADR 0022).
The hooks resolve a linked worktree to its main checkout from git's own
files, so the project's registration, docs and per-machine settings
(`framework.local.json`) are found without re-registering anything. In
a worktree, handoff notes are kept per checkout and the metrics log per
project, with each event tagged by its `checkout`, so `/metrics`
attributes cost per worktree. `session_brief` names the repo and branch
when you start in one.

- **Mode A:** nothing to link; the worktree carries its own `.claude/`
  and `docs/`. `/worktree` offers to copy `settings.local.json`.
- **Mode B:** `.claude`, `docs` and `CLAUDE.md` are links into the
  AI-repo, which a fresh worktree of the code repo doesn't have.
  `/worktree` runs `.claude/scripts/link_worktree.py <worktree>` to
  mirror them (plus an anchored `info/exclude` entry). `--dry-run`
  shows what it would do; `--repair` re-creates links in a worktree
  that lost them (e.g. after a sync tool or a fresh clone). It refuses
  a worktree placed inside the AI-repo.
- **Mode C:** no links; the registration gate simply opens inside a
  worktree of a registered repo.

Claude Code's own `--worktree` is the exception in mode B: because
`.claude` is a link, it lands inside the AI-repo's `.claude/worktrees/`.
Use `/worktree`; `.claude/worktrees/` is gitignored as a safety net.

Don't use subagent `isolation: worktree` or an automatic `--worktree`
flag for this — `/worktree` exists specifically because those tools'
base-branch behavior isn't guaranteed to be
`origin/{{MAIN_INTEGRATION_BRANCH}}`.

## Two independent parts of the same spec, same session

If a spec's `/tasks` output has two tasks that don't read each other's
not-yet-existing output (e.g. one touches only `{{BACKEND_DIR}}/**`,
the other only `{{FRONTEND_DIR}}/**`, and neither depends on the
other's contract), you don't need a second worktree at all.

Running `/implement <spec-path>` (orchestration mode, see
framework ADR 0004) now does this
automatically: it reads every task's `Depends on` field, computes
dependency-ready waves, and dispatches a whole wave's tasks to their
own subagent calls in parallel, one call per task. Reach for the
manual pattern below only outside that case — e.g. two tasks that
belong to *different* specs, or when you deliberately want to run just
two specific tasks by hand instead of sweeping the whole list:
delegate both to their own subagent call, run in parallel, from the
same session — neither touches a file the other does.

**Don't** parallelize a task that changes a contract (e.g. an API
shape) with the task that consumes it — the consumer needs the
producer's change to land first. `/tasks` is responsible for flagging
this dependency explicitly (every task states `Depends on: none | #N`,
not only cross-layer ones); only tasks it marks independent are safe to
run this way, whether via `/implement`'s orchestration or by hand.

## Knowing what's currently in flight

Deliberately **not** a new file to maintain (a tracking doc goes stale
the moment someone forgets to update it — the opposite of "reference,
never duplicate"). Instead:

```
git worktree list
```

tells you every active worktree and its branch. If `/worktree` created
each one as `task/<short-name>` and each spec lives at
`docs/product/specs/NNNN-<short-name>/` (a legacy single-file spec
`NNNN-<short-name>.md` works the same), the branch name alone tells
you which spec a worktree belongs to — no separate bookkeeping needed.
To see a worktree's task-level progress, check that spec's `tasks.md`
(written by `/tasks`) from within that worktree. Inside one spec's
sweep, checkboxes go to `tasks.md` and reviewer lines to
`reconciliation.md`, so parallel tasks don't write the same file
(framework ADR 0024).

## Context hygiene while juggling several tasks

- **`/clear` costs no tokens.** Use it between unrelated tasks in the
  same main session — the highest-return habit for token economy that
  exists, and it's literally free.
- **`/compact` costs tokens** — it reads the entire conversation to
  generate the summary. If you use it, use it early, while the cache
  is still warm, not after the session has gone idle.
- **Don't expect the agent to "decide" when to compact** — what
  already solves this for free is the pipeline's own subagent split:
  every handoff between `triage` → `architect` → `coder` → `reviewer`
  is already a fresh, clean context, with no summarization cost at
  all.

## Never do this in chat

- Don't paste the whole architecture or several ADRs manually — the
  agents already know where to read, via `CLAUDE.md`.
- Calling `/implement <spec-path>` to sweep a whole spec is fine —
  that's orchestration mode's actual job (framework ADR 0004), and each task
  still gets its own isolated subagent call underneath, not one
  subagent working through several tasks in the same context window.
  What still breaks the token economy is asking the *main session* to
  hold and reason about several tasks' worth of code at once instead of
  letting the orchestrator dispatch them.
- Don't skip validating the spec with your stakeholder thinking it'll
  "save a step" — it's the cheapest checkpoint in the entire workflow
  to catch a mistake early.
