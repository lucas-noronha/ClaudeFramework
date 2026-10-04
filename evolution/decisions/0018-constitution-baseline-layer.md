---
doc_type: adr
id: 0018
status: accepted
date: 2026-10-03
supersedes: null
superseded_by: null
context_budget: ~750 tokens
---

# ADR 0018 — The constitution gains a framework-owned baseline layer

Like ADR 0001–0017, this documents a decision about *this framework's
own* tooling. **Extends ADR 0015's layering** (supreme shared file +
optional project file) with a third layer above both.

## Context

`docs/constitution.md` shipped as one file holding two different things:
the framework's own baseline principles (I–V: secrets, logging, input
validation, least privilege, dependency vetting) and a slot for the
adopter's own (VI onward). On the first mode C adoption the organization
wrote VI–XI into that same file (spec 0001, D13). From then on a
framework upgrade had only bad options: overwrite the file and lose the
organization's amendments, or never touch it and never update the
baseline.

## Options considered

- **Merge on upgrade** (three-way merge of the shipped file into the
  amended one). Rejected: a text merge of normative prose has no safe
  automatic resolution, and a silent wrong merge of a constitution is
  worse than none.
- **Mark the baseline region inside the one file** (begin/end markers
  the installer replaces). Rejected: fragile against hand edits, and the
  amendment hook couldn't tell a baseline edit from an organization one.
- **Split the file: a framework-owned baseline beside the organization
  layer (chosen).**

## Decision

- `docs/constitution-baseline.md` holds Principles I–V. It ships with
  the framework, is versioned with it, and **an upgrade replaces it
  wholesale**. It is never hand-edited in an adopted project.
- `docs/constitution.md` is the **organization layer** (in a shared
  root, modes B/C) or the project's own layer (mode A). It numbers its
  principles from VI, extends the baseline, and may never weaken it. It
  keeps its Governance section, and **an upgrade never touches it**.
- `<project-subtree>/constitution.md` stays as ADR 0015 defined it:
  optional, project-owned, additive.
- Every stage that checks the constitution reads all existing layers,
  top-down. The supreme pair (baseline + organization) is the
  non-negotiable floor.
- `constitution_amendment_check.py` nudges on any edit to the baseline
  ("framework-owned, replaced on upgrade — amend `constitution.md`").
  The organization and project layers keep the unversioned-drift nudge.
- The user-level installer replaces the baseline and creates
  `constitution.md` only when absent (spec 0001 AC-06).

## Rationale

Ownership decides upgradeability. One file with two owners can't be
upgraded safely; two files with one owner each can be upgraded with a
copy. The split costs readers one extra file, and they were already
reading more than one in modes B/C.

## Consequences

- A project adopted before this ADR has I–V inside its own
  `constitution.md`. It keeps working: agents read whatever layers exist,
  and the duplicate text is harmless. To adopt the split, delete I–V
  from `constitution.md` once `constitution-baseline.md` is in place.
  That's a MAJOR amendment under its Governance section.
- Promoting an organization principle into the baseline is a change to
  this repository, never an edit to an installed baseline.
- Mode A gains a second file. ADR 0015's "mode A is unchanged, one file"
  no longer holds; layering by owner now applies in every mode.

## References

`evolution/product/specs/0001-mode-c-hardening.md` (FR-10, AC-06),
`evolution/decisions/0007-constitution-document.md`,
`evolution/decisions/0015-unified-docs-tree-and-layered-constitution.md`,
`docs/constitution-baseline.md`, `docs/constitution.md`,
`.claude/hooks/constitution_amendment_check.py`
