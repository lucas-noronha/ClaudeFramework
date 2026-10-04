---
doc_type: adr
id: 0021
status: proposed
date: 2026-10-03
supersedes: null
superseded_by: null
context_budget: ~800 tokens
---

# ADR 0021 — The framework's own specs and ADRs live in `evolution/`, outside the shipped skeleton

Like ADR 0001–0020, this documents a decision about *this framework's
own* tooling.

## Context

The framework kept its own ADRs (0001–0020) in `docs/decisions/` and its
own specs in `docs/product/specs/` — the very folders it ships to
projects as the place for *their* ADRs and specs. Consequences:

- Mode A says "copy `docs/` into your repo", so every adopting project
  received twenty framework ADRs and three framework specs as if they
  were its own. A project's first ADR then collided with framework ADR
  0001 in numbering, in `decision_index.py`'s README, and in
  `spec_number_guard.py`.
- Shipped instructions cited "ADR 0004" and `docs/decisions/0004-...`.
  Inside a project that names the project's own ADR 0004 — a different
  document.
- `spec_index.py` linked `../../decisions/0008-...` from a project's spec
  index: in a mode A project, potentially the project's own, unrelated
  ADR 0008.
- The user-level installer (ADR 0017) copied the framework's ADRs into
  the shared root as "reference ADRs".

## Options considered

- **Keep them in `docs/`, ship them as read-only reference under a
  separate path** (e.g. `docs/framework/decisions/`). Rejected: projects
  still receive the framework's development history, and every upgrade
  churns it.
- **Move the shipped skeleton into its own folder** (`template/`).
  Rejected: every path in every shipped file, the README's adoption steps
  and both settings templates would move, for the same boundary.
- **Move the framework's own specs and ADRs to a top-level `evolution/`,
  and name them in shipped files without a path (chosen).**

## Decision

- `evolution/decisions/` holds the framework's ADRs (and their index);
  `evolution/product/specs/` its specs. `docs/decisions/` keeps only
  `0000-adr-template.md`; `docs/product/specs/` ships empty.
- The skeleton is exactly `.claude/`, `docs/`, `CLAUDE.md.template`,
  `.mcp.json.example` and `.gitignore.framework-additions`. Mode A copies
  it; the installer installs only from it and no longer installs
  framework ADRs — this reverses ADR 0017's "reference ADRs in the
  namespace" (spec 0001 FR-01).
- Shipped files cite **"framework ADR NNNN"** / **"framework spec NNNN"**,
  never a bare "ADR NNNN" or a path into `evolution/`.
  `spec_index.py` names framework ADR 0008 instead of linking it.
- `evolution/` has a project subtree's shape, with its own
  `project-config.json` (gate = the framework's test suite), so the
  pipeline can run on the framework itself through a routing entry
  (`register_project.py --subtree`).
- `tests/test_skeleton_boundary.py` enforces the boundary: nothing from
  `evolution/` in `docs/` or in an install, and no ambiguous reference in
  a shipped file.

## Rationale

Ownership again, as in ADR 0018: a document belongs where its owner
works. The framework's history is owned by this repository; a project's
`docs/` is owned by the project. Naming instead of linking costs agents
the ability to open a framework ADR from inside a project, but they
never needed it to operate — every rule they apply is stated in the
shipped command, agent or skill itself; the ADR is only the why.

## Consequences

- Accepted ADRs keep their historical `docs/decisions/...` paths in their
  bodies (immutability); `evolution/README.md` says how to read them.
- No project had adopted mode A when this landed, so no project carries
  a copy of the framework's ADRs and nothing needs migrating.
- Mode B AI-repos carry `evolution/` (they are clones of this
  repository) but outside `docs/`, so project subtrees never meet it.

## References

`evolution/README.md`, `evolution/decisions/0017-user-level-install-mechanics.md`,
`tests/test_skeleton_boundary.py`, `.claude/scripts/install_user_level.py`,
`.claude/hooks/spec_index.py`
