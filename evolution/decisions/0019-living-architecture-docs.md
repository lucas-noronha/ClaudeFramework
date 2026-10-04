---
doc_type: adr
id: 0019
status: accepted
date: 2026-10-03
supersedes: null
superseded_by: null
context_budget: ~1200 tokens
---

# ADR 0019 — Architecture docs get a lifecycle, routing frontmatter and a census engine

Like ADR 0001–0018, this documents a decision about *this framework's
own* tooling. It complements ADR 0009/0012, which keep **specs** honest
against code; this one does the same for **architecture docs**.

## Context

`coder` and `reviewer` treat `architecture/module-structure.md` as
ground truth, yet nothing kept it true. On 2026-09-30 (spec 0002), drafts
derived from code and docs still held an inverted layer arrow, an
invented "may not reference" column, a rule contradicting the
ecosystem's own layering and a false event-inheritance rule. Syncing
three projects surfaced about 40 commits and many statements the code
contradicted. The first adopter had built the missing pieces by hand: a
census script, probes, a ledger with a watermark, routing frontmatter
and a "describing is not prescribing" rule. All of them were tied to its
own stack, language and branch, and the census had two flaws: it read
the working tree, so a feature branch looked like drift, and it missed
config keys held in `const` fields.

## Options considered

- **Leave it to review discipline.** Rejected: the evidence above is what
  review discipline produced.
- **Adopt the adopter's scripts as they are.** Rejected: .NET layout,
  Portuguese prose and a hardcoded `develop` branch, and both census
  flaws.
- **Generate architecture docs from code.** Rejected: rules and intent
  can't be extracted. Auto-written prose would be confidently wrong in
  exactly the way the drafts were.
- **A generic engine that detects and routes, with pluggable stack
  extractors; agents and humans write the prose (chosen).**

## Decision

- **Census engine** (`.claude/scripts/census.py`, stdlib). Its inventory
  comes from the project's **integration ref** (`main_integration_branch`,
  preferring `origin/<branch>`), read via `ls-tree`/`cat-file`/`grep`,
  never the working tree. It keeps drift against the previous run, a
  map of which docs cite each item, inline probes and a ledger. It is
  read-only on git, never fetches, and writes only under
  `<docs root>/architecture/census/`.
- **Pluggable extractors** (`census_extractors/<name>.py`), chosen per
  project by `census.extractor`. `dotnet-layered` ships first (handlers,
  endpoints, collections, config keys resolved through constants, enum
  members). `none` keeps everything else working on any stack.
  Extractors must be deterministic.
- **Probes** are inline comments next to the rule or finding they back.
  A rule probe that matches is drift: the code breaks the rule, or the
  rule is stale. A finding probe that goes silent means the finding is
  retired.
- **Ledger**: a watermark, pending entries written by `/implement` and
  `/quick` (never touching the watermark), and documented commits.
  `ledger advance` moves the watermark to the ref's HEAD only when every
  commit since is handled; otherwise it lists the unhandled ones.
- **`/update-docs`**: freshness (ask, never fetch) → census → drift →
  commits since the watermark (pending entries first) → findings →
  watermark. `/update-docs promote` runs the lifecycle below.
- **Lifecycle `draft → active`.** An automatically derived doc starts
  `draft`, with a banner. An **independent** `reviewer` pass (the new
  doc-verification scope) checks each rule against code. What it can't
  back is removed, and only then is the doc `active`. `coder`/`reviewer`
  treat draft rules as advisory and active rules as binding.
  `reviewer` reports "rule may be stale" separately when the code
  consistently contradicts an active rule, without blocking or rewriting.
- **Routing frontmatter**: `resumo` (the question a doc answers) and
  `naoResponde` (when opening it is wasted) on architecture docs and in
  the templates. Index tables copy `resumo` verbatim, and the doc wins.
  `frontmatter_check.py` and `claude_md_index_check.py` nudge. The key
  names are configurable (`routing_keys`).
- **"Describing is not prescribing"** becomes a framework rule, in
  `docs/workflow/living-architecture-docs.md` and in `coder`/`reviewer`.
  It covers the Pitfall / Convention / Finding markers and no inventory
  numbers in prose.

## Rationale

The engine does the part that is mechanical and testable: what exists at
the ref, what changed, what each doc cites, and which commits are
undocumented. It routes the part that isn't (prose, decisions) to an
agent or a human. Reading the ref instead of the working tree fixes the
false-drift flaw by construction. Making `draft` advisory turns the
proven failure mode, a confidently wrong draft, into reported conflicts
instead of enforced errors.

## Consequences

- The default routing keys are the first adopter's Portuguese names, as
  spec 0002 specified. A project wanting English keys sets
  `routing_keys` in its config.
- Mode A needs a machine-readable config for the census. ADR 0020
  introduces the optional `.claude/project-config.json`.
- Census artifacts live in the docs tree. In mode A that is inside the
  code repo's `docs/`, which is the project's own documentation, so
  NFR-02's "never writes to the code repo" means never outside the docs
  root.
- Regex extraction is wrong in known, stable ways (no `MapGroup` prefix,
  no compiler-level resolution). The census's value is its diff, not its
  completeness.

## References

`evolution/product/specs/0002-living-architecture-docs.md`,
`docs/workflow/living-architecture-docs.md`,
`evolution/decisions/0006-architecture-anamnesis.md`,
`evolution/decisions/0009-per-task-spec-reconciliation.md`,
`evolution/decisions/0012-on-demand-reconciliation-sweep.md`,
`.claude/scripts/census.py`, `.claude/commands/update-docs.md`
