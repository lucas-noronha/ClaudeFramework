---
doc_type: adr
id: 0002
status: proposed
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~1350 tokens
---

# ADR 0002 — Global plugin integration: Core vs Optional, absorbed not hard-wired

Like ADR 0001, this documents a decision about *this framework's own*
tooling (kept as a worked example) — the actual Core/Optional plugin
list is a property of whatever's installed on your machine, not a
mandate. Adjust `docs/workflow/plugin-integrations.md`'s table for your
own install; this ADR only fixes the *mechanism*.

## Context

Claude Code plugins are installed per user account, globally across
every project on a machine — unlike this framework's own `.claude/`,
which is repo-local. Some globally available plugins (a language LSP,
a deeper review pass, TDD/debugging discipline, an org-specific MCP
like Azure DevOps) genuinely improve the pipeline when present.
Unaddressed, either the framework ignores that capability, or its
commands/agents grow a hard dependency on a plugin the next machine
that copies this skeleton may not have.

## Options considered

- **Ignore plugins entirely.** Simplest, but wastes real capability and
  gives no answer for "what should I even install for this."
- **Hard-wire commands to plugins** (e.g. `/review` calls `code-review`
  directly). Most powerful, but breaks portability — the same command
  behaves differently, or errors, depending on the machine.
- **Absorb + complement, user-gated install** (chosen). Commands/agents
  stay the sequencing authority (ADR 0001 stands). A Core plugin's
  *discipline* is written into agent-facing material so it applies even
  when absent; when installed, the relevant subagent invokes it as a
  complementary pass. Installing anything is a deliberate, confirmed
  action — never silent.

## Decision

- **`docs/workflow/plugin-integrations.md`** — the catalog: **Core**
  (useful on effectively any project) vs **Optional** (situational — a
  language LSP, an org-tied MCP), what each does, which pipeline stage
  it complements.
- **`.claude/skills/plugin-awareness/SKILL.md`** — a meta-skill (no
  single `applies_to` stage, tagged to every hands-on role): (1) states
  the discipline absorbed from Core plugins (TDD/debugging rigor,
  review rigor) so an agent behaves accordingly whether or not the
  plugin is installed; (2) instructs agents to *suggest* (never
  install) an official plugin/MCP when they notice repetitive manual
  work it would replace, pointing at `/setup-framework`.
- **`.claude/hooks/plugin_gap_check.py`** — deterministic `SessionStart`
  check: scans file extensions against a fixed language→LSP-plugin
  table and the user's globally enabled plugins; suggests
  `/setup-framework` when the dominant language has no matching LSP
  enabled. Respects a per-machine dismiss list so declining doesn't nag
  every session. Never blocks.
- **`.claude/commands/setup-framework.md`** (`/setup-framework`) — the
  only place installation happens, and the general entry point for
  adopting/maintaining this framework; plugin installation is one
  domain among others (project bootstrap, scaffolding-file merges), not
  its whole purpose — the next optional capability gets a new domain
  here, not a new top-level command. For plugins specifically: checks
  what's enabled, asks via `AskUserQuestion` which missing Core plugins
  to install, runs `claude plugin install <name>@claude-plugins-official`
  for the accepted ones (`user` scope — genuinely global). Declining is
  a no-op: `plugin-awareness`'s absorbed discipline already covers that
  agent's behavior either way.
- **`coder` and `reviewer` gain the `Skill` tool.** When the matching
  Core plugin is installed, `coder` invokes `superpowers`'s
  TDD/debugging skills and `code-simplifier`, and `reviewer` invokes
  `code-review`/`pr-review-toolkit`, as a complementary pass — scaled to
  what the task/diff actually needs, not reflexively on every call, to
  keep `reviewer`'s single-pass principle intact. `architect`, `triage`,
  `quickfix` don't gain it — none of the Core plugins in scope map to
  their stage, and `quickfix` stays deliberately cheap.

## Rationale

Keeps ADR 0001's guarantee intact — commands are still the only
sequencing authority — while making the plugin layer real instead of
aspirational documentation. Gating installs behind `/setup-framework`
(never a hook, which can't ask the user anything) keeps that
machine-global side effect deliberate, like this framework's other
hard-to-reverse actions.

## Consequences

- `coder`/`reviewer` can invoke *any* globally available skill, not
  strictly the ones this ADR names — the `Skill` tool has no
  finer-grained scoping today. This relies on the instruction, not a
  hard boundary; revisit if it proves too loose.
- The Core/Optional list is a snapshot of one machine's install — a
  worked example to edit, like ADR 0001 itself.
- `plugin_gap_check.py`'s table only covers what the marketplace ships
  today (`csharp-lsp`, `typescript-lsp`) — needs a manual entry the day
  it ships another language LSP.
- `/setup-framework` changes global, machine-wide state, not just this
  repo — called out explicitly in the command itself.

## References

`docs/workflow/plugin-integrations.md`,
`.claude/skills/plugin-awareness/SKILL.md`,
`.claude/hooks/plugin_gap_check.py`,
`.claude/commands/setup-framework.md`,
`docs/decisions/0001-tooling-agents-commands-skills.md`
