---
doc_type: adr
id: 0001
status: accepted
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~400 tokens
---

# ADR 0001 — Split between subagents, slash commands, skills, and hooks

This ADR documents a decision made about *this framework itself*
(kept as a worked example of the format) — not a decision about
{{PROJECT_NAME}}. Keep it as-is if it still describes how you're using
`.claude/`; write a new ADR that supersedes it if your project departs
from this split.

## Context

An AI-first development workflow (spec → plan → tasks → implementation
→ review) needs a deterministic sequencing mechanism, and reusable
knowledge that applies at any stage. Conflating the two under a single
primitive (e.g. using Skills for sequencing too) creates a real risk:
automatic triggering by text similarity can route the agent to the
wrong stage or stack context from two stages at once.

## Decision

- **Subagents** (`.claude/agents/`) — the pipeline roles (`triage`,
  `architect`, `researcher`, `coder`, `quickfix`, `reviewer`), each
  with a fixed model in its frontmatter and isolated context.
- **Slash commands** (`.claude/commands/`) — the pipeline's
  deterministic entry points (`/spec`, `/plan`, `/tasks`, `/implement`,
  `/review`, `/adr`, `/worktree`), each delegating to the right
  subagent.
- **Skills** (`.claude/skills/`) — reusable knowledge that applies at
  any stage, regardless of sequence. This framework ships only the two
  the framework's own process needs (`adr-writing`, `skill-authoring`);
  every project-specific one (e.g. a data-isolation invariant
  checklist, a module/feature scaffolding checklist, a sensitive-data
  handling rule) is a property of that project's actual architecture
  and domain, added there, not shipped as a default.
- **Hooks** (`.claude/settings.json`) — the deterministic gate
  (build/lint/tests) and structural guards (ADR immutability, spec
  numbering) running with zero token cost, before any agent-based
  review.

## Rationale

Aligned with the pattern observed in GitHub Spec Kit, which solves the
same problem with deterministic slash commands (`/speckit.specify`,
`/speckit.plan`, `/speckit.tasks`, `/speckit.implement`) instead of
automatic triggering — a pipeline's sequence shouldn't depend on
probabilistic description matching.

## Consequences

- Every new fixed process stage becomes a slash command, never a
  Skill.
- Every new skill must justify why it applies "at any stage" — if it
  only makes sense at one specific stage, it belongs inside the body
  of that slash command or subagent, not in its own Skill. See
  `.claude/skills/skill-authoring/SKILL.md` for the explicit test.

## References

`docs/workflow/ai-first-development.md`,
`docs/workflow/feature-development-guide.md`
