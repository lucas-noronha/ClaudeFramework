---
doc_type: spec
id: 0002
status: implemented
area: living-docs
relates_to: [0001]
context_budget: ~2450 tokens
---

# Living architecture docs — census, routing frontmatter and verified ground truth

## Feature name

Give the framework a strategy for keeping architecture docs true to the code. Today it only
keeps specs and ADRs honest.

## Business context

The framework tracks specs (index, status sync, per-task reconciliation) and ADRs
(immutability, index). It has no mechanism for architecture docs. Yet `cfw-coder` and
`cfw-reviewer` treat `architecture/module-structure.md` as ground truth, so a stale or wrong
doc is amplified into every review.

The first adopter already had what the framework lacks. It came as a hand-built system:
- a structural census (`census.sh`: handlers, endpoints, collections, config keys, enum
  members), with drift against the previous run and a map of which docs cite each item;
- probes, one per recorded defect, which go silent when the defect dies;
- a ledger with a watermark of the last documented commit and a "pending commit" table,
  filled by `/implement`;
- routing frontmatter (`resumo`, `naoResponde`) copied into indexes;
- the rule "describing is not prescribing", with explicit markers (Pitfall, Convention,
  Finding-that-needs-a-decision).

Evidence from 2026-09-30 that this matters:
- **Drafts were wrong.** Architecture drafts derived from docs or code still held wrong rules
  when an independent pass verified them against code: an inverted layer arrow, an invented
  "may not reference" column, a rule contradicting the ecosystem's own layering, and a false
  event-inheritance rule.
- **The sync found real stale prose.** Syncing three projects surfaced ~40 commits and many
  statements that code contradicts.
- **Two census flaws.** It reads the working tree, not the integration ref, so it reports
  false drift on feature branches. Its extractor misses config keys held in `const` fields.

What was adopted on the first machine (installed copy only, see 0001 NFR-01):
- `census.sh` moved into the machinery and is driven by the registry;
- `/cfw-update-docs`;
- `/cfw-implement` step 8, which writes the ledger's pending entry.

What was **not** adopted: `resumo`/`naoResponde` and "describing is not prescribing". They
survive only in the adopter's own docs and templates; no framework file, template or check
knows about them. The census extractor and `/cfw-update-docs` also still carry project
specifics (.NET layout, `Zamp.Framework`, Portuguese prose, the `develop` branch).

## Functional requirements

- FR-01: A **generic census engine** in the framework: census TSV, drift against the previous
  run, the doc-mentions map, probes, the ledger (watermark + pending + documented entries).
  Stack-specific extraction is a **pluggable extractor**, declared per project
  (`project-config.json` → `census.extractor`), with `dotnet-layered` as the first
  implementation.
- FR-02: The census reads identifiers and runs probes against the project's integration ref
  (`main_integration_branch`, see 0001 FR-06) via `git show`/`git grep <ref>`, never the
  working tree.
- FR-03: `/update-docs` (framework version, in the framework's canonical language):
  1. check freshness (stop and ask for a fetch, never fetch);
  2. run the census;
  3. resolve drift;
  4. document commits since the watermark, matching pending entries first;
  5. retire or rewrite findings with their probes;
  6. advance the watermark only when every commit is handled.
- FR-04: `/implement`, for census-enabled projects, updates the affected docs and writes a
  pending ledger entry (touched `src/`/`tests/` files, spec id, task, docs touched). It never
  touches the watermark.
- FR-05: Routing frontmatter becomes a framework convention. `resumo` (the question the doc
  answers) and `naoResponde` (when opening it is wasted) are recommended on every
  architecture doc. Project index tables copy `resumo` verbatim, and the doc wins on
  divergence. `frontmatter_check` nudges when an architecture doc lacks `resumo`. Key names
  are configurable, so a project can keep its own vocabulary.
- FR-06: "Describing is not prescribing" becomes a framework rule, in a workflow doc and in
  `cfw-coder`'s and `cfw-reviewer`'s instructions:
  - a documented deviation is never a pattern to copy;
  - docs mark Pitfall / Convention / Finding-that-needs-a-decision explicitly;
  - a new finding is born with a probe.
- FR-07: Architecture doc lifecycle `draft → active`:
  - a doc derived automatically (Domain 4 anamnesis or registration) starts `draft`, with a
    banner;
  - an **independent** verification pass checks every rule against code, and removes what it
    cannot back;
  - only then is the doc promoted to `active`;
  - `cfw-coder`/`cfw-reviewer` treat a `draft` rule as advisory (report the conflict) and an
    `active` rule as ground truth.
- FR-08: Rule probes. Each checkable dependency rule in `module-structure.md` may carry a
  probe, so the census reports a rule violation as drift. This closes the loop in both
  directions: code breaking a rule, and a rule the code no longer follows.
- FR-09: When `cfw-reviewer` finds that code consistently contradicts an `active` rule (the
  same deviation in several places, not one diff), it reports "the rule may be stale" as a
  separate finding. It does not block the diff or silently rewrite the rule.

## Non-functional requirements

- NFR-01: No inventory numbers in prose, anywhere the framework writes docs. Counts live in the
  census; prose points to it.
- NFR-02: The engine never writes to the code repo and uses read-only git only.
- NFR-03: Extractors are deterministic: consistently wrong beats inconsistently right. A diff
  is the product.

## Explicitly out of scope

- Extractors for stacks other than .NET layered (the plugin interface is in scope).
- Auto-writing prose. The engine detects and routes; an agent or human writes.

## Roles and permissions involved

Framework maintainer; `cfw-coder`, `cfw-reviewer` and the update-docs command as consumers.

## Related specs

- 0001-mode-c-hardening — extends: generalizes the census adoption that 0001 D5 patched for
  one machine.

## Acceptance criteria

- [x] AC-01: With the repo checked out on a feature branch one commit ahead, the census
      reports zero drift attributable to that branch (the store sync on 2026-09-30 had 4 of 9
      lines from the branch).
- [x] AC-02: A config key declared as a `const` and read via `GetValue(Const)` appears in the
      census.
- [x] AC-03: A project on a non-.NET stack can register with `census.extractor: none` and
      every other framework feature works.
- [x] AC-04: `/update-docs` on a project with N commits since the watermark ends with either
      the watermark at the ref's HEAD, or an explicit list of unhandled commits. Never both,
      never neither.
- [ ] AC-05: A `draft` `module-structure.md` rule that the diff violates yields an advisory
      finding, not a blocking one. The same rule `active` yields a blocking one.
- [x] AC-06: The framework's architecture and requirements templates carry `resumo` and
      `naoResponde` (or the configured names), and `frontmatter_check` nudges on a missing
      `resumo`.

## Impact on existing architecture

- New ADR: architecture-doc lifecycle and census engine. It complements ADR 0009/0012,
  which cover spec-vs-code; this covers docs-vs-code.
- Touches `cfw-coder`, `cfw-reviewer`, `/implement`, `frontmatter_check.py` and the
  architecture templates.

## Reconciliation

Recorded after the fact: this spec was implemented directly on 2026-10-03, without `/plan` and `/tasks`; the sections below document what was actually done, so the pipeline's own bookkeeping holds.

- [task 1] FR-01: matches spec
- [task 1] FR-02: matches spec
- [task 3] FR-03: matches spec — command steps are instructions; the ledger logic they rely on is tested
- [task 3] FR-04: matches spec
- [task 4] FR-05: matches spec — default keys resumo/naoResponde, configurable via routing_keys
- [task 5] FR-06: matches spec
- [task 5] FR-07: matches spec — the independent pass is reviewer's new doc-verification scope
- [task 1] FR-08: matches spec — probe paths are git glob pathspecs (`**` crosses folders)
- [task 5] FR-09: matches spec
- [task 5] NFR-01: matches spec — stated as a rule; not mechanically checked
- [task 1] NFR-02: matches spec — writes only under <docs root>/architecture/census/
- [task 1] NFR-03: matches spec
- [task 1] AC-01: matches spec — reproduced on a synthetic repo; the adopter's real .NET repos not run yet
- [task 2] AC-02: matches spec — synthetic C# source
- [task 1] AC-03: matches spec
- [task 1] AC-04: matches spec
- [task 5] AC-05: couldn't verify — agent instruction only; needs a real review over a draft doc
- [task 4] AC-06: matches spec

## Technical plan

Recorded after the fact: this spec was implemented directly on 2026-10-03, without `/plan` and `/tasks`; the sections below document what was actually done, so the pipeline's own bookkeeping holds.

**Tier:** structural. **ADR:** framework ADR 0019. Traceability per FR/AC: `CHANGELOG.md`.

## Tasks

- [x] 1. Census engine: integration-ref reads, drift, mentions, inline probes, ledger with watermark — Tests: FR-01, FR-02, FR-08, NFR-02, NFR-03, AC-01, AC-03, AC-04
- [x] 2. `dotnet-layered` extractor, constants resolved for config keys — Tests: AC-02
- [x] 3. `/update-docs` (sync and promote) and `/implement` step 8 — Tests: FR-03, FR-04
- [x] 4. Routing frontmatter in templates, `frontmatter_check` and `claude_md_index_check` nudges — Tests: FR-05, AC-06
- [x] 5. "Describing is not prescribing", `draft → active` lifecycle, stale-rule finding: workflow doc, `coder`, `reviewer` — Tests: FR-06, FR-07, FR-09, NFR-01, AC-05
