---
doc_type: template
scope: product-requirements
status: active
last_updated: {{DATE}}
context_budget: ~410 tokens
---

# Template — requirement intake ({{LANGUAGE}})

Usage: for every new feature, before it becomes an implementation task,
create the folder `docs/product/specs/NNNN-short-name/` (framework
ADR 0024) and write the body below into its `spec.md`. One feature = one
spec folder. Don't accumulate multiple features in the same folder —
each spec needs to be readable in isolation by an agent without loading
the others.

Free text is written in {{LANGUAGE}}; frontmatter keys, enumerated
values, the file names `spec.md`, `plan.md`, `tasks.md` and
`reconciliation.md`, `## Tasks`/`## Reconciliation`, the reconciliation
outcome phrases and `Approved`/`Returned` stay English (framework ADR
0023, ADR 0024). The stakeholder validates `spec.md` alone.

## Folder layout

One file per pipeline artifact, each with a single owner. No per-folder
index or `README.md`; each file's `summary` and the specs index cover
that role.

| File | Created by | Holds |
| --- | --- | --- |
| `spec.md` | `/spec` | Frontmatter and the requirement sections below, "Feature name" to "Impact on existing architecture". Its `status` and `tier` are the only lines that change after approval. |
| `plan.md` | `/plan` (standard and structural; a trivial spec has none) | Approach, ADR reference, scope check, Definition of Done, Test plan. |
| `tasks.md` | `/tasks` | `## Tasks`, one checkbox per task. |
| `reconciliation.md` | `/spec`, empty | `## Reconciliation`, written by `reviewer` and `/reconcile`. |

A pipeline step may add an extra file the spec needs (for example
`research.md`), directly in the folder, with `doc_type: spec-note`. It
never holds requirement, plan, task or reconciliation content.

A **lite spec** (`/quick`) is a folder `NNNN-quick-<short-name>/` with a
single `spec.md` (`lite: true`, `tier: standard`) holding context, FRs,
ACs, an inline `## Tasks` and an empty `## Reconciliation`. A legacy
single-file spec `NNNN-short-name.md` keeps working in its own layout.

Every file other than `spec.md` carries this minimal frontmatter and
never a `status`:

```yaml
---
doc_type: spec-plan   # or spec-tasks | spec-reconciliation | spec-note
spec: NNNN
summary: <what this file answers>
context_budget: ~300 tokens   # estimate from the file's real size (chars/4), not a fixed value
---
```

Skeletons of the other three files (the title and headings are fixed):

`plan.md`:

```markdown
# Technical plan

**ADR:** <reference, if any>

## Approach
## Scope check
## Definition of Done
- [ ] <numbered against the spec's FR/AC>
## Test plan
- S01: <scenario> — FR-01, AC-01
```

`tasks.md` (the sub-bullets are plain, never checkboxes, and carry the
task's own Test plan lines and, for a structural spec, its approach
excerpt):

```markdown
## Tasks

- [ ] 1. <task> — Depends on: none — Tests: S01
  - S01: <full text of that Test plan line>
  - Approach: <excerpt of plan.md that applies, structural specs only>
```

`reconciliation.md`:

```markdown
## Reconciliation
```

`spec.md`'s frontmatter also gains `tier: trivial | standard | structural`,
set by `/plan`.

---

**Every generated spec starts with its own frontmatter block** below —
not copied from this template file's own frontmatter above, a new one
specific to the spec being created:

```yaml
---
doc_type: spec
id: NNNN
status: draft
area: <short-kebab-case tag for the functional domain/capability this
  spec belongs to — set automatically by /spec, never asked of the
  human; see framework ADR 0008>
relates_to: []
summary: <the one question this spec answers — index tables copy it verbatim>
notFor: <when opening this spec is wasted — optional>
context_budget: ~350 tokens
---
```

`status` lifecycle: `draft` (written by `/spec`, not yet reviewed by
the stakeholder) → `approved` (stakeholder signed off; set by `/plan`,
which asks whether to approve a `draft` spec before planning it — or
`/quick` for a lite spec) → `implemented` (set
automatically by `spec_status_sync.py` once every box in "## Tasks" is
checked — never set this by hand) → `abandoned` (dropped before or
during implementation, won't be pursued — set by hand at any point; a
spec in this status is excluded from `session_brief.py`'s "pending"
list).

## Feature name

## Business context
<!-- Why this matters to the {{PROJECT_NAME}} user. Written by, or
validated with, the domain-expert stakeholder — not a technical
assumption. -->

## Functional requirements
<!-- What the system must do, in business language, not technical.
Number them (FR-01, FR-02...) for cross-referencing in code tasks. -->

- FR-01:
- FR-02:

## Non-functional requirements
<!-- Performance, security, applicable regulatory compliance (e.g.
data retention, privacy law), availability. Number them (NFR-01,
NFR-02...). -->

- NFR-01:

## Explicitly out of scope
<!-- What this feature does NOT cover, to prevent scope creep during
implementation by an AI agent. -->

## Roles and permissions involved
<!-- Which roles (see your project's auth architecture doc, if any)
interact with this feature, and what each can do. -->

## Related specs
<!-- Set automatically by /spec (framework ADR 0008)
— every other spec sharing this spec's `area`, with its relationship to
this one. Not a human-declared field. Empty means either this is that
area's first spec, or /spec found no real relationship to declare —
never invent an overlap that isn't there just to fill this in.
Format: `- NNNN-short-name — relationship` (e.g. "extends", "modifies
FR-03", "no direct overlap, same area only"). -->

## Acceptance criteria
<!-- Testable, objective. What must be true to consider it done. Number
them (AC-01, AC-02...) — /plan's Definition of Done and Test plan
reference these numbers directly, so an unnumbered criterion can't be
traced from a test back to the requirement it exists for. -->

- [ ] AC-01:
- [ ] AC-02:

## Impact on existing architecture
<!-- Fill only if there's an impact. Reference the affected ADR or
architecture doc, don't re-explain it here. -->

## Reconciliation
<!-- Lives in `reconciliation.md` for a folder spec (not in `spec.md`); in
the body of a lite or legacy single-file spec only.
Populated automatically and incrementally by `reviewer` during
`/implement`'s per-task pass
(framework ADR 0009) — one line per
FR/AC a task claimed via its `Tests:` field, noting whether what was
actually built matches this spec's own text. Never write here by hand.
Empty once every "## Tasks" box is checked is a gap `/review`'s final
pass treats as a finding, not a clean bill of health. -->
