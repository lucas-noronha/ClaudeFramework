---
doc_type: adr
id: 0008
status: proposed
date: {{DATE}}
supersedes: null
superseded_by: null
context_budget: ~800 tokens
---

# ADR 0008 — Specs auto-tag their own area and lineage, never hand-declared

Like ADR 0001–0007, this documents a decision about *this framework's
own* tooling (kept as a worked example).

## Context

A spec had no relationship to any other spec — no way to see that a
new one extends or modifies a capability an earlier spec already
shaped in the same functional area. OpenSpec covers this with a
brownfield-first delta model (each change documents ADDED/MODIFIED/
REMOVED against a living per-capability spec). Raised directly by
comparing this framework against OpenSpec for large-scale maturity;
scoped down deliberately (see Options below) to fit this framework's
existing one-file-per-feature spec shape instead of adopting OpenSpec's
own file layout wholesale.

## Options considered

- **Manual `relates_to` field, human-declared at `/spec` time.**
  Rejected on direct instruction — this is exactly the kind of
  "remember to tag it yourself" duplication this framework avoids
  elsewhere (`skill_index.py`'s `applies_to` tagging exists so a skill
  declares its own relevance instead of every agent file listing every
  skill). The spec should identify its own group automatically.
- **Full OpenSpec-style change-folder + archive-into-living-spec
  model.** Rejected — bigger structural change than the actual gap
  needs: it would stop specs being one file per feature, breaking
  "each spec needs to be readable in isolation" (`requirements-template.md`).
  Heavier than this project's real requirement.
- **Frontmatter `area` (auto-inferred by `/spec` against the existing
  spec index) + `relates_to` (auto-populated ids) + a body "## Related
  specs" section; the index hook groups/sorts by area (chosen).**

## Decision

`/spec` reads `docs/product/specs/README.md` before drafting, infers
`area` (reusing an existing tag when the new spec clearly shares that
functional domain, proposing a new short kebab-case one otherwise),
and populates `relates_to` (frontmatter ids) plus "## Related specs"
(body, one line per related spec with the relationship — "extends",
"modifies FR-03", "no direct overlap, same area only"). Never asks the
human to assign either. `spec_index.py` parses `area`/`relates_to` and
sorts/columns the index by area so lineage is visible without opening
every file.

## Rationale

Mirrors the ADR `supersedes`/`superseded_by` convention already
established (design principle 3) instead of inventing a new
relationship primitive. Keeps specs one-file-per-feature. The
inference cost is paid once, by the same LLM pass that already drafts
FR/NFR from a raw description — no new pipeline stage.

## Consequences

- `/spec` now reads the spec index before drafting — one extra, cheap
  read.
- Area assignment is a per-run judgment call, not a controlled
  vocabulary — it can drift (two near-duplicate area tags for what's
  really one domain) with no automatic merge/dedup mechanism. A human
  noticing this fixes it by hand, editing both specs' frontmatter;
  not solved here.
- This change also fixes a latent bug found while making it: three
  existing hooks (`spec_status_sync.py`, `spec_index.py`, and the
  stakeholder-validation-sync example hook in `settings.example.json`)
  already assumed every spec has a YAML frontmatter block with
  `status:` in it, but `requirements-template.md` never actually
  produced one — no spec's status could ever have auto-flipped to
  `implemented` before this. Same fix (a real frontmatter block, see
  `requirements-template.md`) makes both this feature and that
  previously-dormant one actually work.

## References

`docs/product/requirements-template.md`, `.claude/commands/spec.md`,
`.claude/hooks/spec_index.py`,
`docs/decisions/0001-tooling-agents-commands-skills.md`
