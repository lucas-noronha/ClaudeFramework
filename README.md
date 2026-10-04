# Claude Framework — an AI-first delivery workflow

This is a generic, project-agnostic extraction of an AI-assisted
development workflow originally matured on a real multi-tenant SaaS
built by a single developer with Claude Code. It is not a library you
install — it's a **skeleton of `.claude/` + `docs/` files** you copy
into a new repository's root and adapt.

It gives you a deterministic pipeline (spec → plan → tasks → implement
→ review), a fixed split between subagents/commands/skills/hooks (so
sequencing never depends on probabilistic text matching), and a
context-economy discipline for docs so an agent never has to reload
the whole project to do one task.

## Why this exists

The bottleneck on a small team (often just one person) working with AI
agents isn't writing code — it's keeping context **consistent and
cheap to reload** across sessions, and keeping a pipeline's stages from
bleeding into each other. This framework encodes both as file
structure, not as instructions you have to remember to repeat.

## What's in the box

```
CLAUDE.md.template              → copy to your repo root; /setup-framework fills the placeholders and renames it to CLAUDE.md
.mcp.json.example               → Context7 (up-to-date library docs) pre-configured; merge into (or copy as) your .mcp.json — /setup-framework does this without clobbering an existing one
.gitignore.framework-additions  → per-machine state entries (not docs) to merge into your real .gitignore — /setup-framework does this too; named so copying the skeleton never overwrites your existing .gitignore
.claude/
  README.md        → component reference: what each agent/command/skill/hook does and why
  agents/          → 6 fixed subagent roles (see "The pipeline" below)
  commands/        → 12 slash commands, the pipeline's deterministic entry points (including the /quick fast lane, /update-docs and /metrics)
  skills/          → 3 meta-skills (adr-writing, skill-authoring, plugin-awareness) — the framework ships no architecture/domain skill, you add your own and tag each with applies_to: [agent-name, ...]
  hooks/           → deterministic, zero-token-cost checks and guards: 3 keep docs/decisions/README.md, docs/product/specs/README.md, and .claude/skills/README.md indexed automatically; 3 more nudge (never block) on doc context-budget drift, missing frontmatter, and a docs/constitution.md change without a version bump; 1 flips a spec's status to implemented once its tasks are all checked off; 1 blocks a write that matches a high-confidence secret pattern, repo-wide, active by default; 1 more runs your ecosystem's dependency audit when a manifest changes; 2 append a raw pipeline-observability event log (one is a shared helper, not wired directly); 1 pair (session start/end) carries a handoff note between sessions; 1 more flags at session start when the repo's language has an official LSP plugin not yet enabled
  settings.example.json → wires the hooks for mode A; /setup-framework renames it to settings.json with the build/test command filled in
  scripts/         → on-demand tools: the mode C installer/uninstaller, project registration (single or bulk), doc-base migration, the census engine, per-feature metrics
  settings.multi-project.json.example → the same wiring for modes B/C, where one settings.json is shared by several projects: hook paths behind a {{HOOKS_DIR}} placeholder /setup-framework resolves per mode, the build/test gate and the language-dependent agent hooks looking their values up per project at runtime instead of being baked in
docs/
  constitution-baseline.md → the framework's own Principles I–V, replaced on every upgrade (ADR 0018)
  constitution.md  → the organization/project layer on top of the baseline: supreme, versioned, non-negotiable principles (secrets, security baseline, one placeholder slot for a project-specific one) — checked by /spec, /plan, coder/quickfix, reviewer; amended under its own Governance section, never edited silently (ADR 0007)
  glossary.md.template
  architecture/    → overview template + 2 blank slots (module-structure, frontend) — no default architecture pattern shipped; fill in your project's actual shape or delete what doesn't apply
  decisions/       → only the ADR template (0000-adr-template.md) — a project's own ADRs start at 0001 here
  product/         → spec intake template (a spec auto-tags its own area/lineage and carries a "## Reconciliation" section — ADR 0008/0009) (no companion validation template: the split is retired, ADR 0023)
  workflow/        → living-architecture-docs.md (how architecture docs stay true to code), the conceptual flow, the practical "what do I type" guide, parallel-work guidance, the model-tiering convention, the Core-vs-Optional plugin catalog, and how the constitution/lineage/reconciliation/metrics layer fits together
evolution/         → the framework's OWN specs and ADRs (its development history) — never copied into a project; see evolution/README.md for the boundary
tests/             → the framework's own tests (not shipped into projects): every acceptance criterion of specs 0001–0003, run with `python -m unittest` from `tests/`
CHANGELOG.md       → what changed, per spec
```

## Placeholder convention

Files use `{{PLACEHOLDER}}` tokens for anything project-specific.
`/setup-framework` (Domain 1) resolves these for you, detecting what
it can from the repo and asking for the rest — this section is the
reference for what each one means, and the fallback if you're doing it
by hand: search for `{{` across the copied skeleton and fill every
match before your first real task, since an agent reading a doc with
an unfilled placeholder should treat it as a sign the doc hasn't been
set up yet, not as a real value. Common ones:

- `{{PROJECT_NAME}}` — your project's name
- `{{LANGUAGE}}` — the one setup language, asked once by
  `/setup-framework` (English by default, which costs nothing; any other
  language is translated by the model at setup and, on upgrade, only for
  changed files). Machine-parsed markers stay English (ADR 0023)
- `{{BACKEND_DIR}}` / `{{FRONTEND_DIR}}` — your repo's top-level roots,
  if it's a monorepo (drop the split entirely if it isn't)
- `{{BUILD_TEST_CMD}}` — the command your deterministic gate hook runs

## Adopting this in a new project

`/setup-framework` opens with **one question: which of three adoption
modes you want** (`evolution/decisions/0014-setup-framework-adoption-modes.md`).
They're mutually exclusive whole-repo commitments, and they differ only
in where the machinery physically lives — so the command explains each
one's real trade-offs before you pick, because **a wrong choice is
expensive to undo** (it means moving `docs/product/specs/`,
`docs/decisions/` and `CLAUDE.md` between a repo root, a cloned
AI-repo, and a user-level projects root, then relinking or unlinking
every repo pointing at the old layout).

| Mode | Where the machinery lives | The code repo gets | Best when |
|---|---|---|---|
| **A — Direct in-repo** | the code repo's own root | everything, committed | nothing forbids Claude files in the repo, one project |
| **B — External AI-repo** | a separate AI-repo | three never-committed links | the code repo must stay Claude-free, and you want the framework versioned and shared with a team |
| **C — User-level** | `~/.claude` on your machine | nothing at all | you want one setup covering every repo you touch, per developer |

Modes B and C both back **several projects from one copy** of the
machinery, using the same mechanism (`evolution/decisions/0013-multi-project-ai-repo.md`):
a per-machine, gitignored `projects.local.json` routes this session's
`CLAUDE_PROJECT_DIR` to that project's own subtree, and a
`project-config.json` in that subtree holds its build/test command and
language settings. A single shared `settings.json` then serves every
project, since nothing project-specific is baked into it. One project
is just N=1 in that structure — there's no simpler single-project path
to choose, and no migration when a second project arrives.

### Mode A — direct in-repo

1. Copy `.claude/`, `docs/`, `CLAUDE.md.template`,
   `.mcp.json.example`, and `.gitignore.framework-additions` into the
   new repo's root — as-is, no renaming yet.
2. Run `/setup-framework` inside that repo and pick mode A. It:
   - **Domain 1** — detects what it can from your repo (project name,
     default branch, backend/frontend split, build/test command, …),
     asks you to confirm or fill in the rest, resolves every
     `{{PLACEHOLDER}}` consistently across every file, and renames
     `CLAUDE.md.template` → `CLAUDE.md`,
     `.claude/settings.example.json` → `settings.json`,
     `auto_format.py.example` → `auto_format.py`, and
     `overview.md.template`/`glossary.md.template` into their real
     names.
   - **Domain 2** — checks which of this framework's recommended Core
     plugins are already enabled on your machine and installs any
     you're missing (see `docs/workflow/plugin-integrations.md`) —
     optional, the pipeline works without them, just with less
     complementary rigor across `/spec`, `/plan`, `coder`/`quickfix`,
     `/implement`, `/review`, and `/worktree` (`superpowers` specifically backs a
     complementary pass at nearly every one of those stages, not just
     implementation — see
     `evolution/decisions/0003-superpowers-sdd-wrapping.md`).
   - **Domain 3** — merges `.mcp.json.example` and
     `.gitignore.framework-additions` into your project's real
     `.mcp.json`/`.gitignore` (creating either fresh if you don't have
     one yet, only adding what's missing if you do — never overwrites
     an existing entry), then deletes the now-redundant source files.
   - **Domain 4** — optional: if you're onboarding an *existing*
     codebase, asks whether to draft
     `docs/architecture/module-structure.md`/`frontend.md` from
     patterns it detects there (layout, naming conventions, observed
     import direction between layers, cited against sample files) — see
     `evolution/decisions/0006-architecture-anamnesis.md`. Always a **draft**
     clearly marked as such, never presented as finished; skipped
     entirely on a green field with nothing yet to detect.
3. Read (and correct) the two architecture-doc slots
   (`docs/architecture/module-structure.md`,
   `docs/architecture/frontend.md`) with *your* actual structure and
   dependency rules, or delete whichever doesn't apply. If Domain 4 ran,
   it already drafted a starting point from your existing code — read
   it fully and fix anything wrong, don't take it on faith. If it
   didn't (declined, or nothing to detect), write these by hand; this
   is the one step `/setup-framework` can offer help with but never
   finish on its own — this framework takes no position on monolith
   vs. microservices, layered vs. flat, feature folders vs. anything
   else, and a *human-confirmed* description is what `coder` and
   `reviewer` end up trusting either way.
4. Read `docs/workflow/ai-first-development.md` (the concept) and
   `docs/workflow/feature-development-guide.md` (the "what do I type"
   recipe) once — after that you shouldn't need to re-derive the flow.
5. Start with `/spec <idea>`.

### Mode B — external AI-repo (zero footprint in the code repo)

Some environments forbid committing anything Claude-related inside the
actual code repo at all. For that case skip mode A's step 1 entirely —
keep this repo (or a company fork of it) as its own separate
**AI-repo** — and run `/setup-framework` from inside it, picking mode
B. Its **Domain 5** then, once per target repo:

- **Links** the target code repo to this one via local,
  never-committed relative symlinks/junctions/hard links at
  `<target repo>/.claude` → the one shared `.claude/`,
  `<target repo>/docs` → the AI-repo's own shared `docs/` root, and
  `<target repo>/CLAUDE.md` → `docs/<name>/CLAUDE.md`. The `docs` link
  reaches shared material (`constitution.md`, `workflow/`, `glossary.md`)
  transparently; a project's own content is reached through the
  registry instead, per ADR 0015 — see the `project-registration`
  skill.
- **Creates that project's own `docs/<name>/` subtree** in the
  AI-repo, holding its real `product/specs/`, its ADRs starting fresh
  at `0000-adr-template.md`, its `CLAUDE.md`, and optionally its own
  `constitution.md` (additive only, never overriding the shared one) —
  so several target repos share one `.claude/` and one `docs/` root
  without their product content ever colliding.
- **Writes the two config files** ADR 0013 splits by lifecycle: a
  gitignored, per-machine `.claude/projects.local.json` routing this
  machine's path for the target repo to that subtree, and a committed
  `docs/<name>/project-config.json` holding the build/test command
  and language settings (never overwritten without asking).
- **Adds a bootstrap note at the *lowest common ancestor*** of the two
  repos — auto-loaded by Claude Code's own directory-tree walk, no
  link required for this part — telling any session started in the
  target repo to stop and demand this setup if the links are missing.

The target repo doesn't need to be a sibling directory: it can sit at
any depth, e.g. one package deep inside someone else's monorepo, as
long as the two repos share *some* common ancestor on the same
filesystem. It ends up with zero Claude-related files ever staged in
its own git history. The links and the routing file are per machine, so
re-run Domain 5 after any fresh clone or on a new machine — see Domain
5 in `.claude/commands/setup-framework.md` for the exact steps.

### Mode C — user-level, multi-project (no links anywhere)

Claude Code already loads `~/.claude` for every session on a machine,
so if the machinery lives there, a code repo needs no copied file *and*
no link to reach it. Pick mode C and **Domain 6** runs the installer
from this repository (`evolution/decisions/0017-user-level-install-mechanics.md`):

```
python .claude/scripts/install_user_level.py                # dry run
python .claude/scripts/install_user_level.py --apply        # install or upgrade
```

- Agents, commands and skills get a **namespace prefix** (default `cfw`):
  `/cfw-spec`, `/cfw-quick`, `cfw-coder`, so they never collide with your
  own `spec`/`plan` commands. Everything else lives in `~/.claude/cfw/`:
  hooks, scripts, the registry, `framework.json`, and the shared `docs/`
  root with the framework's reference ADRs.
- Hooks do **nothing** in a repo that isn't registered, so unrelated
  repos get zero footprint.
- It asks once for a **projects root** (default `~/.claude/cfw/docs/`,
  outside version control — any versioned or synced folder works too).
- It never overwrites a file it doesn't own, refuses to overwrite one
  you edited by hand (fix it here, then re-install), and records
  everything in a manifest: `python ~/.claude/cfw/scripts/uninstall.py`
  removes exactly that and restores `settings.json` byte for byte.

Projects register lazily: the first `/cfw-spec`, `/cfw-plan`,
`/cfw-quick`, ... in an unregistered repo asks for its name, build/test
command and languages, then continues. Several existing repos can be
registered in one pass, and an existing doc base can be imported with
`migrate_context.py` (links rewritten and verified, source untouched).

Two things to know before choosing it: it's per developer, so a
teammate gets none of it (mode B is the shareable one), and if you've
relocated your user-level config with `CLAUDE_CONFIG_DIR`, pass that
directory with `--config-dir`.

## The pipeline

| Stage | Command | Subagent(s) | Model tier |
|---|---|---|---|
| Fast lane (small changes) | `/quick` | `triage` → `quickfix` (trivial) or lite spec → `/implement` (standard) | haiku → haiku/sonnet |
| Intake | `/spec` | — | — |
| Technical plan | `/plan` | `triage` → `architect` (structural only) | haiku → opus |
| Breakdown | `/tasks` | — (mechanical, no subagent) | — |
| Build | `/implement` | `triage` → `quickfix`/`coder`, dependency-ordered waves, one subagent per task | haiku → haiku/sonnet |
| Quality gate | *(automatic, per task)* | — (hook) | zero token cost |
| Per-task review | *(automatic, inside `/implement`)* | `reviewer` — coder-tier tasks only | sonnet |
| Final review | `/review` | `reviewer` (whole-feature diff) | sonnet |
| Isolation | `/worktree` (also offered automatically by `/implement`) | — | — |
| Post-hoc fidelity sweep | `/reconcile` (any time, against an `implemented` spec) | `reviewer` (sweep scope) | sonnet |
| Ad hoc decision | `/adr` | `architect` | opus |
| Architecture docs vs. code | `/update-docs` (census projects) | `reviewer` (doc verification, on `promote`) | sonnet |
| Pipeline cost per feature | `/metrics` | — | — |
| Framework setup | `/setup-framework` | — | — |

Full rationale for this exact split → `evolution/decisions/0001-tooling-agents-commands-skills.md`.
Why `/plan`/`/tasks`/`/implement` are divided this way (technical
planning in `/plan`, mechanical sequencing in `/tasks`, dependency-aware
orchestration + per-task review in `/implement`) →
`evolution/decisions/0004-plan-tasks-implement-rebalance.md`.
Why a spec's `/implement` sweep gets its own worktree (and a task never
does) → `evolution/decisions/0005-spec-worktree-lifecycle.md`.
Why each role gets the model tier it gets → `docs/workflow/model-tiering.md`.

## What's genuinely generic vs. what's yours to define

- **Fully generic, don't need editing beyond placeholders:** all 6
  agents, all 12 commands, the `adr-writing`, `skill-authoring`, and
  `plugin-awareness` skills, all 23 hook files (only
  `auto_format.py.example` and `dependency_audit.py.example` need a
  real command swapped in — the latter's `MANIFEST_COMMANDS` also needs
  trimming to your actual ecosystem(s), see ADR 0010), the workflow
  docs. `plugin-awareness`'s *worked-example* plugin list in
  `docs/workflow/plugin-integrations.md` is the one exception — see
  below.
- **A real default, deliberately — the one exception to "no defaults
  shipped":** `docs/constitution.md`'s Core Principles (secrets,
  logging, input validation, least privilege, dependency vetting) ship
  with actual content, not a blank slot. See
  `evolution/decisions/0007-constitution-document.md` for why this doesn't
  contradict the architecture blank-slots decision below — secrets/
  security hygiene is close to universal across projects, unlike
  module layout or tenancy strategy. Principle VI is left an explicit
  placeholder for whatever project-specific invariant you need.
- **Blank slots by default, optionally draftable:**
  `docs/architecture/module-structure.md`,
  `docs/architecture/frontend.md`. This framework takes no position on
  monolith vs. microservices, layered vs. flat, feature folders vs.
  anything else — that's a property of your project, not something a
  reusable template should decide for you. Fill them in with your real
  structure and dependency rules, or delete what doesn't apply.
  `/setup-framework`'s Domain 4 can draft a starting point from an
  *existing* codebase's own detected patterns (see
  `evolution/decisions/0006-architecture-anamnesis.md`), but only ever as a
  draft you still have to read and correct — it never finishes these
  files on its own.
- **A worked example you're expected to edit:**
  `docs/workflow/plugin-integrations.md`'s Core/Optional table. Claude
  Code plugins are installed per machine, not per repo, so the exact
  list here only ever reflects whatever's installed on whichever
  machine last edited it — the mechanism around it (`/setup-framework`,
  `plugin-awareness`, `plugin_gap_check.py`) is generic, the table
  contents are not. See `evolution/decisions/0002-plugin-integration.md`.
- **Not shipped at all, by design:** any skill encoding a specific
  architecture or domain rule (a tenant-isolation checklist, a module-
  scaffolding pattern, a sensitive-data-handling rule, etc.). The
  `.claude/skills/` folder ships with only the meta-skills the
  framework's own process needs. The first time your project needs one
  of these, write it following `skill-authoring/SKILL.md`'s format,
  tied to whatever your project's own architecture docs establish —
  don't reach for a generic example, because there isn't one; the
  right shape depends entirely on your project's real invariants.

This is deliberate: the goal is a framework that works the same way
regardless of architecture or stack, not one that nudges every new
project toward the specific shape (a layered modular monolith, a
multi-tenant RLS-isolated database, a feature-folder React frontend)
that the source project happened to use. Business/architecture
decisions like tenancy strategy, monolith vs. microservices, and
module scaffolding belong entirely to each project — the framework
only supplies the process around them (how a decision gets recorded,
how a checklist-shaped Skill gets written), never the decision itself.

## Since the first real adoption (specs 0001–0003)

Mode C hardening, living architecture docs and a proportional pipeline
landed together — see `CHANGELOG.md` for the unified list and ADRs
0017–0020 for the decisions.

## What's new here vs. the project this was extracted from

A few things were added or changed while generalizing, worth knowing
about since they weren't validated on a real project yet the way
everything else was:

- **`/plan`/`/tasks`/`/implement` rebalanced to match Spec Kit's own
  split** — checked against GitHub's Spec Kit (already cited in ADR
  0001's rationale) and Anthropic's own Claude Code best practices,
  this framework's `/plan` had drifted into doing almost nothing
  (classify + conditional ADR) while `/tasks` quietly absorbed the real
  technical-planning judgment. `evolution/decisions/0004-plan-tasks-implement-rebalance.md`
  moves that judgment back to `/plan` (a real, tier-proportional
  technical plan for standard/structural specs, an explicit scope-creep
  check, nothing for trivial), makes `/tasks` purely mechanical again,
  and turns `/implement` into an optional orchestrator: given a spec
  instead of one task, it computes dependency-ready waves from
  `/tasks`'s own annotations, dispatches each wave's tasks to their own
  isolated subagent in parallel, and auto-runs `reviewer` on every
  coder-tier task (never quickfix-tier, per
  `docs/workflow/model-tiering.md`) before checking it off — always
  scoped to that task's own files, since orchestration mode's parallel,
  uncommitted waves mean a bare `git diff` would span every task in
  flight, not just the one being reviewed. `/plan` also now writes a
  **Definition of Done** and a **Test plan** (one line per expected
  unit test, plain-language, each tagged to the spec's own `FR-NN`/
  `AC-NN`), which `/tasks` distributes across tasks and `coder`/
  `reviewer` check against instead of inventing coverage ad hoc — the
  whole feature reduces to a short, scannable list of phrases before
  any code exists. The standalone `/review` stays for a final,
  whole-feature pass (including the Definition of Done check, which
  the per-task pass deliberately skips) — it's complementary, not
  replaced.
- **A spec's `/implement` sweep gets its own worktree, so several specs
  can run at once** — `evolution/decisions/0005-spec-worktree-lifecycle.md`.
  Orchestration mode now checks for a worktree named
  `task/<spec-short-name>` before starting and offers to create one
  (via `/worktree`'s own steps) if it's missing, then hands off to a
  new session there — the same session can't just `cd` into it and
  keep going, since this framework's hooks (the build/test gate, spec
  tracking) are wired to whichever directory the current session
  actually started in. Isolation stops at the spec on purpose: a single
  task never gets a worktree of its own, no matter how large — every
  task in a sweep keeps sharing subagent-level isolation (ADR 0004)
  instead of paying a session hand-off per task. On an Approved
  `/review`, if the spec is in its own worktree, it now offers to push
  the branch and open a PR.
- **`superpowers` wrapped across the whole SDD lifecycle, not just
  `coder`** — ADR 0002 originally scoped `superpowers`'s complementary
  invocation to `coder`'s TDD/debugging pass only. `evolution/decisions/0003-superpowers-sdd-wrapping.md`
  extends the same absorbed+complementary mechanism to `/spec`
  (`brainstorming`), `/plan` (`writing-plans`, standard/structural
  only), `/implement`'s orchestration mode
  (`dispatching-parallel-agents`/`subagent-driven-development`/
  `executing-plans`), `coder`/`quickfix` (adds `receiving-code-review`,
  `verification-before-completion`), `/review`
  (`requesting-code-review`, `finishing-a-development-branch`), and
  `/worktree` (`using-git-worktrees`, alongside its own authoritative
  origin-pinned steps). Still fully optional and user-gated via
  `/setup-framework` — every stage's own written-out steps are
  unaffected if you decline installing it.
- **`/adr` command** — the original only created ADRs as a side effect
  of `architect` inside `/plan`, for structural tasks. Sometimes you
  just want to record a decision that isn't attached to a task at all
  (e.g. "we're switching CI providers") — `/adr` does that directly.
- **`skill-authoring` skill** — a meta-skill capturing the test from
  ADR 0001 ("does this apply at any stage, regardless of sequence?")
  as an explicit checklist, so a future you (or an agent) can decide
  skill vs. command vs. agent-body content consistently across
  projects, not just remember it once.
- **`docs/workflow/model-tiering.md`** — the haiku/sonnet/opus split
  was real and deliberate in the original but only lived implicitly in
  each agent's frontmatter. Documenting it as its own doc makes the
  convention portable and gives you one place to reconsider it as
  model lineups change.
- **`docs/workflow/parallel-work.md`** — consolidates the original's
  worktree usage guidance and adds a lightweight answer to "what's
  currently in flight across worktrees" (`git worktree list` +
  branch-name convention) instead of a new file to maintain and let go
  stale. Deliberately not a new stateful tracking file — that would
  duplicate what git already knows.
- **One setup language** — the original hardcoded Portuguese as the
  stakeholder-facing language, later split into canonical and
  stakeholder languages. That split is retired (spec 0005, ADR 0023):
  `/setup-framework` asks for one language, once. English copies as-is;
  another language is translated by the model at setup and on upgrade
  for changed files only. Frontmatter keys and enumerated values,
  `## Tasks`/`## Reconciliation` and `Approved`/`Returned` stay English,
  so hooks work in any language. No language is baked into the hooks.
- **`docs/decisions/README.md` and `docs/product/specs/README.md`, kept
  in sync automatically** — as ADRs and specs accumulate, finding the
  right one to open stopped being cheap. Two new hooks
  (`decision_index.py`, `spec_index.py`) rebuild a one-line-per-entry
  index (id, title, status) every time an ADR or spec is written or
  edited — deterministic, zero token cost, never goes stale because
  nothing hand-maintains it. `CLAUDE.md`'s index table points at both.
- **`.claude/README.md`** — a component reference (what each
  agent/command/skill/hook does, one line each) separate from the root
  `README.md`'s adoption instructions. Read it when you want to
  understand or modify the machinery itself, not just use it.
- **`spec_number_guard.py` scope fix** — the original matched any
  `NNNN-*.md` file written anywhere in the repo against existing specs,
  not just files actually written inside `docs/product/specs/`. Fixed
  to only fire for writes into that directory; while fixing it, every
  directory-scoped hook was also switched to compare normalized
  (forward-slash) paths instead of raw string equality, since Windows
  freely mixes `\` and `/` and a naive comparison silently never
  matches.
- **No default architecture pattern or domain skill, on reflection** —
  an earlier pass of this generalization shipped
  `docs/architecture/module-structure.md`/`frontend.md` pre-filled with
  the source project's actual pattern (layered modules + a
  facade-based frontend), plus four "worked example" skills
  (`tenant-isolation-checklist` generalized into
  `structural-invariant-checklist`, `sensitive-hr-data` into
  `sensitive-data-handling`, plus `module-scaffolding` and
  `frontend-feature-scaffolding`). On review, that still baked one
  project's architecture opinions into a template meant to work for
  any architecture/stack — those two docs are now blank slots and the
  four skills were removed outright rather than left as "examples to
  replace." What's left in `.claude/skills/` is only the two the
  framework's own process needs (`adr-writing`, `skill-authoring`);
  every agent that referenced the removed skills/docs by name now
  refers to "whatever your project's architecture docs/skills define"
  generically instead. `evolution/decisions/0006-architecture-anamnesis.md`
  later revisited this, carefully: `/setup-framework` may now draft
  these two files from patterns it detects in an *existing* codebase
  being onboarded — the unsafe part of the original mistake was
  shipping one fixed opinion as this framework's own default, trusted
  without review; a project-specific draft that stays explicitly
  unread-and-unfinished until a human checks it doesn't repeat that.
- **`applies_to` skill tagging + `.claude/skills/README.md`** —
  removing the example skills raised a real question: once a project
  adds its own, how does e.g. `coder` reliably know to check one,
  instead of hoping automatic description-matching catches it? The
  fix isn't a hand-maintained list inside each agent (that duplicates
  the same "N places to keep in sync" problem this framework avoids
  everywhere else) — it's a `applies_to: [agent-name, ...]` frontmatter
  field on the skill itself, plus a new hook (`skill_index.py`) that
  rebuilds `.claude/skills/README.md` from those tags automatically.
  Adding a skill to a project is then a one-file edit: tag it once, at
  the source; every pipeline agent's body says to check that index for
  its own name before starting a task. (While building this, the index
  hooks were also hardened to only parse the YAML frontmatter block,
  not the whole file — `skill_index.py` initially picked up a false
  match from `skill-authoring/SKILL.md`'s own template *example*
  sitting in its body.)
- **`.mcp.json.example`** — `CLAUDE.md.template` already told you to
  "add an MCP entry for Context7" but nothing shipped the actual file.
  Now it does, mirroring the exact config the source project runs
  (`npx @upstash/context7-mcp`, a local stdio server — not guessed).
- **Context-budget drift and missing-frontmatter nudges** — two new
  hooks (`context_budget_check.py`, `frontmatter_check.py`) turn two
  of this framework's own prose principles ("don't let a doc bloat,
  split it"; "every doc carries `doc_type`/`status`/`context_budget`")
  into mechanical, non-blocking nudges instead of things only caught on
  a human's careful read. Both are warnings, never gates — a doc that's
  deliberately larger than its stated budget just needs that number
  updated, not a hook fighting the author. (Dogfooding this while
  building it caught a real one: this framework's own
  `validation-summary-template.md` had drifted to ~2.6x its stated
  budget after an earlier edit — fixed on the spot.)
- **`claude_md_index_check.py`** — a third nudge in the same family,
  added after the same drift it now catches actually happened while
  extending this framework: `CLAUDE.md`'s own "Index" table quotes each
  doc's `~Cost`, duplicating a number that also lives in that doc's own
  `context_budget` frontmatter — several docs' budgets changed and
  `CLAUDE.md`'s copy silently went stale. Unlike `decision_index.py`/
  `spec_index.py`/`skill_index.py`, which fully own an auto-generated
  file safe to rewrite outright, `CLAUDE.md` is hand-authored prose with
  this table embedded in it — so this hook only ever nudges, it never
  rewrites a line inside a file a human is meant to be editing.
- **`spec_status_sync.py` + a checkbox convention for tasks** — nothing
  previously flipped a spec's `status` to `implemented`; it relied on
  remembering to edit it by hand, same problem ADR bookkeeping had
  before `adr_backlink.py`. Fixed the same way: `/tasks` now writes
  `## Tasks` as checkboxes, `/implement` checks one off per finished
  task, and a hook flips `status` once they're all checked — never from
  `draft`, so it can't skip the stakeholder-validation checkpoint.
- **`session_handoff.py` + a `SessionEnd` hook** — the original had no
  counterpart to `session_brief.py` at the *end* of a session. Verified
  first (rather than guessing) that Claude Code's `SessionEnd` event
  fires once per session close, not once per turn like `Stop`, and
  that it hands the hook `last_assistant_message` directly — so the
  hook needs no transcript parsing and no LLM call: it just snapshots
  that message to `.claude/session-handoff.md` (overwritten each time),
  and `session_brief.py` surfaces it at the next `SessionStart`. This
  leans on a real existing convention (a turn already ends with a short
  "what changed, what's next" per how these agents are instructed to
  communicate) rather than inventing a new one.
- **`docs/constitution.md`** — raised directly by comparing this
  framework against GitHub Spec Kit/OpenSpec/BMAD for large-scale
  maturity: none of the pipeline's docs previously carried
  non-negotiable, cross-cutting principles distinct from `CLAUDE.md`'s
  project glue or an ADR's point-in-time decision.
  `evolution/decisions/0007-constitution-document.md` adds a versioned,
  supreme document (secrets, logging, input validation, least
  privilege, dependency vetting, prefilled — the one deliberate
  exception to shipping no defaults) that `/spec`, `/plan`,
  `coder`/`quickfix`, and `reviewer` all check against, amended only
  through its own Governance procedure. Checked, not hard-enforced —
  `constitution_amendment_check.py` nudges (git-`HEAD`-diffed, fails
  open without git) when the content changes without a version bump,
  the same posture as `context_budget_check.py`/`frontmatter_check.py`
  rather than `adr_immutability_guard.py`'s hard block, since
  amendments are expected over time, not frozen like an accepted ADR.
- **Specs auto-tag their own `area` and lineage** —
  `evolution/decisions/0008-spec-area-lineage.md`, also from the same
  maturity comparison (OpenSpec's brownfield delta model was the
  reference point, deliberately not adopted wholesale — see the ADR's
  Options). `/spec` now reads `docs/product/specs/README.md` before
  drafting and infers `area` + `relates_to` itself, mirroring the ADR
  `supersedes`/`superseded_by` convention instead of a new primitive —
  never a human-declared tag, on direct instruction.
  `spec_index.py`'s table now sorts/groups by area. Building this
  surfaced a real latent bug: `spec_status_sync.py`, `spec_index.py`,
  and the stakeholder-validation-sync example hook all already assumed
  every spec had a YAML frontmatter `status:` field, but
  `requirements-template.md` never actually produced one — no spec's
  status could have auto-flipped to `implemented` before this fix.
- **`reviewer` reconciles spec vs. diff, per task** —
  `evolution/decisions/0009-per-task-spec-reconciliation.md`, closing the
  same maturity gap GitHub Spec Kit's `/speckit.reconcile` and
  OpenSpec's `/opsx:sync` cover, scoped to this framework's own
  `/implement` pass on direct instruction rather than a new standalone
  command: `reviewer` already reads a coder-tier task's diff, so it now
  also appends one line per `FR-NN`/`AC-NN` the task declared to the
  spec's own "## Reconciliation" section (matches spec, or diverged and
  why) — append-only, informational, never replacing the Approved/
  Returned verdict. `reviewer` gained `Edit` access for exactly this
  write. `/review`'s whole-feature pass now also checks that every
  requirement the spec claims has at least one such entry before
  approving. Known gap, left open: this only catches drift during a
  spec's own implementation sweep, not later staleness after a spec is
  already `implemented` — noted as a candidate for a future ADR, not
  solved here.
- **`docs/constitution.md` gets technical teeth** —
  `evolution/decisions/0010-constitution-technical-enforcement.md`. ADR
  0007 made the constitution supreme but only checked by an agent's own
  judgment; this closes that with three additions, none of them gated
  on the file existing: `secret_leak_guard.py` (new, active by
  default, stdlib-only regex) hard-blocks a write matching a
  high-confidence credential pattern; `dependency_audit.py.example`
  (new, needs a real command like `auto_format.py.example` already
  does) runs an ecosystem audit whenever a dependency manifest changes;
  and `reviewer`/`coder` both now invoke the `security-review` skill
  for a security-sensitive diff, mapping a finding to a named Core
  Principle when the constitution file exists. Deliberately scoped down
  from a real secrets scanner (gitleaks/trufflehog) to a small
  high-confidence pattern set — the generic "secret = long string"
  shape was rejected outright, since it would trip on this framework's
  own `{{PLACEHOLDER}}`/`.example` conventions constantly.
- **A raw pipeline-observability event log** —
  `evolution/decisions/0011-pipeline-metrics.md`. `.claude/pipeline-metrics.jsonl`
  (git-ignored, per-machine), one JSON line per event:
  `spec_created`/`spec_implemented` (lets `draft`→`implemented` elapsed
  time be computed later), `reconciliation_snapshot` (current
  matches/diverged/out-of-scope counts from a spec's own
  "## Reconciliation" section), and `reviewer_verdict`
  (Approved/Returned). No dashboard, no new service — just a stream a
  human or an agent can summarize with `jq` when someone actually wants
  to look, instead of the pipeline's health living only anecdotally.
  `reviewer_verdict` carries a real, explicitly documented reliability
  gap: it depends on reading a subagent-dispatch tool's `PostToolUse`
  payload, matched on both `Task` and `Agent` since which name a given
  Claude Code version actually uses isn't something this framework can
  verify generically — worth checking empirically after adopting it.
- **`/reconcile`** —
  `evolution/decisions/0012-on-demand-reconciliation-sweep.md`, closing the
  gap ADR 0009 named explicitly: the per-task reconciliation pass only
  catches drift during a spec's own `/implement` sweep, nothing
  revisited a spec once `implemented` if later work touched the same
  code. Runnable any time against an `implemented` spec; delegates to a
  new third scope on `reviewer` ("sweep scope" — no file list, no diff,
  no build/test gate prerequisite) that judges *current* code state
  against the spec's `FR-NN`/`AC-NN` and appends a dated `### Sweep`
  block to "## Reconciliation," never editing an earlier sweep. Chose a
  fresh compliance check over a git-diff-based approach on purpose:
  this framework doesn't persist a file manifest per task (only
  `coder`'s transient end-of-turn report has one), so a diff long after
  the fact would have to guess at file history via commit-message
  conventions this framework doesn't enforce — an honest "couldn't
  verify" beats a diff that silently misses files.

## Design principles worth keeping when you adapt this

1. **One subject per file.** Split the moment a doc explains two
   unrelated things.
2. **Reference, never copy.** A relative path to another doc beats
   duplicating its content — duplication is what goes stale.
3. **ADRs are immutable once accepted.** A changed decision is a new
   ADR that supersedes the old one, never a silent edit. Enforced here
   by a hook (`adr_immutability_guard.py`), not just a convention.
4. **Frontmatter on every doc** (`status`, `context_budget`, etc.) —
   lets an agent filter what's worth loading before opening the file.
5. **Sequencing lives in commands, not in skills.** Skills trigger on
   text similarity, which is fine for "does this rule apply right now"
   but wrong for "what stage of the pipeline are we in" — see ADR 0001.
6. **Don't ask an agent to hold what a deterministic check can hold
   for free.** Build/test/format/guard-rails are hooks, not something
   re-verified by an LLM call on every turn.
