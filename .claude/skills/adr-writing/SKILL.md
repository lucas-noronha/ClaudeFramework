---
name: adr-writing
description: Applies the project's standard ADR format (frontmatter, context, options, decision, consequences) whenever an architecture decision is being recorded or reviewed.
applies_to: [architect]
---

Fixed format, following `docs/decisions/0000-adr-template.md` and the
existing ADRs in `docs/decisions/`:

```markdown
---
doc_type: adr
id: 000N
status: proposed | accepted | superseded
date: YYYY-MM-DD
supersedes: null | 000X
superseded_by: null | 000Y
---

# ADR 000N — Short decision title

## Context
## Options considered
## Decision
## Rationale
## Consequences
## References
```

Rules:
- Sequential numbering, never reuse a removed ADR's number.
- An ADR is never edited after `accepted` — a changed decision becomes
  a new ADR with `supersedes` pointing to the old one, which moves to
  `status: superseded`. (Enforced by the `adr_immutability_guard` hook
  — don't try to work around it; write the new ADR instead.)
- "Consequences" includes the accepted trade-off, not just the
  benefit — if a decision has zero cost, you're probably missing what
  you're giving up.
- References use relative paths to other docs, never duplicate their
  content.
