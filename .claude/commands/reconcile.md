---
description: On-demand spec-vs-code fidelity sweep for a spec that's already `implemented` — catches drift that happened after the fact, closing the gap framework ADR 0009 left open (the per-task reconciliation pass only covers a spec's own /implement sweep). Never gates anything; purely diagnostic.
argument-hint: path to an implemented spec (docs/product/specs/NNNN-name.md)
---

Before anything else in this command: apply the `project-registration`
skill's check — it resolves where this session's `docs/` and `CLAUDE.md`
actually live (registering the project first if it isn't yet), and in
the common case costs one check and changes nothing.

Resolve the spec first (framework ADR 0024) — $ARGUMENTS may be a file, a
folder or `NNNN`, in either layout:
`python "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/_spec_layout.py" resolve $ARGUMENTS`
(pass an absolute path, a folder name or `NNNN` — a relative path resolves
against the current directory).
Its JSON gives the status file and the **reconciliation target**
(`reconciliation.md` in a spec folder, the single file's "## Reconciliation"
section otherwise); that target is where the sweep is read and written.

Prerequisite: the spec at $ARGUMENTS needs `status: implemented`. If
it's `draft`/`approved`, there's nothing shipped yet to reconcile —
point at `/plan`+`/implement` instead. If it's `abandoned`, stop; there
is nothing to check.

Language: write free text in {{LANGUAGE}}; frontmatter keys, enumerated values, `## Tasks`/`## Reconciliation`, the reconciliation outcome phrases and `Approved`/`Returned` stay English.

Unlike `/review`, this never blocks a merge and doesn't need the
build/test gate to have just run — it's a standalone audit, runnable
any time against a spec that's been sitting in `implemented` for a
while, to answer "does the code still actually do what this spec says,
or has something drifted since." See
framework ADR 0012 for why this is
a fresh check against current code state, not a diff (this framework
doesn't persist a file manifest per task, so there's nothing reliable
to diff against after the fact).

1. Read the spec's Functional/Non-functional requirements and
   Acceptance Criteria, its "Impact on existing architecture" section,
   its `area` frontmatter tag, and the existing reconciliation target
   (the per-task entries from `/implement`, plus any prior
   `### Sweep` block from an earlier `/reconcile` run).
2. Delegate to `reviewer`, explicitly telling it: **this is a sweep,
   not a diff or a per-task review** — no file list, no build/test gate
   prerequisite. Hand it the spec path and point it at where this
   spec's capability actually lives today (its own architecture
   pointers plus `docs/architecture/`), so it can judge current code
   state against each `FR-NN`/`AC-NN` the same way it already judges
   Definition of Done for `/review`, just without a diff to anchor on.
3. `reviewer` appends one new `### Sweep — <today's date, YYYY-MM-DD>` block to the
   reconciliation target, one line per `FR-NN`/`AC-NN`:
   `still matches`, `now diverged — <reason>`, or `couldn't verify —
   <why>` if the relevant code isn't findable from the spec's own
   pointers. Never edits or removes an earlier sweep's lines — sweeps
   accumulate as a history, not a single mutable verdict.
4. Report the sweep's findings directly to the user. This command
   never auto-fixes anything: a real divergence is a decision for the
   user — accept the drift (update the spec to match reality, a
   `/spec`-level edit, not this command's job) or file it as a bug/new
   task against the spec's own area.

Read-only against the codebase, write-only against the spec's own
reconciliation target — this command implements nothing and calls
neither `coder` nor `quickfix`.
