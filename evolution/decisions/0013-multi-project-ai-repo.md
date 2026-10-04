---
doc_type: adr
id: 0013
status: accepted
date: 2026-09-25
supersedes: null
superseded_by: 0015
context_budget: ~1050 tokens
---

# ADR 0013 — One AI-repo backs several target repos: one shared `.claude/`, per-machine routing plus per-project config

Like ADR 0001–0012, this documents a decision about *this framework's
own* tooling.

## Context

Domain 5 of `/setup-framework` (external AI-repo mode) lets a separate
**AI-repo** back a code **target repo** through three local,
never-committed links at the target's root (`.claude`, `docs`,
`CLAUDE.md`), so the target repo carries zero Claude-related footprint
in its own git history. It currently assumes 1:1 — one AI-repo, one
target repo.

Checking every hook in `.claude/hooks/` first: all 17 resolve paths
relative to `CLAUDE_PROJECT_DIR`, never a hardcoded or absolute path.
So the agents, commands, skills and hooks are already
project-agnostic. Three things do break if a second target repo links to
the same AI-repo today:

1. **Per-project state physically lives inside `.claude/`** —
   `session_handoff.py` writes `<project>/.claude/session-handoff.md`,
   `_pipeline_metrics.py` appends `<project>/.claude/pipeline-metrics.jsonl`,
   plus `settings.local.json` and `.plugin-gap-dismissed.json`. With one
   shared `.claude`, these become the same physical file for every target
   repo: one project's handoff and metrics leak into another's.
2. **`settings.json` bakes per-project values into hook wiring** — the
   `SubagentStop` command is literally `{{BUILD_TEST_CMD}}` (resolved
   once by Domain 1), and the two validation-summary agent hooks embed
   `{{CANONICAL_LANG}}`/`{{STAKEHOLDER_LANG}}`/`{{STAKEHOLDER_LANG_CODE}}`
   in their prompt text. A single shared `settings.json` cannot hold two
   projects' different build/test commands or language splits.
3. **Product content would physically collide** —
   `docs/product/specs/`, `docs/architecture/module-structure.md`/
   `frontend.md`, and the real (growing) `docs/decisions/` must be
   genuinely separate per target repo.

So the real question is not "how do we duplicate the framework per
project" but "how does a shared hook know *which* project the current
session belongs to".

## Options considered

- **Stay 1:1 — one AI-repo clone per target repo.** Zero design change,
  but every framework improvement has to be re-applied by hand to N
  near-identical clones, which drift apart the moment one is updated and
  the others aren't. That drift is the problem being solved.
- **Give each project its own `.claude/` subtree, with the shared
  `agents/commands/skills/hooks` symlinked into it.** Rejected: it puts
  a symlink *inside* a symlinked directory, so discovery depends on
  Claude Code traversing two hops on every platform, and it makes the
  AI-repo itself unusable until those internal links are recreated on
  each machine (junctions have no git representation; a committed git
  symlink checks out as a plain text file wherever `core.symlinks` is
  off). A large, fragile mechanism for something one lookup solves.
- **Have each hook infer project identity by resolving the `docs` link's
  real filesystem target.** Rejected: resolving a link's true target is
  exactly the platform-fragile operation this command already works
  around elsewhere (Windows junction vs. symlink resolution differs
  across Python and OS versions — the reason Domain 5 needs its
  symlink-then-junction fallback chain at all). It also offers nowhere to
  put `BUILD_TEST_CMD` or the language values, and doesn't help Domain 5
  itself check what is already linked.
- **One shared `.claude/`, plus a single committed registry holding both
  routing and per-project values.** Rejected: a registry keyed by each
  developer's own absolute `CLAUDE_PROJECT_DIR` grows one entry per
  person per project forever, and turns routine onboarding into a commit
  against a shared file — a merge conflict waiting to happen, for data
  that is meaningless on anyone else's machine.
- **Keep the mechanism behind a "single-project or multi-project?"
  question, so a 1:1 setup stays on today's simpler direct links.**
  Rejected: the mechanism below already degrades to exactly one linked
  project with no special case, so the branch bought nothing and cost
  two code paths to keep correct.
- **One shared `.claude/`, with per-machine routing and per-project
  config split into two files with different lifecycles (chosen).** A
  plain two-step JSON lookup, no path resolution edge cases, nothing
  machine-specific ever shared.

## Decision

Domain 5 always uses the mechanism below, unconditionally — whether one
target repo is linked or ten. There is no mode question and no second
code path: with a single project, the same structure simply holds one
entry.

**`.claude/` exists exactly once**, at the AI-repo's own root, shared
identically by every target repo — a target repo's `.claude` link points
straight at `ai-repo/.claude`, with no per-project indirection anywhere.
Per-project *content* lives in a `projects/<target-repo-name>/` subtree:

```text
ai-repo/
  .claude/
    agents/ commands/ skills/ hooks/   <- shared by every project
    settings.json                      <- shared, one file
    projects.local.json                <- routing only, gitignored, per-machine
  docs/                                <- shared generic material: workflow/, templates
  projects/
    <target-repo-name>/
      docs/
        product/specs/, architecture/*.md, decisions/   <- real, per-project
      CLAUDE.md                     <- real, per-project
      project-config.json           <- committed: this project's shared values
      session-handoff.md            <- per-project state, gitignored
      pipeline-metrics.jsonl        <- per-project state, gitignored
      settings.local.json           <- per-machine, gitignored
      .plugin-gap-dismissed.json    <- per-project, gitignored
```

The target repo keeps exactly three links: `.claude` → `ai-repo/.claude`,
`docs` → `ai-repo/projects/<name>/docs`, `CLAUDE.md` →
`ai-repo/projects/<name>/CLAUDE.md`. A new project's `docs/decisions/`
starts with only `0000-adr-template.md`.

The lookup a shared hook needs is split in two, by lifecycle:

- **`ai-repo/.claude/projects.local.json` — routing only, gitignored,
  per-machine.** Key: this machine's live `CLAUDE_PROJECT_DIR`
  (absolute). Value: this machine's absolute path to that project's
  `projects/<name>/` subtree. Nothing else. Written by Domain 5 every
  time a developer runs it on their own machine — the same lifecycle and
  discipline as the `settings.local.json` this framework already has in
  classic mode, not a new pattern. Because it is never shared, absolute
  paths in it are simply correct.
- **`ai-repo/projects/<name>/project-config.json` — committed**, inside
  the project's own subtree beside its `docs/` and `CLAUDE.md`. Holds
  exactly the stable, team-relevant values that don't vary by machine:
  `BUILD_TEST_CMD`, `CANONICAL_LANG`, `STAKEHOLDER_LANG`,
  `STAKEHOLDER_LANG_CODE`, and whatever later joins them. No absolute
  paths, no per-machine data. This file's presence and history in git is
  what lets a team see when a project was attached or reconfigured.

A hook therefore reads `<CLAUDE_PROJECT_DIR>/.claude/projects.local.json`
(reachable through the target repo's own `.claude` link), looks up its
own `CLAUDE_PROJECT_DIR` to get the subtree path, then reads
`<subtree>/project-config.json` for the values it needs at runtime —
two steps, zero filesystem-link resolution. It **fails open at either
step** (no routing entry, or a missing/malformed `project-config.json`)
with a nudge to re-run Domain 5, never blocking the session — the same
posture as `constitution_amendment_check.py` and `frontmatter_check.py`.

Domain 5 accordingly makes two different writes with two different
justifications: it always writes/updates this machine's routing entry in
`projects.local.json`, and it creates or updates the committed
`project-config.json` only when the project's shared values are actually
being set for the first time or deliberately changed.

**Project-specific skills/agents/commands**, if one is ever needed, go
into that same single shared `.claude/skills/` (etc.), scoped by their
own content and frontmatter — extending the existing `applies_to`
convention (which already tags a skill by the agent it serves) to
optionally also name a project. No new matching mechanism: Claude Code's
relevance-based triggering already means a session working on project Y
won't invoke a skill whose own description says it is for project X.

## Rationale

Because every hook resolves through `CLAUDE_PROJECT_DIR`, everything
routed through the `docs`/`CLAUDE.md` links keeps working verbatim at the
paths this framework already documents. The only thing a shared hook was
ever missing is its own project's identity — and a JSON lookup keyed by
the live `CLAUDE_PROJECT_DIR` supplies that with no filesystem semantics
involved, on any platform, which is what the link-resolution option could
not promise. Splitting routing from config then follows from the two
kinds of data having genuinely different lifecycles: one is per-machine
and worthless to anyone else, the other is a project fact worth
versioning. Keeping them in one file would force the wrong lifecycle onto
one of them. Sharing `.claude/` outright also means a framework
improvement lands for every project at once, which is the entire point of
not keeping N clones.

Applying this unconditionally rather than behind a mode question follows
from the same shape: one project is just N=1 here, so a "simple mode"
would be a second code path maintained for no behavioural gain.

Nothing here is superseded. The one existing ADR whose text names a
moving path, ADR 0011, decides *that* pipeline observability is a
git-ignored append-only event log written by hooks with no new service —
external AI-repo mode relocates that file within the AI-repo without
touching any of it.

## Consequences

- **Three existing hook wirings change shape, not just location — real
  net-new work.** `settings.example.json`'s `SubagentStop` command
  (today the literal `{{BUILD_TEST_CMD}}`) and the two validation-summary
  agent hooks (today embedding the language placeholders in prompt text)
  can no longer be resolved once into static text, because there is only
  one shared `settings.json`. Each must become, or call, a small script
  that does the two-step lookup and uses the values found at runtime.
- **`session_handoff.py` and `_pipeline_metrics.py` must stop writing
  under `<project>/.claude/`** and instead resolve their project's
  subtree via the routing lookup, writing as siblings of
  `docs/`/`CLAUDE.md` (`projects/<name>/session-handoff.md`,
  `.../pipeline-metrics.jsonl`). `session_brief.py`, which reads the
  handoff, changes with them.
- **`.gitignore` must cover the new per-machine paths.**
  `.gitignore.framework-additions` needs `.claude/projects.local.json`,
  `projects/*/session-handoff.md`, `projects/*/pipeline-metrics.jsonl`,
  `projects/*/settings.local.json` and
  `projects/*/.plugin-gap-dismissed.json`; without them, per-machine
  state and routing get committed into the AI-repo by accident — the
  exact failure the routing/config split exists to prevent.
- **Two files to keep consistent instead of one**, and a two-step lookup
  where a single read would have done. The accepted cost of not forcing
  one lifecycle onto both kinds of data; mitigated by both steps failing
  open, so a stale or missing routing entry degrades a session rather
  than breaking it.
- **A fresh clone of the AI-repo needs one Domain 5 run per machine
  before hooks can route.** All its *content* is real and immediately
  readable — no internal links to rebuild, unlike the rejected
  per-project `.claude/` option — but `projects.local.json` is
  per-machine by design, so it is regenerated by the same Domain 5 run
  that recreates the target repo's three outward links. One step, not a
  new one.
- **Every project's skills are listed together** in
  `.claude/skills/README.md`, since `skill_index.py` indexes one shared
  directory — visible where it wasn't before, though not triggered for
  the wrong project. A minor, accepted cosmetic cost.
- **ADR numbering becomes per-project.** Each target repo's decisions
  start at 0001 under its own subtree; this framework's own ADRs stay in
  the shared `docs/decisions/` and are not visible to a target repo's
  sessions. Deliberate — they're worked examples about the framework —
  but an existing 1:1 setup migrating to this layout has to decide which
  of its ADRs are project decisions and move them.
- **Shared `docs/workflow/` is genuinely shared**: an edit there
  silently affects every linked project. Anything project-specific
  belongs under `projects/<name>/docs/`.
- **Domain 5 gains two distinct config writes to get right**, and the
  target repo's own three links remain uncommitted and must still be
  recreated per machine or fresh clone — unchanged from today.
- Noted as future work, out of scope here: a separate `framework/`
  folder for this repo's own meta-ADRs and construction history, tied to
  an eventual split between a distribution repo and a development repo.

## References

`.claude/commands/setup-framework.md` (Domain 1, Domain 5),
`.claude/settings.example.json`, `.claude/hooks/_pipeline_metrics.py`,
`.claude/hooks/session_handoff.py`, `.claude/hooks/session_brief.py`,
`.claude/skills/skill-authoring/SKILL.md`, `.gitignore.framework-additions`,
`docs/decisions/0011-pipeline-metrics.md`,
`docs/decisions/0014-setup-framework-adoption-modes.md`
