---
doc_type: workflow
scope: feature-development-guide
status: active
last_updated: {{DATE}}
related: [ai-first-development.md, parallel-work.md, model-tiering.md, governance-and-observability.md, living-architecture-docs.md, ../architecture/module-structure.md, ../architecture/frontend.md]
context_budget: ~1600 tokens
---

# Practical guide — what do I type in chat

This is the "I sat down to build something, now what?" guide. It exists
so you don't have to re-decide the flow for every feature — just follow
the recipe.

## Before anything

Open Claude Code at the **root of the code repository** (where
`.claude/` and `CLAUDE.md` live). That auto-loads the index — you don't
need to paste architecture context manually into the chat. If you find
yourself pasting the whole spec or re-explaining the architecture in
the conversation, you're duplicating what `CLAUDE.md` already delivers
on its own — avoid it.

## Standard flow, step by step

| # | You type | What happens | When to move on |
|---|---|---|---|
| 1 | `/spec <short description of the idea>` | Generates a draft at `docs/product/specs/NNNN-*.md` (+ a stakeholder-language companion, if your project uses that split) | Whenever the spec doesn't exist yet |
| 2 | *(outside the chat)* Send the spec (or its companion) to your stakeholder | — | Nothing to edit: the next `/plan` asks whether to approve the spec and sets `status: approved` itself (or `abandoned` if the feature gets dropped) |
| 3 | `/plan docs/product/specs/NNNN-*.md` | Triage classifies; trivial stops there, standard gets a short technical plan, structural gets `architect` (+ ADR if needed) plus the same plan | If an ADR was proposed, you approve it manually (`status: accepted`) before moving on |
| 4 | `/tasks docs/product/specs/NNNN-*.md` | Mechanically breaks the plan into small, dependency-annotated tasks | Always |
| 5 | `/implement docs/product/specs/NNNN-*.md` | First offers to isolate this spec in its own worktree (see below); then orchestrates every remaining task: dependency-ordered waves, one subagent per task, parallel within a wave, automatic `reviewer` pass per coder-tier task | Or `/implement <task number>` for just one task — see below |
| 6 | *(automatic)* Hook runs build + tests, per task | Deterministic gate, zero token cost | If it fails, that task's subagent gets the result back before the sweep continues |
| 7 | `/review` | Reviewer does one final, whole-feature pass across the cumulative diff, plus the spec's Definition of Done and "## Reconciliation" completeness | Once every task is checked off — catches cross-task issues the per-task pass in step 5 can't see |
| 8 | Merge (or push + PR, if this spec is in its own worktree — `/review` offers it on Approved) | — | After "Approved" from `/review` |
| 9 *(later, optional)* | `/reconcile docs/product/specs/NNNN-*.md` | Re-checks an already-`implemented` spec against the codebase as it is *now* — no diff, no gate, just "does this still hold" | Any time you suspect drift, or on whatever cadence you like — see `governance-and-observability.md` |

## `/implement`: sweep the whole spec, or just one task

`/implement docs/product/specs/NNNN-*.md` (a spec path) first checks
whether this spec already has its own worktree (branch
`task/<short-name>`) and, if not, asks whether to create one before
starting — worth it if you want to run other specs' sweeps at the same
time, or a clean, spec-scoped diff and PR at the end (see
framework ADR 0005). Say yes and it creates
the worktree, then stops so you can open a new session there and
re-run the same command — this framework's hooks only work correctly
in the session that actually started in that directory. Say no (or
it's a small, trivial-tier spec not worth the extra session) and it
proceeds right here.

Either way, it then runs every unchecked task to completion on its
own: it reads each task's `Depends on` field, computes what's safe to
run in parallel, and dispatches each task to its **own** subagent
call — so a wave of three independent tasks means three isolated
subagent contexts, dispatched in parallel, not one subagent working
through three tasks in the same context window. That isolation, not
manual pacing, is what keeps a sweep from polluting context; see
framework ADR 0004.

Use `/implement <task number or description>` instead when you want
just that one task — same routing (`quickfix`/`coder`), same
auto-review for coder-tier work, same checkbox update, just scoped to
one task instead of the whole remaining list.

## For a small change: the fast lane

If the change doesn't deserve a spec, describe it instead:

```
/quick fix the typo in the checkout confirmation email
```

`/quick` classifies the request with `triage`, no spec required
(framework ADR 0020):

- **trivial** → `quickfix` fixes it directly; the build/test gate runs;
  no spec file, no review. You get the tier and the gate result back.
- **standard** → it offers a *lite spec*: one file with FRs, ACs and the
  task list, which you approve on the spot, then `/implement` runs it.
  `/plan` is skipped unless you ask for it.
- **structural** → it stops and points you at the full `/spec` →
  `/plan` path, because that's where the ADR gets written.

Only the ceremony shrinks: the constitution, the gate and the scope
rules are the same as in the full path. `/implement <one task>` still
works for a single task, and `/metrics` shows what each lane actually
cost on this project.

## Keeping architecture docs true

If the project enabled the census (its config's `census` block), run
`/update-docs` from time to time. It checks the docs against the
integration branch, routes drift, documents every commit since the last
sync, and moves its watermark only when nothing is left out. A drafted
doc becomes trustworthy through `/update-docs promote <doc>`. See
`living-architecture-docs.md`.

## Recording a decision with no task attached

If you just decided something outside any spec (e.g. switching a CI
provider, adopting a new convention), skip the whole pipeline and run
`/adr <short description of the decision>` directly — see
`.claude/commands/adr.md`.

## Running more than one task, or more than one spec, at once

See `parallel-work.md` for isolating a whole spec in its own worktree
(now offered automatically by `/implement`), nesting a worktree for one
unusually heavy task, running two independent tasks of the same spec in
parallel from one session, and what to check to see what's currently in
flight.

## Turning on the deterministic gate (hook)

`.claude/settings.example.json` includes a hook that runs your
project's build + tests automatically whenever a code-writing subagent
finishes (read-only subagents skip it, framework ADR 0020). `/setup-framework`
does these steps for you; by hand:

1. Rename it to `.claude/settings.json`.
2. Put your actual build/test command in `.claude/project-config.json`
   as `build_test_cmd` (the hook reads it there).
   It's a single slot — for a two-stack monorepo (e.g. a .NET backend +
   a React frontend, this framework's own `auto_format.py.example`
   default), chain both stacks explicitly rather than leaving one
   uncovered, e.g. `dotnet test {{BACKEND_DIR}} && npm --prefix
   {{FRONTEND_DIR}} test`. Running both on every edit is the safe
   default; only split it per-stack (e.g. via a hook that checks which
   `{{BACKEND_DIR}}`/`{{FRONTEND_DIR}}` the edited file falls under) if
   the combined runtime actually becomes a bottleneck.
3. Rename `.claude/hooks/auto_format.py.example` to `auto_format.py`
   and replace its two example branches with your stack's real
   formatter/linter commands (see the comments in that file).
4. Check the current hooks syntax against the official Claude Code
   documentation before trusting the example blindly — this is a
   feature that evolves frequently.

Two more are already active with no setup: `secret_leak_guard.py`
blocks a write matching a high-confidence credential pattern, and (if
you keep `docs/constitution.md`) every pipeline stage checks it
automatically. Rename `dependency_audit.py.example` the same way as
`auto_format.py.example` once you've trimmed it to your real
ecosystem(s). See `governance-and-observability.md` for all of this,
plus the git-ignored `.claude/pipeline-metrics.jsonl` event log that
accumulates as you use the pipeline.
