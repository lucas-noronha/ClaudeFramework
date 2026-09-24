# `.claude/` — how this machinery works

This is the component reference: what each file in here does and why
it exists. For "how do I adopt this in a new project," see the
repository root's `README.md` instead — this one assumes you've
already read that and want to understand (or modify) the pipeline
itself.

The short version, from `docs/decisions/0001-tooling-agents-commands-skills.md`:
**subagents** are pipeline roles, **commands** are the pipeline's
deterministic entry points, **skills** are knowledge that applies at
any stage, **hooks** are deterministic checks that cost zero tokens.
Four different primitives because conflating them (e.g. using a Skill
for sequencing) makes the pipeline depend on probabilistic text
matching for something that should be exact.

One more file sits above all four: `../docs/constitution.md` (ADR
0007) — non-negotiable, versioned principles `/spec`, `/plan`,
`coder`/`quickfix`, and `reviewer` all check against, amended under its
own Governance section rather than edited silently.

## agents/ — the pipeline roles

Each file is one subagent: a name, a fixed `model` tier (see
`../docs/workflow/model-tiering.md` for why each gets the tier it
gets), a fixed tool list, and its own isolated context — it never sees
the calling session's conversation, only what's explicitly handed to
it.

| File | Role | Called by |
|---|---|---|
| `triage.md` | Classifies a task's size (trivial/standard/structural) in one sentence, implements nothing | `/plan`, `/implement` |
| `architect.md` | Assesses structural impact, drafts an ADR if one is needed, never writes implementation code | `/plan` (structural tier), `/adr` |
| `researcher.md` | Answers one pointed external/domain question, returns a conclusion not raw research | `architect`, `coder`, on demand |
| `coder.md` | Implements standard/structural tasks with tests, following the architecture docs and skills relevant to what it's touching | `/implement` (standard/structural tier, single-task or orchestration mode) |
| `quickfix.md` | `coder`'s cheaper sibling for genuinely trivial, single-file fixes | `/implement` (trivial tier) |
| `reviewer.md` | One review pass against an explicit checklist (including the spec's Test plan coverage; the Definition of Done and "## Reconciliation" completeness too, when the scope is the whole feature), after the build/test hook is already green. Per-task scope also appends reconciliation entries to the spec's own "## Reconciliation" section for that task's `FR-NN`/`AC-NN` tags (ADR 0009) — the only agent with `Edit` access beyond `coder`/`quickfix`. Invokes the `security-review` skill for a security-sensitive diff, folding a finding into a named Core Principle when `docs/constitution.md` exists (ADR 0010). A third **sweep scope**, called only from `/reconcile`, audits an already-`implemented` spec against current code state — no diff, no gate, appends a dated sweep block instead of an Approved/Returned verdict (ADR 0012) | `/review` (whole-feature diff); also fired automatically inside `/implement`'s orchestration mode, scoped to one task's own files (see ADR 0004); `/reconcile` (sweep scope) |

## commands/ — the pipeline's deterministic entry points

Each file is a slash command: fixed steps, explicit delegation to the
right subagent(s). The sequence never depends on an agent "deciding"
which stage it's in.

| File | Command | What it does |
|---|---|---|
| `spec.md` | `/spec` | Formalizes an idea into a spec file (+ stakeholder-language companion, if configured) from the requirements template. Wraps `superpowers:brainstorming` first, when enabled (see ADR 0003), and always checks the described solution actually follows from the underlying business problem before formalizing it — flagging a mismatch as an "unclear, ask" item instead of silently proceeding. Also auto-assigns the spec's own `area`/`relates_to` lineage from the existing spec index (ADR 0008, never asked of the human) and checks the request against `docs/constitution.md`, if present |
| `plan.md` | `/plan` | Triages complexity; trivial stops there, standard writes a short technical plan + Definition of Done + Test plan (numbered against the spec's `FR-NN`/`AC-NN`), structural adds `architect` (+ ADR) plus the same three artifacts and an explicit scope-creep check (see ADR 0004). Wraps `superpowers:writing-plans` for standard/structural, when enabled |
| `tasks.md` | `/tasks` | Mechanically breaks the technical plan into small, dependency-annotated (`Depends on:` per task) `/implement`-sized tasks, distributing the Test plan's entries one-to-one across them (`Tests:` per task) — no technical judgment happens here (ADR 0004) |
| `implement.md` | `/implement` | Single-task mode: routes one task to `quickfix`/`coder`. Orchestration mode (spec path instead of a task): first checks/offers a spec-scoped worktree (ADR 0005), then dispatches dependency-ready waves in parallel, one isolated subagent per task (never a worktree per task — isolation stops at the spec), auto-`reviewer` per coder-tier task before checking it off (ADR 0004). Wraps `superpowers:dispatching-parallel-agents`/`subagent-driven-development`/`executing-plans` in orchestration mode, when enabled |
| `review.md` | `/review` | Final, whole-feature pass: runs `reviewer` against the cumulative diff plus the spec's Definition of Done, once the build/test hook is green — complements `/implement`'s per-task pass, doesn't replace it. On Approved, offers to push + open a PR if the spec is in its own worktree (ADR 0005). Wraps `superpowers:requesting-code-review`/`finishing-a-development-branch`, when enabled |
| `worktree.md` | `/worktree` | Creates an isolated git worktree for a whole spec from a known-clean remote branch (branch name must match the spec's own short-name — `/implement` looks it up by that name, see ADR 0005), so several specs can run `/implement` at the same time, each in its own session. Names `superpowers:using-git-worktrees` as the same discipline, when enabled, without replacing its own origin-pinned steps |
| `adr.md` | `/adr` | Records a decision directly via `architect`, for something with no spec/task attached |
| `reconcile.md` | `/reconcile` | On-demand spec-vs-code fidelity sweep for a spec already `implemented` — no file list, no diff, no build/test gate prerequisite. Delegates to `reviewer`'s sweep scope, which judges current code state against the spec's `FR-NN`/`AC-NN` and appends a dated `### Sweep` block to "## Reconciliation" (ADR 0012). Closes the gap ADR 0009 explicitly left open: post-implementation drift, not just drift during the original `/implement` sweep |
| `setup-framework.md` | `/setup-framework` | Single entry point for adopting/maintaining this framework. Domain 1: detects+asks to resolve every `{{PLACEHOLDER}}` and renames the template/example files that are ready (`CLAUDE.md.template`, `settings.example.json`, `auto_format.py.example`, `overview.md.template`, `glossary.md.template`). Domain 2: checks globally enabled plugins against `docs/workflow/plugin-integrations.md`'s Core list, installs missing ones only with explicit confirmation. Domain 3: merges `.mcp.json.example`/`.gitignore.framework-additions` into this repo's real `.mcp.json`/`.gitignore` — creates either if missing, only adds what's not already there if not, never overwrites existing content — then deletes the now-redundant source files. Domain 4 (optional): asks to draft `docs/architecture/module-structure.md`/`frontend.md` from patterns detected in an existing codebase — always a clearly-marked draft, never silently finalized (ADR 0006). New setup domains get added here, not as new top-level commands. |

## skills/ — knowledge that applies at any stage

Unlike commands, skills trigger on relevance (an agent reads the
`description` and decides it applies), not on sequence. See
`skill-authoring/SKILL.md` for the exact test that decides whether
new knowledge belongs here or inside a command/agent body.

| File | Purpose | Status in this template |
|---|---|---|
| `adr-writing/SKILL.md` | The fixed ADR format + immutability rule | Fully generic, use as-is |
| `skill-authoring/SKILL.md` | How to decide Skill vs. command vs. agent body, and how to structure a new Skill | Fully generic, use as-is |
| `plugin-awareness/SKILL.md` | Discipline absorbed from this machine's Core plugins (works even if they're not installed) + how to suggest an Optional plugin/MCP without installing it. Per ADR 0003, the `superpowers` discipline listed here now spans `/spec`, `/plan`, `coder`/`quickfix`, `/implement`, `/review`, and `/worktree`, not just `coder` (`/tasks` stays out of it — ADR 0004 makes it purely mechanical) | Generic mechanism, but its worked-example plugin list (`docs/workflow/plugin-integrations.md`) reflects one machine's install — edit that table for yours |

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
| `spec_status_sync.py` | `PostToolUse` (Edit) | Flips a spec's `status` to `implemented` automatically once every checkbox in its `## Tasks` section is checked — only from `approved`, never from `draft` or `abandoned`. Also logs a `spec_implemented` pipeline-metrics event (ADR 0011) at the moment it flips |
| `skill_index.py` | `PostToolUse` (Write/Edit) | Rebuilds `.claude/skills/README.md` — a one-line-per-skill index (name, `applies_to` agents, description) — from each `SKILL.md`'s own frontmatter |
| `context_budget_check.py` | `PostToolUse` (Edit/Write) | Warns (never blocks) when a doc under `docs/` is more than 2x past its own frontmatter's `context_budget` estimate — a rough chars/4 heuristic, no tokenizer dependency |
| `frontmatter_check.py` | `PostToolUse` (Edit/Write) | Warns (never blocks) when a doc under `docs/` is missing `doc_type`/`status`/`context_budget` — the fields the rest of this framework's tooling depends on |
| `claude_md_index_check.py` | `PostToolUse` (Edit/Write) | Warns (never rewrites) when `CLAUDE.md`'s own "Index" table quotes a different `~Cost` than the doc it points at now declares in its own frontmatter — see the note below on why this one only nudges |
| `constitution_amendment_check.py` | `PostToolUse` (Edit/Write, `docs/constitution.md` only) | Warns (never blocks) when the file changed since the last commit without its `version`/`last_amended` frontmatter moving too — compares against `git show HEAD:docs/constitution.md`, fails open if git isn't available (ADR 0007) |
| `secret_leak_guard.py` | `PreToolUse` (Edit/Write, repo-wide) | Blocks a write whose new content matches a high-confidence credential pattern (AWS key ID, GitHub/Slack token, a private-key block) — stdlib regex, no scanner dependency, active by default. Never reads `docs/constitution.md`; works the same with or without it (ADR 0010) |
| `auto_format.py.example` | `PostToolUse` (Edit/Write) | Template: runs your stack's formatter/linter on the file just touched. Rename to `auto_format.py` once you've filled in the real commands |
| `dependency_audit.py.example` | `PostToolUse` (Edit/Write, no-ops unless the file is a recognized dependency manifest) | Template: runs your ecosystem's vulnerability audit (`npm audit`, `pip-audit`, …) when a manifest changes, reports findings as a `systemMessage`. Rename to `dependency_audit.py` once you've trimmed it to your real ecosystem(s) (ADR 0010) |
| `pipeline_metrics.py` | `PostToolUse` (spec Write/Edit; subagent dispatch matched on `Task`/`Agent`) | Appends `spec_created`, `reconciliation_snapshot`, and `reviewer_verdict` events to the git-ignored `.claude/pipeline-metrics.jsonl` — raw observability, no dashboard. `reviewer_verdict` depends on your Claude Code version's subagent-dispatch tool actually being named `Task` or `Agent`; check empirically (ADR 0011) |
| `_pipeline_metrics.py` | *(not wired — imported)* | Shared `log_event()` helper both `pipeline_metrics.py` and `spec_status_sync.py` import; not a hook entry point itself |

Two of these hooks depend on a convention, not just file location:
`spec_status_sync.py` only works if `/tasks` actually writes checkbox
items (`- [ ] 1. ...`) in the spec's `## Tasks` section and `/implement`
checks them off — both commands already say so. And
`.claude/session-handoff.md` (written by `session_handoff.py`) is
per-machine operational state, not project documentation —
`.gitignore.framework-additions` already covers it, alongside
`.claude/settings.local.json`; run `/setup-framework` (Domain 3) to
merge those entries into your repo's real `.gitignore`.

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

Wires every hook above to its event, plus (as an example) an
agent-based `PostToolUse` hook that keeps a spec's stakeholder-language
validation summary in sync with its canonical file whenever the
canonical file changes post-validation. Rename to `settings.json` once
you've replaced `{{BUILD_TEST_CMD}}` with your project's real
build/test command — and, per ADR 0010, once `dependency_audit.py.example`
is trimmed to your real ecosystem(s) and renamed the same way
`auto_format.py.example` already needs to be.

## Why a Write/Edit to the wrong directory doesn't silently misfire

Every hook above that scopes itself to one directory (`spec_number_guard`,
`decision_index`, `spec_index`, `skill_index`, `adr_backlink`,
`adr_immutability_guard`) compares **normalized** paths (forward
slashes, no trailing slash) rather than raw string equality — Windows
mixes `\` and `/` freely, and naive `os.path.dirname(x) == y`
comparisons break the moment one side uses a different separator than
the other. If you add a new directory-scoped hook, follow the same
normalization, or you'll get a hook that silently never fires instead
of a visible error.

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
