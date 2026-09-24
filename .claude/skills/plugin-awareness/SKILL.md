---
name: plugin-awareness
description: Absorbed discipline from this machine's Core plugins (works with or without them installed), plus how to suggest an Optional plugin/MCP without installing it yourself. Applies whenever coder, quickfix, architect, or reviewer are working, regardless of pipeline stage.
applies_to: [coder, quickfix, architect, reviewer]
---

Full catalog and rationale: `docs/workflow/plugin-integrations.md`,
`docs/decisions/0002-plugin-integration.md`,
`docs/decisions/0003-superpowers-sdd-wrapping.md`,
`docs/decisions/0004-plan-tasks-implement-rebalance.md`. This file is
what you act on; those are why.

The user interacts with this framework's own commands only
(`/spec`, `/plan`, `/tasks`, `/implement`, `/review`, `/worktree`,
etc.) — never with a plugin directly. Any use of a Core plugin below
happens inside your own steps, invisibly to the user; you report the
outcome (a finding, a simplification), never "I called plugin X."
`/spec`, `/plan`'s own plan-writing step (not the `architect`
delegation), and `/implement`'s orchestration logic run directly in the
main thread with no subagent of their own to hold this instruction, so
they carry the equivalent inline in their own command bodies instead of
through this skill's `applies_to` list — still the same convention,
just written where it has to live.

## 1. Absorbed discipline — applies whether or not the plugin is installed

- **Brainstorming before spec** (from `superpowers`): before drafting a
  spec from a rough idea, explore intent, requirements, and design
  questions explicitly rather than jumping straight to filling the
  template — that's what surfaces the "unclear, ask" list `/spec`
  already requires.
- **Problem vs. solution check** (same discipline, `/spec`'s own step):
  state the actual business problem separately from the solution
  described, and flag it as an "unclear, ask" item if the solution
  doesn't obviously follow from that problem — don't formalize a
  confidently-described but possibly-wrong feature just because it was
  asked for clearly. This is the cheapest point in the whole pipeline to
  catch that.
- **Write the plan before the checklist** (from `superpowers`): before
  a validated spec gets broken into tasks, think through the actual
  technical approach — what changes, which files/modules, the real
  risk points — as a short written plan proportional to the tier
  `triage` assigned, plus a Definition of Done and a Test plan (one
  line per expected unit test) numbered against the spec's own
  `FR-NN`/`AC-NN` items, never free-floating. That's `/plan`'s job;
  `/tasks` only mechanically sequences whatever `/plan` already
  decided (including distributing the Test plan's entries one-to-one
  across tasks), it doesn't reopen that judgment.
- **Review against the stated test list, not invented coverage** (from
  the same discipline): when checking that tests exist, check them
  against the spec's own Test plan entries first — a diff with tests
  that don't match any listed scenario isn't automatically fine just
  because tests exist.
- **Dependency-aware parallel dispatch** (from `superpowers`): when
  running several independent tasks from the same spec, isolate each
  in its own subagent call and confirm two tasks are actually
  independent (no shared file, no shared contract) before running them
  at the same time — don't infer that from a task's one-line
  description alone.
- **Test-first discipline** (from `superpowers`): before writing
  implementation code, restate the expected behavior as a test that
  fails for the right reason first. Don't write the implementation and
  then backfill a test that merely confirms what you already wrote.
- **Systematic debugging** (from `superpowers`): when something breaks
  unexpectedly, form one specific hypothesis about the cause and check
  it before changing code — don't iterate by guessing and rerunning.
- **Verification before claiming done** (from `superpowers`): before
  marking any task complete, checking a box, or reporting a fix, run
  the actual verification command and read its output — don't infer
  success from the diff looking right.
- **Technical rigor on review feedback** (from `superpowers`): when
  `reviewer` returns findings, verify each one is actually correct
  before implementing it — don't apply feedback performatively just
  because it was said with confidence.
- **Review rigor** (from `code-review` / `pr-review-toolkit`): a review
  pass separates real correctness bugs from style/simplification
  opinions, and explicitly checks for silent failures — a caught
  exception that's swallowed, a fallback that masks a real error
  instead of surfacing it.
- **Explicit review scope, never a self-computed diff**: `reviewer`
  only ever reviews the exact scope it was handed — a task's own file
  list from `/implement`'s orchestration mode, or the whole cumulative
  diff from `/review`. It never runs a bare `git diff` itself and calls
  that "the" diff, and any complementary tool it invokes
  (`code-review`, `pr-review-toolkit`, `requesting-code-review`) gets
  told the same explicit scope, never left to compute its own — during
  orchestration mode the working tree holds several tasks' uncommitted
  changes at once, so an unscoped diff would review work that isn't the
  task in question.
- **Simplification pass** (from `code-simplifier`): once an
  implementation is green, a second look for unnecessary abstraction,
  dead branches, or duplicated logic is part of finishing the task, not
  optional polish.
- **Deliberate git isolation before parallel work** (from
  `superpowers`): before starting a task meant to run in its own
  worktree, confirm the workspace is actually based on a clean,
  known-good ref rather than assuming whatever's checked out locally is
  safe to branch from — that's `/worktree`'s whole job.

If the matching Core plugin *is* installed and enabled this session,
`coder`/`reviewer` (and `/spec`/`/plan`/`/implement`/`/review`/`/worktree`
themselves) invoke it directly via the `Skill` tool as a complementary
pass instead of relying only on the paragraphs above — see their own
agent/command bodies for exactly when. `/tasks` never invokes one — per
ADR 0004 it's pure mechanical decomposition, no technical judgment to
back with a skill. `quickfix` never invokes a
plugin directly (no `Skill` tool, deliberately kept cheap per
`docs/decisions/0002-plugin-integration.md`) — the absorbed paragraphs
above are its floor and its ceiling. Either way, the standard above is
the floor, not the plugin's job alone.

## 2. Suggesting an Optional plugin/MCP — judgment call, never automatic

Language-server gaps are already caught deterministically at session
start by `.claude/hooks/plugin_gap_check.py` — don't re-check that
yourself.

For everything else: if you notice yourself (or the task) doing
repeated manual work that a specific *official* plugin or MCP server
would replace — e.g. hand-parsing Azure DevOps work items or PR links
when the `azure-devops` MCP isn't configured, or manually redoing a
multi-file review checklist `pr-review-toolkit` already automates —
say so once, as a plain one-line suggestion pointing at
`/setup-framework` ("this looks like recurring Azure DevOps lookups —
`/setup-framework` can help you wire up the `azure-devops` MCP if
that's useful here"). Rules:

- Only name plugins/MCPs listed in `docs/workflow/plugin-integrations.md`
  — never suggest an unfamiliar third-party marketplace entry you
  haven't verified.
- Say it once per task, not on every turn.
- Never install or configure anything yourself — `/setup-framework` is
  the only place installation happens, and only with the user's
  explicit confirmation there.
