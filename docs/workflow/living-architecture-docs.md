---
doc_type: workflow
scope: living-architecture-docs
status: active
last_updated: {{DATE}}
resumo: How do architecture docs stay true to the code, and what may an agent take from them?
naoResponde: What any particular project's architecture is — read that project's own architecture docs.
related: [../architecture/module-structure.md.template]
context_budget: ~1100 tokens
---

# Living architecture docs

Specs and ADRs are kept honest by hooks and reconciliation. Architecture
docs need the same, because `coder` and `reviewer` treat
`architecture/module-structure.md` as ground truth: a stale or wrong doc
gets amplified into every review. Full rationale:
framework ADR 0019.

## 1. Describing is not prescribing

An architecture doc describes the code as it is, plus the rules the team
actually holds it to. It is not a wish list, and an observed deviation
in it is not a pattern to copy.

- **A documented deviation is never a pattern to copy.** That the code
  does X somewhere doesn't make X the way to write new code.
- **Mark every non-rule explicitly**, as a blockquote, so no reader
  mistakes it for one:
  - `> **Pitfall:** ...` — a trap in the existing code; don't repeat it.
  - `> **Convention:** ...` — how things are done here, followed by
    choice, not enforced by structure.
  - `> **Finding (needs a decision):** ...` — the code contradicts a rule
    or itself, and a human has to decide which side wins.
- **A new finding is born with a probe** (section 4), so it can't
  outlive the defect it describes.
- **No inventory numbers in prose** ("the 14 handlers", "all 6
  collections"). They are stale the day after they're written. Counts
  live in the census; prose points to it.

## 2. Routing frontmatter

Every architecture doc carries two routing keys, so a reader (human or
agent) can decide whether to open it from the index alone:

```yaml
resumo: The one question this doc answers.
naoResponde: When opening it is wasted (optional).
```

Index tables (`CLAUDE.md`'s, a project's own) copy `resumo` verbatim,
and on divergence the doc wins. `claude_md_index_check.py` nudges when
a row drifts, and `frontmatter_check.py` nudges when an architecture doc
has no `resumo`. The key names are configurable per project through
`routing_keys` in its config, e.g.
`"routing_keys": {"summary": "answers", "not_for": "not_for"}`.

## 3. Lifecycle: `draft` → `active`

- A doc **derived automatically** — Domain 4 anamnesis, a registration,
  a migration — starts `status: draft`, with the "detected
  automatically" banner. Drafts verified against code on 2026-09-30
  still held an inverted layer arrow, an invented rule and a false
  inheritance claim, so a draft is never trusted on sight.
- `/update-docs promote <doc>` runs an **independent** verification:
  `reviewer`, in a fresh context, checks every rule against the code and
  cites it. Rules it can't back are removed. Only then does the doc
  become `active`.
- `coder` and `reviewer` read a `draft` rule as **advisory** (report a
  conflict, don't block), and an `active` rule as **ground truth** (a
  violation returns the diff).
- When `reviewer` sees the code consistently contradict an `active` rule
  — the same deviation in several places, not one diff — it reports
  "the rule may be stale" as a separate finding. It doesn't block the
  diff and doesn't rewrite the rule.

## 4. The census, probes and the ledger

Opt in per project (`census` in its config; see
`../../.claude/scripts/census.py` for every key). Then:

- **Census** — an inventory of structural items (handlers, endpoints,
  collections, config keys, enum members, whatever the project's
  extractor finds), read from the **integration branch**, never the
  working tree, with drift against the previous run and a map of which
  docs cite each item. The extractor is pluggable (`dotnet-layered`, or
  `none` for every other stack: everything else still works).
- **Probes** — one inline comment per finding or checkable rule, beside
  the text it backs:

  ```html
  <!-- census-probe id=R-02 kind=rule paths="src/*.Domain/**/*.cs" pattern="using [A-Za-z.]*\.Infrastructure" -->
  ```

  A rule probe that matches means drift (the code breaks the rule, or
  the rule is stale). A finding probe that stops matching means the
  defect is gone, so retire the finding.
- **Ledger** — a watermark (the last commit the docs are known to
  describe), *pending* entries that `/implement` and `/quick` write as
  they change code, and the commits `/update-docs` has documented since.
  The watermark only moves when every commit up to the ref's HEAD is
  handled.

## 5. Who does what

| When | Who | What |
|---|---|---|
| A task changes code in a census project | `/implement`, `/quick` | update the docs that task makes untrue; write a pending ledger entry; never the watermark |
| Periodically, or before a release | `/update-docs` | freshness → census → drift → commits → findings → watermark |
| A drafted doc is ready to trust | `/update-docs promote <doc>` | independent verification, then `active` |
| Every review | `reviewer` | draft = advisory, active = blocking; flag rules that look stale |

The engine detects and routes. Prose is always written by an agent or a
human.
