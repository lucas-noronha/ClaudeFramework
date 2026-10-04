---
doc_type: workflow
scope: ai-first-development
status: active
last_updated: {{DATE}}
context_budget: ~700 tokens
---

# AI-first development flow

## Core principle

The bottleneck on a small team working with AI agents isn't writing
code — it's keeping context consistent across sessions with AI agents.
This docs repository exists so any agent loads **only** the context a
given task needs, never the whole project.

This document describes the conceptual flow. For the practical
step-by-step of "what do I type in chat", see
`feature-development-guide.md`. For the subagent/slash-command/skill
implementation that materializes this flow, see
framework ADR 0001 and the
`.claude/` folder at the repository root.

## Flow, from requirement to code

1. **Discovery conversation** with the stakeholder about a new feature
   (outside this docs repository — can be a call, free text, etc.).
2. **Formalize as a spec**, using
   `../product/requirements-template.md`, saved at
   `docs/product/specs/NNNN-short-name.md`. One spec per feature. `/spec`
   also auto-tags the spec's own `area` and lineage (`relates_to`) by
   reading the existing spec index — never something you declare by
   hand.
3. **Explicit validation**: the spec only moves from `draft` to
   `approved` after they review it. This is the human-in-the-loop
   checkpoint — don't skip it. If the feature gets dropped instead, the
   spec moves to `abandoned` — either way, only a human sets these two,
   never a hook.
4. **Implementation session with an AI agent**: the agent receives
   only
   - `CLAUDE.md` (always, it's the index)
   - `docs/constitution.md`, if your project has one — supreme,
     checked regardless of which feature is being built (see
     `governance-and-observability.md`)
   - the specific feature's spec
   - the architecture docs referenced by the spec (e.g. if it touches
     a specific cross-cutting concern, load that doc, and only that
     one)

   Don't load unreferenced ADRs, nor specs from other features.
5. **New architecture decision during implementation?** It becomes a
   new ADR before the code is accepted — never an implicit decision
   left only in the code.
6. **Reconciliation doesn't stop at merge.** `reviewer` records
   spec-vs-code fidelity per task while a spec is being implemented,
   and `/reconcile` lets you re-check an already-`implemented` spec
   against the codebase any time later — see
   `governance-and-observability.md` for both mechanisms and how they
   differ.

## Context-economy practices (context engineering)

- **One subject per file.** If you notice you're explaining two
  unrelated things in the same doc, it's time to split.
- **Reference, never copy.** A relative path to another doc, not its
  content.
- **ADRs are immutable.** Decision changed? A new ADR with
  `supersedes` pointing to the old one, which moves to
  `status: superseded`. This preserves history without forcing a
  reread of everything on every change.
- **Frontmatter on every file.** `status`, `scope`, `last_updated`,
  `context_budget` — lets you filter what to load before even opening
  the content.
- **`CLAUDE.md` never grows past one screen.** If it's growing, the new
  content probably belongs in a specific doc linked from it.
- **One project language, English structure.** Free text — specs,
  ADRs, architecture docs, the `.claude/` prompts and agent replies —
  is in the project's `{{LANGUAGE}}`; frontmatter keys, enumerated
  values, `## Tasks`/`## Reconciliation`, the reconciliation outcome
  phrases and `Approved`/`Returned` stay English so hooks and scripts
  keep working (framework ADR 0023). There is no second "stakeholder"
  language and no companion file: the stakeholder reads the spec
  itself. The language is chosen once at setup. English (the default) copies
  the framework's files as they are, at no cost; any other language has the
  model translate them at setup, and again on upgrade only for the files
  that changed upstream. A deterministic check keeps every marker above
  intact, and a file it cannot verify stays English.
