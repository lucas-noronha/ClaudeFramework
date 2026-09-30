---
doc_type: adr
id: 0014
status: accepted
date: 2026-09-25
supersedes: null
superseded_by: null
context_budget: ~950 tokens
---

# ADR 0014 — Three adoption modes chosen upfront, and a user-level `~/.claude` mode with lazy per-project registration

Like ADR 0001–0013, this documents a decision about *this framework's
own* tooling.

## Context

`/setup-framework` today offers two fundamentally different adoption
shapes without ever naming the choice: Domains 1-4 copy the skeleton
into the target repo's own root, while Domain 5 links a target repo to a
separately-cloned AI-repo (ADR 0013). Which one applies is inferred
mid-run, from a question buried inside Domain 5's own steps.

A third shape is wanted, and isn't reachable at all today: the framework
machinery living in `~/.claude`, the user-level Claude Code config
directory, which is loaded automatically for every session on that
machine regardless of project. That property was confirmed by direct
research into Claude Code's own config discovery earlier in this design
conversation, and it changes what the zero-footprint goal costs: if the
machinery is already user-level, a target repo needs no links at all to
reach it.

ADR 0013 solved "which project is this session about" with a reusable
routing/config-split mechanism. Whether that mechanism is general enough
to serve a second adoption shape, rather than being Domain 5 trivia, is
the question this ADR settles.

## Options considered

- **Leave the shape implicit, add mode C as another numbered domain.**
  Rejected: the three shapes are mutually exclusive whole-repo
  decisions, not independent optional steps like Domains 2-4. Burying a
  third one in a sixth domain invites running two incompatible shapes
  against the same repo.
- **Make `~/.claude` a variant of Domain 5, differing only in where the
  AI-repo sits.** Tempting, since the mechanism is shared — but the
  linking step, the whole reason Domain 5 exists, is precisely what mode
  C removes. Folding them hides that difference.
- **Register each project in mode C by running `/setup-framework`
  against it once.** Rejected: nothing reminds a developer to do it, and
  the failure is silent — work proceeds against an unregistered project
  and lands in the wrong place, or nowhere.
- **Detect the gap with a `SessionStart` hook nudge only.** Zero token
  cost and deterministic, but a nudge can be ignored and can't collect
  the values registration needs.
- **An explicit upfront mode question, plus lazy registration performed
  by whichever pipeline command first needs a registered project
  (chosen).**

## Decision

`/setup-framework` opens with a new first question — before Domain 1 or
Domain 5's steps — naming three mutually exclusive shapes:

- **(A) Direct in-repo.** Today's Domains 1-4, unchanged: the skeleton
  is copied into the target repo's own root.
- **(B) External AI-repo.** Today's Domain 5, unchanged, per ADR 0013 —
  a separately-cloned AI-repo reached through three links at the target
  repo's root, always using 0013's `projects/<name>/` mechanism whatever
  the project count.
- **(C) User-level, multi-project.** New. The machinery (`agents/`,
  `commands/`, `skills/`, `hooks/`, `settings.json`) is copied into
  `~/.claude` directly, merged with the same never-clobber discipline
  Domain 3 already applies to `.gitignore`/`.mcp.json` — a developer's
  `~/.claude` may already hold personal skills or unrelated settings,
  and none of it may be overwritten. **No target repo gets any link at
  all** in this mode: Claude Code already reads `~/.claude` for every
  session on the machine, so zero footprint in the target repo is
  automatic, with no symlink/junction mechanism involved.

Mode C reuses ADR 0013's mechanism exactly — `projects.local.json`
routing, a committed `projects/<name>/project-config.json`, and the same
two-step hook lookup — rooted at `~/.claude` instead of a cloned repo.
In effect, `~/.claude` *is* the AI-repo for this mode.

**Where per-project content lives is the user's choice, asked once.**
Setting up mode C on a machine asks for a **projects root**: the folder
under which every registered project's `<name>/docs/`,
`<name>/CLAUDE.md` and `<name>/project-config.json` will be written.
`~/.claude/projects/` is offered as the default, but any folder is valid
— including one the developer already versions or syncs (a personal
notes repo, a synced drive folder). The chosen root is recorded once, as
a `projects_root` key in `~/.claude/projects.local.json` alongside that
file's routing entries: same lifecycle exactly (per-machine, gitignored,
absolute paths, written by setup), so it needs no new file of its own.
This question is asked once per machine at mode C setup — never per
project, never again during a lazy registration.

**Per-project registration in mode C is lazy and on-demand.** A project
is never set up by running `/setup-framework` against it. Instead, every
pipeline command that touches project-specific docs — `/spec`, `/plan`,
`/tasks`, `/implement`, `/review`, `/adr`, `/reconcile` — checks as its
own first step whether the current `CLAUDE_PROJECT_DIR` has a routing
entry in `~/.claude/projects.local.json`. If it doesn't, the command
pauses and registers the project right there: asks for the project name,
build/test command and language settings via `AskUserQuestion`, creates
`<projects_root>/<name>/` with its `docs/`, `CLAUDE.md` and
`project-config.json` under the root already chosen above, writes the
routing entry — and *then* continues with what was actually asked.

That check is written **once**, as a skill holding the registration
procedure, with each of the seven commands carrying a one-line explicit
pointer to it as its own first step. Per
`.claude/skills/skill-authoring/SKILL.md`, a concern that applies at
every pipeline stage regardless of sequence belongs in a skill — but the
same file warns that pipeline sequence must not depend on probabilistic
description matching, which is why the *trigger* stays an explicit
instruction in each command body rather than relying on the skill
self-firing. One source of truth for the procedure, a deterministic
trigger for it, and no duplicated prose in seven files.

## Rationale

Naming the shape once, upfront, matches what the choice actually is: a
one-time, whole-repo commitment that determines whether anything is
copied, linked, or neither. The three modes then differ only in where
the machinery lives, which is exactly the kind of difference a first
question settles cheaply.

Mode C is also the payoff of ADR 0013's design: because 0013 expressed
project identity as a path-keyed lookup rather than baking it into
Domain 5's linking steps, a mode with no links at all inherits the whole
mechanism unchanged. Had project identity been inferred from resolving
the `docs` link — the option 0013 rejected — mode C would have had
nothing to infer from and would have needed its own parallel design.
Letting the projects root be any folder falls out of the same property:
routing entries already store an absolute subtree path, so nothing cares
where that subtree actually sits.

Lazy registration wins over a setup-time pass because the moment a
command needs a project's docs is the only moment the need is certain,
and the developer is right there to answer. It converts a silent
misconfiguration into a question asked at exactly the right time.

## Consequences

- **In mode C, `<project>/docs` and `<project>/CLAUDE.md` do not exist
  at all** — there are no links. So every command and hook that today
  reads or writes `<CLAUDE_PROJECT_DIR>/docs/...` must route through the
  registry to `<projects_root>/<name>/docs/...`. This is a substantially
  wider surface than mode B needed (where the `docs` link made those
  paths work transparently, and only four state files plus three hook
  wirings changed). Strongly worth implementing as one small shared
  path-resolution helper that every hook imports — the same pattern
  `_pipeline_metrics.py` already establishes for shared non-hook code —
  so this becomes one helper plus a one-line change per hook, not
  bespoke logic in seventeen files.
- **Mode C's `settings.json` hook commands are a straightforward
  rewrite**: `python ~/.claude/hooks/x.py`, since the hooks no longer
  sit under any project. `~` expansion is safe here — every hook in this
  framework already runs in shell form (a `command` string, no `args`
  array), which executes through `sh`/`bash` (Git Bash on Windows), and
  the existing `${CLAUDE_PROJECT_DIR:-.}` syntax is itself bash
  parameter expansion, so bash-compatible execution is already a
  load-bearing assumption here rather than something mode C introduces.
  One narrow limitation, named rather than designed around: a developer
  who has relocated their user-level config via `CLAUDE_CONFIG_DIR`
  would have to adjust these commands by hand — that variable isn't
  documented as available inside a hook's own execution environment, so
  the command string can't detect and adapt to it. This is entirely on
  the developer's own choice to customize, not a gap this framework owns:
  Claude Code itself, not mode C, is what stops reading the default
  `~/.claude` once `CLAUDE_CONFIG_DIR` points elsewhere, so anything mode
  C set up there (or any other user-level content) becomes unreachable
  the same way it would for any other tool relying on that default —
  mode C takes no responsibility for detecting or migrating around a
  customization it has no visibility into.
- **Seven command files change, not just `setup-framework.md`** — real
  implementation surface, even though each change is one line pointing
  at the registration skill.
- **A `SessionStart` hook could cheaply complement this**: a
  deterministic check of registration status, printing a nudge at zero
  token cost. Worth adding, but explicitly *not* a substitute — the
  decided mechanism is command-level pause-and-register, because a nudge
  can neither block bad work nor collect the values registration needs.
- **Three modes are three code paths in one command.** The accepted cost
  of serving genuinely different adoption shapes; bounded by each mode
  being chosen once per repo and by B and C sharing 0013's mechanism
  rather than each inventing one.
- **Taking mode C's default projects root accepts a backup risk.**
  `~/.claude/projects/` sits outside any repo a developer would think to
  version, so a machine loss takes those specs and ADRs with it. The
  mechanism no longer forces this — pointing the root at a versioned or
  synced folder avoids it entirely — but the default should say so when
  it's offered.
- **A wrong mode choice is expensive to undo** — it means moving
  content between a repo root, a cloned AI-repo, and a user-level
  projects root. The upfront question must therefore explain the
  trade-offs, not just list three labels.

## References

`docs/decisions/0013-multi-project-ai-repo.md`,
`.claude/commands/setup-framework.md`,
`.claude/skills/skill-authoring/SKILL.md`,
`.claude/settings.example.json`, `.claude/hooks/_pipeline_metrics.py`
