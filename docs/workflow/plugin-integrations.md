---
doc_type: workflow
scope: plugin-integrations
status: active
last_updated: {{DATE}}
context_budget: ~1550 tokens
related: [../decisions/0002-plugin-integration.md, ../decisions/0003-superpowers-sdd-wrapping.md, ../decisions/0004-plan-tasks-implement-rebalance.md]
context: This catalog is a worked example — the exact table below
  reflects the official `claude-plugins-official` marketplace as
  installed on the machine this framework was extended on. Replace it
  with whatever's actually installed on yours; the mechanism (Core vs
  Optional, absorbed discipline, gated install) is what's meant to
  travel with the framework, not this specific plugin list.
---

# Plugin integrations — Core vs Optional

Claude Code plugins are installed per user account, globally across
every project on a machine — unlike everything else under `.claude/`,
which is repo-local. This doc splits what's out there into two
buckets and says what this framework actually does with each. The
mechanism itself is recorded in
`../decisions/0002-plugin-integration.md`; this file is the table you
keep current.

## Core — useful on effectively any project

| Plugin | What it gives you | Where it complements the pipeline | How this framework uses it |
|---|---|---|---|
| `superpowers` | Brainstorming/planning methodology, TDD discipline, systematic debugging, parallel-agent orchestration, review-feedback discipline, git-worktree isolation, branch finishing | `/spec`, `/plan`, `coder`/`quickfix` (implementation), `/implement` (orchestration), `/review`, `/worktree` | Wrapped at each matching stage as a complementary pass when installed (see `docs/decisions/0003-superpowers-sdd-wrapping.md` for the mapping, `docs/decisions/0004-plan-tasks-implement-rebalance.md` for what each stage itself does): `/spec` invokes `brainstorming`; `/plan` invokes `writing-plans` for standard/structural tiers (never trivial); `/tasks` invokes nothing — pure mechanical decomposition; `/implement`'s orchestration mode invokes `dispatching-parallel-agents`/`subagent-driven-development` to structure parallel task waves and `executing-plans` to run a spec's task list to completion; `coder` invokes `test-driven-development`, `systematic-debugging`, `receiving-code-review`, and `verification-before-completion`; `quickfix` carries the `verification-before-completion` discipline absorbed only — it has no `Skill` tool, kept deliberately cheap per ADR 0002; `/review` invokes `requesting-code-review` and points at `finishing-a-development-branch` once approved; `/worktree` names `using-git-worktrees` as the same discipline without replacing its own origin-pinned steps. The equivalent discipline is written into `plugin-awareness` for when it isn't installed — this framework's own commands stay the sequencing authority either way. |
| `code-review` | Configurable-effort correctness/simplification review | `/review` → `reviewer` | `reviewer` invokes it as a complementary pass when installed, folding real findings into its own verdict. Its own checklist pass stays authoritative either way. |
| `pr-review-toolkit` | Specialized reviewers (silent-failure-hunter, type-design-analyzer, test-coverage, comment accuracy) | `/review` → `reviewer` | Same as `code-review` — complementary, not a replacement. |
| `security-review` | Security-focused review of pending changes | `reviewer` (any scope), `coder` | Invoked for a security-sensitive diff (auth, secrets, input handling); a finding maps to a named Core Principle when `docs/constitution.md` exists (ADR 0010). Its value doesn't depend on the constitution file being present. |
| `code-simplifier` | Post-hoc simplification pass, functionality preserved | `coder`, after implementation is green | `coder` runs it once tests pass, before considering the task done, when installed. |
| `context7` (MCP) | Current library/framework docs | `researcher`, `architect` | Already wired via `.mcp.json.example` — no change from this ADR. |

## Optional — situational, install only if it applies to this project

| Plugin / MCP | Applies when | How this framework surfaces it |
|---|---|---|
| `csharp-lsp` | The repo is (or has a substantial) C# codebase | `plugin_gap_check.py` flags it automatically at session start if `.cs` files dominate and the plugin isn't enabled globally |
| `typescript-lsp` | The repo is (or has a substantial) TypeScript/JS codebase | Same mechanism, for `.ts`/`.tsx` |
| `frontend-design` | The project has a real frontend with visual/UX decisions | Not auto-detected — mention it to the user if a task is frontend-heavy and it isn't enabled |
| `azure-devops` (MCP, user-configured — org + PAT, not a marketplace plugin) | The project's issue tracker / repos / pipelines live in Azure DevOps | Not auto-detected (an MCP server, not a file-extension signal) — `plugin-awareness` instructs agents to suggest it if they notice repeated manual Azure DevOps lookups |
| `ralph-loop` | Long-running autonomous loop workflows | Orthogonal usage style, user-invoked directly — catalog entry only |
| `skill-creator`, `claude-code-setup` | Authoring/evaluating skills; one-time automation audits of a new codebase | Meta-tools used occasionally outside the pipeline — catalog entry only |

## Installing what's missing

Run `/setup-framework` — it checks what's globally enabled against the Core
list above, asks before installing anything (default scope: `user`,
i.e. every project on this machine, not just this one), and never
installs Optional entries without you naming one explicitly. Declining
everything is safe: every Core plugin's value has a written fallback
in `.claude/skills/plugin-awareness/SKILL.md`, so nothing in the
pipeline breaks — it just runs without the complementary pass.
`superpowers` specifically now backs a complementary pass at nearly
every SDD stage (`/spec`, `/plan`, `coder`/`quickfix`, `/implement`,
`/review`, `/worktree` — see the row above and
`docs/decisions/0003-superpowers-sdd-wrapping.md`), so it's worth
installing even on a project where you don't expect to lean on the
other Core plugins.

For an Optional, language-specific plugin `plugin_gap_check.py` flags
at session start, `/setup-framework` also offers "don't ask again" —
it records that choice in `.claude/.plugin-gap-dismissed.json`
(per-machine, gitignored) so a deliberate decline doesn't turn into a
nag on every future session.

### Copy-paste example: adding an org-specific MCP (Azure DevOps)

Optional MCPs like `azure-devops` are org-tied (organization name +
personal access token), so they're never auto-installed. Add this to
your own `.mcp.json` (never commit a real PAT — use an env var):

```json
{
  "mcpServers": {
    "azure-devops": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@azure-devops/mcp", "{{AZURE_DEVOPS_ORG}}", "--authentication", "pat"],
      "env": { "AZURE_DEVOPS_PAT": "{{AZURE_DEVOPS_PAT_ENV_VAR}}" }
    }
  }
}
```

## Keeping this table current

When you install or remove a global plugin and it changes which bucket
it belongs in, edit this table directly — nothing regenerates it
automatically (unlike `docs/decisions/README.md` or
`.claude/skills/README.md`, this isn't a per-file index, it's a
judgment call about your own machine's setup).
