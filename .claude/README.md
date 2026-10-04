# `.claude/` — how this machinery works

This is the component reference: what each file in here does and why
it exists. For "how do I adopt this in a new project," see the
repository root's `README.md` instead — this one assumes you've
already read that and want to understand (or modify) the pipeline
itself.

The short version, from framework ADR 0001:
**subagents** are pipeline roles, **commands** are the pipeline's
deterministic entry points, **skills** are knowledge that applies at
any stage, **hooks** are deterministic checks that cost zero tokens.
Four different primitives because conflating them (e.g. using a Skill
for sequencing) makes the pipeline depend on probabilistic text
matching for something that should be exact.

One more file sits above all four: the constitution — since framework ADR 0018
two files at the docs root, `../docs/constitution-baseline.md`
(framework-owned Principles I–V, replaced on every upgrade) and
`../docs/constitution.md` (ADR
0007) — non-negotiable, versioned principles `/spec`, `/plan`,
`coder`/`quickfix`, and `reviewer` all check against, amended under its
own Governance section rather than edited silently. In the
multi-project modes it becomes two layers (framework ADR 0015): the shared root's
`docs/constitution.md` is the supreme **floor** binding every project,
and a project's own `docs/<name>/constitution.md` may only **add** to
it — never weaken or contradict it. That file is optional and
project-owned: it is not pre-created, and its absence is normal. Mode A
is unchanged, one file, no layering.

## agents/ — the pipeline roles

Each file is one subagent: a name, a fixed `model` tier (see
`../docs/workflow/model-tiering.md` for why each gets the tier it
gets), a fixed tool list, and its own isolated context — it never sees
the calling session's conversation, only what's explicitly handed to
it.

| File | Role | Called by |
|---|---|---|
| `triage.md` | Classifies a task's (or a free-text request's) size (trivial/standard/structural) in one sentence, implements nothing | `/plan`, `/implement`, `/quick` (framework ADR 0020) |
| `architect.md` | Assesses structural impact, drafts an ADR if one is needed, never writes implementation code | `/plan` (structural tier), `/adr` |
| `researcher.md` | Answers one pointed external/domain question, returns a conclusion not raw research | `architect`, `coder`, on demand |
| `coder.md` | Implements standard/structural tasks with tests, following the architecture docs and skills relevant to what it's touching | `/implement` (standard/structural tier, single-task or orchestration mode) |
| `quickfix.md` | `coder`'s cheaper sibling for genuinely trivial, single-file fixes | `/implement` (trivial tier) |
| `reviewer.md` | One review pass against an explicit checklist (including the spec's Test plan coverage; the Definition of Done and "## Reconciliation" completeness too, when the scope is the whole feature), after the build/test hook is already green. Per-task scope also appends reconciliation entries to the spec's own "## Reconciliation" section for that task's `FR-NN`/`AC-NN` tags (framework ADR 0009) — the only agent with `Edit` access beyond `coder`/`quickfix`. Invokes the `security-review` skill for a security-sensitive diff, folding a finding into a named Core Principle when `docs/constitution.md` exists (framework ADR 0010). A third **sweep scope**, called only from `/reconcile`, audits an already-`implemented` spec against current code state — no diff, no gate, appends a dated sweep block instead of an Approved/Returned verdict (framework ADR 0012). A fourth **doc-verification scope**, called only from `/update-docs promote`, independently checks a `draft` architecture doc's rules against code (framework ADR 0019). Treats `draft` architecture rules as advisory, `active` ones as binding, and flags "rule may be stale" separately | `/review` (whole-feature diff); also fired automatically inside `/implement`'s orchestration mode, scoped to one task's own files (see framework ADR 0004); `/reconcile` (sweep scope) |

## commands/ — the pipeline's deterministic entry points

Each file is a slash command: fixed steps, explicit delegation to the
right subagent(s). The sequence never depends on an agent "deciding"
which stage it's in.

| File | Command | What it does |
|---|---|---|
| `spec.md` | `/spec` | Formalizes an idea into a spec file (+ stakeholder-language companion, if configured) from the requirements template. Wraps `superpowers:brainstorming` first, when enabled (see framework ADR 0003), and always checks the described solution actually follows from the underlying business problem before formalizing it — flagging a mismatch as an "unclear, ask" item instead of silently proceeding. Also auto-assigns the spec's own `area`/`relates_to` lineage from the existing spec index (framework ADR 0008, never asked of the human) and checks the request against `docs/constitution.md`, if present |
| `plan.md` | `/plan` | Triages complexity; trivial stops there, standard writes a short technical plan + Definition of Done + Test plan (numbered against the spec's `FR-NN`/`AC-NN`), structural adds `architect` (+ ADR) plus the same three artifacts and an explicit scope-creep check (see framework ADR 0004). Wraps `superpowers:writing-plans` for standard/structural, when enabled |
| `tasks.md` | `/tasks` | Mechanically breaks the technical plan into small, dependency-annotated (`Depends on:` per task) `/implement`-sized tasks, distributing the Test plan's entries one-to-one across them (`Tests:` per task) — no technical judgment happens here (framework ADR 0004) |
| `implement.md` | `/implement` | Single-task mode: routes one task to `quickfix`/`coder`. Orchestration mode (spec path instead of a task): first checks/offers a spec-scoped worktree (framework ADR 0005), then dispatches dependency-ready waves in parallel, one isolated subagent per task (never a worktree per task — isolation stops at the spec), auto-`reviewer` per coder-tier task before checking it off (framework ADR 0004). Wraps `superpowers:dispatching-parallel-agents`/`subagent-driven-development`/`executing-plans` in orchestration mode, when enabled |
| `review.md` | `/review` | Final, whole-feature pass: runs `reviewer` against the cumulative diff plus the spec's Definition of Done, once the build/test hook is green — complements `/implement`'s per-task pass, doesn't replace it. On Approved, offers to push + open a PR if the spec is in its own worktree (framework ADR 0005). Wraps `superpowers:requesting-code-review`/`finishing-a-development-branch`, when enabled |
| `worktree.md` | `/worktree` | Creates an isolated git worktree for a whole spec from a known-clean remote branch (branch name must match the spec's own short-name — `/implement` looks it up by that name, see framework ADR 0005), so several specs can run `/implement` at the same time, each in its own session. Names `superpowers:using-git-worktrees` as the same discipline, when enabled, without replacing its own origin-pinned steps |
| `adr.md` | `/adr` | Records a decision directly via `architect`, for something with no spec/task attached |
| `quick.md` | `/quick` | Fast lane (framework ADR 0020): triages a free-text request with no spec. Trivial → `quickfix` + build/test gate, no spec, no review; standard → a one-file lite spec, then `/implement`; structural → the full `/spec` → `/plan` path. Only ceremony shrinks — constitution, gate and scope rules are unchanged |
| `update-docs.md` | `/update-docs` | For census-enabled projects (framework ADR 0019): freshness → census → drift → commits since the watermark (pending entries first) → findings → watermark, which advances only when every commit is handled. `promote <doc>` runs the independent `draft` → `active` verification |
| `metrics.md` | `/metrics` | Per-feature cost from the event log — subagents, gate runs/failures, reviewer verdicts, rework — fast lane vs. full path side by side (framework ADR 0020) |
| `reconcile.md` | `/reconcile` | On-demand spec-vs-code fidelity sweep for a spec already `implemented` — no file list, no diff, no build/test gate prerequisite. Delegates to `reviewer`'s sweep scope, which judges current code state against the spec's `FR-NN`/`AC-NN` and appends a dated `### Sweep` block to "## Reconciliation" (framework ADR 0012). Closes the gap framework ADR 0009 explicitly left open: post-implementation drift, not just drift during the original `/implement` sweep |
| `setup-framework.md` | `/setup-framework` | Single entry point for adopting/maintaining this framework. **Opens with one mutually exclusive adoption-mode question (framework ADR 0014)** — a whole-repo commitment that's expensive to undo, so it explains each option's real trade-offs rather than listing labels, and detects an already-adopted mode to offer as the default. **(A) Direct in-repo** → Domains 1-4, unchanged. **(B) External AI-repo** → Domain 5. **(C) User-level, multi-project** → Domain 6. Domain 2 is the exception to that routing: plugins are per machine, so it's offered in any mode. Domain 1: detects+asks to resolve every `{{PLACEHOLDER}}` and renames the template/example files that are ready (`CLAUDE.md.template`, `settings.example.json`, `auto_format.py.example`, `overview.md.template`, `glossary.md.template`). Domain 2: checks globally enabled plugins against `docs/workflow/plugin-integrations.md`'s Core list, installs missing ones only with explicit confirmation. Domain 3: merges `.mcp.json.example`/`.gitignore.framework-additions` into this repo's real `.mcp.json`/`.gitignore` — creates either if missing, only adds what's not already there if not, never overwrites existing content — then deletes the now-redundant source files. Domain 4 (optional): asks to draft `docs/architecture/module-structure.md`/`frontend.md` from patterns detected in an existing codebase — always a clearly-marked draft, never silently finalized (framework ADR 0006). Domain 5 (mode B): runs from this repo (already fully set up) and links a *separate* target code repo to it via never-committed relative symlinks/junctions/hard links at `<target>/.claude` → the one shared `.claude/`, `<target>/docs` → the AI-repo's **shared `docs/` root**, and `<target>/CLAUDE.md` → `docs/<name>/CLAUDE.md` (the same conventional paths Domain 1 would otherwise copy files to, so every hook/agent/command keeps working unmodified), plus a bootstrap `CLAUDE.md` note at the *lowest common ancestor* of the two repos — any shared ancestor works, so the target repo can sit at any depth inside someone else's monorepo — that tells any session in the target repo to stop and demand this setup if the links are missing. Per framework ADR 0013 it *always* uses the per-project-subtree mechanism (one project is just N=1 — there's no single-vs-multi question), and per framework ADR 0015 that subtree is `docs/<name>/` **inside** the shared `docs/` tree, not a separate `projects/` folder — which is why the `docs` link points at the root (keeping `docs/workflow/*`, `docs/constitution.md`, `docs/glossary.md` and the `product/` templates reachable) while project content is reached by resolved absolute path instead. It also reserves `workflow`/`product`/`architecture`/`decisions`/`glossary` as project names, since those collide with the shared root's own folders. It writes two config files with different lifecycles: the gitignored per-machine `.claude/projects.local.json` (routing: this machine's `CLAUDE_PROJECT_DIR` → that project's subtree; `projects_root` now defaults to `<ai-repo>/docs`) and the committed `docs/<name>/project-config.json` (build/test command + language values, never overwritten without asking). Zero Claude-related footprint inside the target repo itself. Domain 6 (mode C): runs `scripts/install_user_level.py` from this repository (framework ADR 0017) — dry run, confirm, `--apply`. Agents/commands/skills are installed under a namespace prefix (`cfw-coder`, `/cfw-spec`), everything else under `~/.claude/<prefix>/` (hooks, scripts, registry, `framework.json`, the shared `docs/` root — never the framework's own `evolution/` specs and ADRs), every cross-reference rewritten, `settings.json` merged additively with absolute hook paths, a manifest recorded for `uninstall.py`. Collisions and hand-edited installed files abort the run. Optionally registers several repos in one pass and imports an existing doc base. Registration otherwise stays lazy (framework ADR 0014). New setup domains get added here, not as new top-level commands. |

## skills/ — knowledge that applies at any stage

Unlike commands, skills trigger on relevance (an agent reads the
`description` and decides it applies), not on sequence. See
`skill-authoring/SKILL.md` for the exact test that decides whether
new knowledge belongs here or inside a command/agent body.

| File | Purpose | Status in this template |
|---|---|---|
| `adr-writing/SKILL.md` | The fixed ADR format + immutability rule | Fully generic, use as-is |
| `skill-authoring/SKILL.md` | How to decide Skill vs. command vs. agent body, and how to structure a new Skill | Fully generic, use as-is |
| `plugin-awareness/SKILL.md` | Discipline absorbed from this machine's Core plugins (works even if they're not installed) + how to suggest an Optional plugin/MCP without installing it. Per framework ADR 0003, the `superpowers` discipline listed here now spans `/spec`, `/plan`, `coder`/`quickfix`, `/implement`, `/review`, and `/worktree`, not just `coder` (`/tasks` stays out of it — framework ADR 0004 makes it purely mechanical) | Generic mechanism, but its worked-example plugin list (`docs/workflow/plugin-integrations.md`) reflects one machine's install — edit that table for yours |

This framework deliberately carries no example domain/architecture
skill — a tenant-isolation checklist, a module-scaffolding pattern, a
sensitive-data rule, all of that assumes a specific architecture or
domain that not every project shares. Write your own the first time
your project needs one, following `skill-authoring/SKILL.md`'s format;
it'll usually be a checklist tied to whatever your project's own
`docs/architecture/*.md` establishes.

**How an agent finds out a project-specific skill applies to it:**
each skill's frontmatter can tag `applies_to: [coder, reviewer]` (any
subset of the agent names above — omit it for a skill that isn't tied
to one pipeline role, like `skill-authoring` itself). Adding a skill to
a project is then a one-file change: tag it once, at the source. Never
edit an agent's own file to "register" a skill for it — that creates
exactly the kind of N-places-to-keep-in-sync duplication the "reference,
never copy" practice in `../docs/workflow/ai-first-development.md`
exists to avoid. `skill_index.py` (below) rebuilds
`.claude/skills/README.md` from these tags automatically, and every
agent whose body says "check `.claude/skills/README.md`" is expected to
look for its own name there before starting a task.

## hooks/ — deterministic, zero-token-cost checks

Each hook reads a JSON event on stdin (what tool ran, on what file)
and either does something to the filesystem directly, or returns a
decision (e.g. block an edit) — no LLM call involved. Wired up in
`settings.example.json`.

| File | Event | What it does |
|---|---|---|
| `session_brief.py` | `SessionStart` | Injects git status + which specs are still in flight (not `implemented` or `abandoned`) + the last session's handoff note (below), so the agent doesn't spend a tool call rediscovering it |
| `plugin_gap_check.py` | `SessionStart` | Deterministically flags when the repo's dominant language has an official marketplace LSP plugin that isn't enabled globally (e.g. `.cs` files, `csharp-lsp` not on) — never blocks, just suggests running `/setup-framework`. Respects `.claude/.plugin-gap-dismissed.json` (per-machine, gitignored) so a plugin you declined via `/setup-framework` stops being suggested every session |
| `session_handoff.py` | `SessionEnd` | Snapshots `last_assistant_message` (the hook event's own field — no transcript parsing, no LLM call) to `.claude/session-handoff.md`, overwritten each time, for the next `session_brief.py` to surface |
| `spec_number_guard.py` | `PreToolUse` (Write) | Blocks creating a new spec whose `NNNN` prefix collides with an existing one in `docs/product/specs/` |
| `adr_immutability_guard.py` | `PreToolUse` (Edit) | Blocks editing an ADR whose `status: accepted` — supersede instead |
| `adr_backlink.py` | `PostToolUse` (Write) | When a new ADR declares `supersedes: NNNN`, sets the old ADR's `superseded_by` automatically |
| `decision_index.py` | `PostToolUse` (Write/Edit) | Rebuilds `docs/decisions/README.md` — a one-line-per-ADR index (id, title, status, supersedes) — so an agent can see what decisions exist without opening or globbing every file |
| `spec_index.py` | `PostToolUse` (Write/Edit) | Same idea, for `docs/product/specs/README.md` |
| `spec_status_sync.py` | `PostToolUse` (Edit) | Flips a spec's `status` to `implemented` automatically once every checkbox in its `## Tasks` section is checked — only from `approved`, never from `draft` or `abandoned`. Also logs a `spec_implemented` pipeline-metrics event (framework ADR 0011) at the moment it flips |
| `skill_index.py` | `PostToolUse` (Write/Edit) | Rebuilds `.claude/skills/README.md` — a one-line-per-skill index (name, `applies_to` agents, description) — from each `SKILL.md`'s own frontmatter |
| `context_budget_check.py` | `PostToolUse` (Edit/Write) | Warns (never blocks) when a doc under `docs/` is more than 2x past its own frontmatter's `context_budget` estimate — a rough chars/4 heuristic, no tokenizer dependency |
| `frontmatter_check.py` | `PostToolUse` (Edit/Write) | Warns (never blocks) when a doc under `docs/` is missing `doc_type`/`status`/`context_budget` — the fields the rest of this framework's tooling depends on |
| `claude_md_index_check.py` | `PostToolUse` (Edit/Write) | Warns (never rewrites) when `CLAUDE.md`'s own "Index" table quotes a different `~Cost` than the doc it points at now declares in its own frontmatter — see the note below on why this one only nudges |
| `constitution_amendment_check.py` | `PostToolUse` (Edit/Write, constitution files only) | Warns (never blocks) when a constitution changed since the last commit without its `version`/`last_amended` frontmatter moving too — compares against the file's own committed path via `git show HEAD:<path>`, fails open if git isn't available (framework ADR 0007). Since framework ADR 0015 it watches **both** layers independently: the shared `docs/constitution.md` and a project's own `docs/<name>/constitution.md`. "The project one never weakens the supreme one" stays a semantic judgment `reviewer`/`coder` make while reading both — deliberately not a syntactic check |
| `secret_leak_guard.py` | `PreToolUse` (Edit/Write, repo-wide) | Blocks a write whose new content matches a high-confidence credential pattern (AWS key ID, GitHub/Slack token, a private-key block) — stdlib regex, no scanner dependency, active by default. Never reads `docs/constitution.md`; works the same with or without it (framework ADR 0010) |
| `validation_sync_check.py` | `PostToolUse` (Edit/Write) | Decides deterministically whether an approved spec's stakeholder-language companion needs re-syncing (language split? approved? requirements hash changed since the companion's `source_hash`?) and only then hands the session an exact instruction with absolute paths. Replaced the always-on Sonnet `agent` hook (framework ADR 0020) |
| `project_tools.py` | `PostToolUse` (Edit/Write) | Runs the formatter / dependency-audit commands a project declares under `project_tools` in its own config; nothing when absent. The shared-install replacement for the two `.example` hooks below (framework ADR 0017) |
| `auto_format.py.example` | `PostToolUse` (Edit/Write) | Template: runs your stack's formatter/linter on the file just touched. Rename to `auto_format.py` once you've filled in the real commands |
| `dependency_audit.py.example` | `PostToolUse` (Edit/Write, no-ops unless the file is a recognized dependency manifest) | Template: runs your ecosystem's vulnerability audit (`npm audit`, `pip-audit`, …) when a manifest changes, reports findings as a `systemMessage`. Rename to `dependency_audit.py` once you've trimmed it to your real ecosystem(s) (framework ADR 0010) |
| `pipeline_metrics.py` | `PostToolUse` (spec Write/Edit; subagent dispatch matched on `Task`/`Agent`) | Appends `spec_created`, `reconciliation_snapshot`, and `reviewer_verdict` events to the git-ignored `.claude/pipeline-metrics.jsonl` — raw observability, no dashboard. `reviewer_verdict` depends on your Claude Code version's subagent-dispatch tool actually being named `Task` or `Agent`; check empirically (framework ADR 0011) |
| `_pipeline_metrics.py` | *(not wired — imported)* | Shared `log_event()` helper both `pipeline_metrics.py` and `spec_status_sync.py` import; not a hook entry point itself |
| `_project_paths.py` | *(not wired — imported; also a CLI)* | The routing lookup every multi-project-aware hook shares (framework ADR 0013/0014): `resolve_project_root()` (this session's project subtree), `load_project_config()`, `state_file_path()`, `resolve_shared_docs_root()`, and `project_relative_path()` — the last being how a directory-scoped hook decides a `file_path` is its business whether it arrived relative or absolute (see below). Reads a user-level install's `framework.json` before inferring anything, and holds the **registration gate** `hook_should_run()` every hook calls first: under a user-level install an unregistered repo gets no hook effect at all (framework ADR 0017). `python _project_paths.py describe` prints the whole resolution as JSON — the `project-registration` skill's probe. Fails open to classic single-repo behaviour everywhere else |

Two of these hooks depend on a convention, not just file location:
`spec_status_sync.py` only works if `/tasks` actually writes checkbox
items (`- [ ] 1. ...`) in the spec's `## Tasks` section and `/implement`
checks them off — both commands already say so. And
`.claude/session-handoff.md` (written by `session_handoff.py`) is
per-machine operational state, not project documentation —
`.gitignore.framework-additions` already covers it, alongside
`.claude/settings.local.json`; run `/setup-framework` (Domain 3) to
merge those entries into your repo's real `.gitignore`.

In the multi-project modes (B and C) that per-machine state can't live
under the one shared `.claude/` — it would become the same physical
file for every project. Per framework ADR 0013 those four files
(`session-handoff.md`, `pipeline-metrics.jsonl`, `settings.local.json`,
`.plugin-gap-dismissed.json`) move into each project's own subtree,
resolved through the routing lookup — which since framework ADR 0015 sits at
`docs/<name>/`, inside the one shared `docs/` tree rather than a
separate `projects/` folder. `.gitignore.framework-additions` carries a
`docs/*/` pattern for each of them, plus `.claude/projects.local.json`
for the routing file itself. The accepted cost, named in framework ADR 0015: a
`docs/` tree that is no longer purely documentation.

## Why `claude_md_index_check.py` only nudges, unlike the other index hooks

`decision_index.py`, `spec_index.py`, and `skill_index.py` fully own the
file they rebuild — each target (`docs/decisions/README.md`,
`docs/product/specs/README.md`, `.claude/skills/README.md`) starts with
"auto-generated, do not edit by hand," so silently regenerating it from
scratch on every write is safe: there's no human prose in there to
clobber. `CLAUDE.md` is the opposite — a hand-authored file where the
"Index" table is one part surrounded by editorial content specific to
your project. A hook has no business rewriting a line inside a file
like that without a human looking, so `claude_md_index_check.py` only
ever prints a `systemMessage` when a doc's `context_budget` frontmatter
drifts from what `CLAUDE.md`'s table says about it — same posture as
`context_budget_check.py` and `frontmatter_check.py`. This exists
because that exact drift happened in practice: several docs' budgets
changed and nobody remembered to update `CLAUDE.md`'s copy of the
number until this hook was added to catch it going forward.

## settings.example.json

Wires every hook above to its event. Since framework ADR 0020 the build/test gate
calls `run_build_test.py` (which reads `build_test_cmd` from the
optional mode A config `.claude/project-config.json` and skips read-only
subagents), and the stakeholder-language validation sync is the command
hook `validation_sync_check.py`, not an always-on agent. Rename to
`settings.json` once Domain 1 has written `.claude/project-config.json`
— and, per framework ADR 0010, once `dependency_audit.py.example` is trimmed to
your real ecosystem(s) and renamed the same way
`auto_format.py.example` already needs to be.

This is the **mode A (direct in-repo)** settings file, and it stays
exactly as described above. It can't serve modes B/C, for the reason
framework ADR 0013 gives: it relies on relative paths and the repo-local
`.claude/hooks/`, and its `if` filters only match mode A's relative
paths, while those modes share a single `settings.json` across every
project.

## settings.multi-project.json.example

The variant modes B and C use instead, for a `settings.json` shared by
several projects. Same permissions and the same set of hooks as the
classic file — four things differ:

- **The directory-scoped hooks carry no `"if"` filter here.** In mode C
  nothing redirects a relative path, so a command writes a spec or an ADR
  by its *resolved absolute* path
  (`.claude/skills/project-registration/SKILL.md` says so explicitly) —
  and a literal-prefix condition like `Write(docs/product/specs/*)` can't
  match that. Rather than bet six hooks (spec numbering, ADR
  immutability/backlinking, both indexes, constitution amendment
  checking) on how `file_path` happens to be reported, they run on every
  `Edit|Write` and self-gate in their own code via
  `_project_paths.project_relative_path()` — the same posture
  `auto_format.py`, `frontmatter_check.py` and friends already had here.
  A hook that silently never fires has no visible symptom, which is
  exactly the failure this avoids. `settings.example.json` (mode A) keeps
  its `if` conditions: a single-project repo never sees the absolute-path
  shape.

- **How Claude Code actually matches these rules** (checked against
  v2.1.252 on 2026-10-03, in fresh headless sessions):
  - An `if` belongs on each **handler** object inside `hooks`. On the
    group, next to `matcher`, it is silently ignored and the handler
    always runs. `settings.example.json` used to have it on the group, so
    its filters never filtered anything; the self-gating code kept it
    correct.
  - In an `if`, the tool name is literal: `Write(path)` filters Write
    calls and `Edit(path)` filters Edit calls. An absolute `//c/...` path,
    with spaces and accents, matches.
  - In a **permission** rule it's the other way round: `Write(path)`
    rules are never used for file checks (Claude Code warns about it at
    startup), and `Edit(path)` covers every file-editing tool. That's why
    both templates allow spec writes with `Edit(...)`. Project-relative
    `/x`, `~/x` and absolute `//c/x` forms all match.
  - Settings changes to hooks are picked up mid-session; permission
    rules apparently only at session start.

- **`{{HOOKS_DIR}}`** replaces the `${CLAUDE_PROJECT_DIR:-.}/.claude/hooks`
  prefix in every hook command, because where the hooks live depends on
  where this file is deployed. `/setup-framework` resolves it when it
  writes the real `settings.json`: Domain 5 (mode B) →
  `${CLAUDE_PROJECT_DIR:-.}/.claude/hooks`, since the target repo's
  `.claude` is a real link to the shared one; Domain 6 (mode C) →
  `~/.claude/hooks`, since no project has a `.claude` at all. `~`
  expands because every hook here runs in shell form — the existing
  `${CLAUDE_PROJECT_DIR:-.}` is itself bash parameter expansion, so
  bash-compatible execution was already load-bearing (framework ADR 0014). It's
  a template, not a one-shot: unlike Domain 1's renames, the `.example`
  file stays in place for the next AI-repo or machine.
- **The `SubagentStop` gate runs `run_build_test.py`** instead of a
  literal `{{BUILD_TEST_CMD}}`. That hook reads `build_test_cmd` from
  the current project's `project-config.json` (via the routing lookup)
  and executes it, propagating its exit code — so the gate still blocks
  on a failed build exactly as in mode A.
- **(Superseded by framework ADR 0020.)** The two validation-summary `agent` hooks
  described below are gone from both settings templates; the command
  hook `validation_sync_check.py` decides from the project config and
  resolved paths, and only then asks the session to sync. The original
  note, kept for history: the two validation-summary `agent` hooks resolve their own
  languages.** Their prompts no longer embed `{{CANONICAL_LANG}}`/
  `{{STAKEHOLDER_LANG}}`/`{{STAKEHOLDER_LANG_CODE}}`; a step 0 tells the
  agent to find `projects.local.json` (project root first, then
  `~/.claude` — the same two places Claude Code itself looks for
  `.claude/`), look up its own `CLAUDE_PROJECT_DIR`, read that
  project's `project-config.json`, and fail open with a nudge if any
  step misses.

## scripts/ — framework tools, run on demand

Not hooks: commands and the installer call them explicitly. Stdlib-only
Python, JSON output, dry run by default wherever they write.

| File | What it does |
|---|---|
| `install_user_level.py` | Mode C install/upgrade (framework ADR 0017): namespace prefix, reference rewriting, `framework.json`, manifest, settings merge, collision and hand-edit refusal. Run from this repository; not itself installed |
| `uninstall.py` | Removes exactly what the manifest lists; restores `settings.json` byte for byte; keeps the registry and project subtrees; restores retired files on request |
| `register_project.py` | The deterministic half of lazy registration — one repo, or several from a plan file (bulk) |
| `migrate_context.py` | Imports an existing doc base into an framework ADR 0015 subtree: folder mapping, per-project numbering, frontmatter, link rewriting, verification; never touches the source |
| `census.py` + `census_extractors/` | The census engine (framework ADR 0019): inventory at the integration ref, drift, doc mentions, inline probes, ledger with watermark |
| `metrics.py` | Feature markers for the event log, and the `/metrics` report (framework ADR 0020) |

The framework's own tests live in `../tests/` (`python -m unittest` from
there); they exercise every acceptance criterion of specs 0001–0003 in
throwaway folders and never touch the real `~/.claude`.

## Why a Write/Edit to the wrong directory doesn't silently misfire

Every hook above that scopes itself to one directory (`spec_number_guard`,
`decision_index`, `spec_index`, `skill_index`, `adr_backlink`,
`adr_immutability_guard`, `spec_status_sync`, `pipeline_metrics`)
compares **normalized** paths (forward slashes, no trailing slash)
rather than raw string equality — Windows mixes `\` and `/` freely, and
naive `os.path.dirname(x) == y` comparisons break the moment one side
uses a different separator than the other.

All of them do it through one shared helper,
`_project_paths.project_relative_path(project_dir, file_path)`, which
answers "where is this file, relative to the root that owns this
session's documentation?" — `"docs/decisions/0001-x.md"` in mode A, or
`None` if it's outside. It resolves the reported path against the
routed project subtree *and* against `CLAUDE_PROJECT_DIR`, so the same
check holds for the relative path mode A writes and for the resolved
absolute one a mode B or mode C command has to use (since framework ADR 0015 the
`docs` link no longer redirects project content in mode B either, so
both routed modes arrive absolute). Match against **that** relative
form, never against the raw input: a prefix/substring test on the raw
string can only ever be right for one of the two shapes, and the wrong
one gives you a hook that silently never fires instead of a visible
error.

One consequence to watch when adding or changing a hook: the string
that helper returns is **not the same shape in both cases**. Matched
against `CLAUDE_PROJECT_DIR` (mode A) an ADR is
`docs/decisions/0001-x.md`; matched against a routed subtree it is
`decisions/0001-x.md`, because framework ADR 0015 put the project's own folders
directly in the subtree with no second `docs/` level. A caller that
tests for a literal `docs/` prefix therefore covers mode A only —
`_project_paths.py`'s own module docstring carries this as a named open
item against the hooks that still do.

`constitution_amendment_check.py` is the one deliberate exception, and
framework ADR 0015 changed what it has to recognize. There are now **two**
constitutions in the multi-project modes — the shared
`docs/constitution.md` and a project's own
`docs/<name>/constitution.md` — so matching on "the final two path
components are `docs/constitution.md`" is no longer sufficient, and
deriving the git repo root from the file's grandparent is wrong for the
project-level one (its committed path is `docs/<name>/constitution.md`,
one level deeper). It recognizes both shapes and diffs each against its
own committed path, still nudging rather than blocking, still failing
open without git.

## Why the index hooks only parse the frontmatter block

`decision_index.py`, `spec_index.py`, and `skill_index.py` all extract
the text between the first pair of `---` lines and run their field
regexes against *that*, never the whole file. Earlier versions matched
against the full content, and `skill_index.py` picked up a false
`applies_to: [coder, reviewer]` from `skill-authoring/SKILL.md`'s own
template *example* in its body — the regex doesn't know the difference
between real frontmatter and a code block that merely looks like it.
Any new field you add to one of these parsers needs the same
frontmatter-only scoping.
