---
description: Brings a census-enabled project's architecture docs back in line with its integration branch — checks freshness, runs the census, resolves drift, documents every commit since the watermark (matching /implement's pending entries first), retires or rewrites findings whose probes went silent, and advances the watermark only once every commit is handled. Also promotes a draft architecture doc to active after an independent verification pass.
argument-hint: (nothing) to sync, or "promote <architecture doc path>"
---

Before anything else in this command: apply the `project-registration`
skill's check — it resolves where this session's `docs/` and `CLAUDE.md`
actually live (registering the project first if it isn't yet), and in
the common case costs one check and changes nothing.

Rationale and conventions: framework ADR 0019
and `docs/workflow/living-architecture-docs.md` (describing is not
prescribing, the markers, no inventory numbers in prose). Every census
call below is `python "${CLAUDE_PROJECT_DIR:-.}/.claude/scripts/census.py" <command>`;
it prints JSON, reads code only at the integration ref, and writes only
under `<project docs>/architecture/census/`.

Language: write free text in {{LANGUAGE}}; frontmatter keys, enumerated values, `## Tasks`/`## Reconciliation`, the reconciliation outcome phrases and `Approved`/`Returned` stay English.

If the project's config has no `census` block, or `census.enabled` is
false, say so and stop: this command needs a project that opted in. Any
extractor works, `none` included.

## Sync (no argument)

1. **Freshness.** Run `census.py status`. If `fresh` is false (no fetch,
   or older than `census.fetch_max_age_hours`, default 24), **stop and
   ask the user to run `git fetch`**. Never fetch yourself. If the ledger
   doesn't exist yet, run `census.py ledger init` once (watermark = the
   ref's HEAD) and say that history before it isn't covered.
2. **Census.** Run `census.py run`. On the very first run (`baseline:
   false`) just persist it with `census.py run --write` and go to step 4.
3. **Resolve drift**, item by item, then persist with
   `census.py run --write`:
   - `removed` items: every doc in `still_cited_by` describes something
     that no longer exists. Rewrite or delete that prose.
   - `added` items: decide whether a doc should describe them. The
     census routes; it never writes prose, and many items need none.
   - A `rule` probe in state `violated`: the code breaks a documented
     rule, or the rule is stale. Don't pick one silently — report it,
     with the probe's `sample` locations, as a Finding-that-needs-a-
     decision for the human.
4. **Document commits.** Run `census.py commits`. For each commit with
   `handled: false`, oldest first:
   - If it has `pending_matches`, start from that pending entry (written
     by `/implement` or `/quick`): its docs-touched list says what was
     already updated. Verify that, then
     `census.py ledger document <sha> --docs <docs> --pending <id>`.
   - Otherwise read the commit's diff, update whatever architecture doc
     it makes untrue, and `ledger document <sha> --docs <docs>`. If it
     changes nothing a doc describes (tests only, a refactor below the
     doc's level), say why: `ledger document <sha> --skip "<reason>"`.
5. **Findings.** For every `finding` probe in state `silent`, the defect
   it tracked is gone: retire that finding from its doc, or rewrite it
   if part of it still holds, with a new probe. Never leave a finding
   whose probe has gone silent.
6. **Watermark.** Run `census.py ledger advance`. It moves the watermark
   to the ref's HEAD only when every commit is handled; otherwise it
   lists the unhandled ones and leaves the watermark alone. End with
   exactly one of the two: "watermark at `<sha>`" or the list of
   unhandled commits. Never both, never neither.

Report: drift resolved, commits documented or skipped (with reasons),
findings retired, the watermark outcome. No inventory counts in any doc
you edited — counts live in `census.tsv`.

## Promote (`promote <doc>`)

A doc derived automatically (Domain 4 anamnesis, registration, a
migration) starts `status: draft` with a banner. `coder` and `reviewer`
treat its rules as advisory until it is promoted.

1. Delegate to `reviewer` in **doc-verification scope**, in a fresh
   context, so it is independent of whoever drafted the doc. Hand it the
   doc's absolute path and the repo path. It checks every rule against
   the code at the integration ref, citing files, and returns the
   rules it could back and the ones it couldn't.
2. Remove every rule `reviewer` couldn't back. Keep the doc's
   Pitfall/Convention/Finding markers, giving each finding a probe.
3. Only then set `status: active` and remove the "detected
   automatically" banner. Report what was removed and why.
