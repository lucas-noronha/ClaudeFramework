---
doc_type: spec-plan
spec: 0005
summary: The technical plan: approach, scope check, Definition of Done and Test plan.
context_budget: ~2300 tokens
---

# Technical plan

**Tier:** structural. **ADR:** framework ADR 0023
(`evolution/decisions/0023-setup-language.md`, `proposed`). `/tasks` and
`/implement` wait until it is accepted. ADR 0023 settles the mechanics;
this plan only orders them.

## Approach, in dependency order

1. **Language lookup and routing keys** (`_project_paths.py`):
   - `setup_language()` checks `framework.json`, then
     `<framework_home>/project-config.json`, then a legacy
     `canonical_lang`, then falls back to English.
   - `describe` gains `language` {name, code, source} and `legacy_split`.
   - `routing_keys()` returns the primary keys `summary`/`notFor`, with
     `resumo`/`naoResponde` as read aliases.
   - `frontmatter_check.py` and `claude_md_index_check.py` use it.
2. **`translation.py`** (stdlib), per ADR 0023 §2 and §5:
   - the record (LF-normalized `source_sha256`, `status`, `policy`,
     `dest`/`output_sha256` in A/B, the term map, the placeholder map);
   - `plan` (new and changed files only, with a token estimate);
   - `check` (the deterministic fidelity rules);
   - `apply` (including the `CLAUDE.md` index-row step);
   - `recover-placeholders`.

   Tests never call a model; they use hand-written Portuguese fixtures.
3. **`translator` agent** (`.claude/agents/translator.md`, sonnet,
   Read/Write). It translates pristine English into staging, using the
   term map and the marker rules. The mode C install excludes it.
4. **Installer, mode C** (ADR 0023 §2 and §7):
   - `--language`/`--language-code`, kept across upgrades;
   - `build_plan` reads the cache whenever the hash is fresh, and aborts
     on a stale or missing entry;
   - the manifest gains `source_sha256` and `translation` per file;
   - `language` is merged as a recorded scalar, never overwritten
     without `--set-language-setting`; `unmerge` removes it only while
     unchanged;
   - uninstall removes `translations/`.

   English output stays byte-identical to today's.
5. **Retire the split** (ADR 0023 §6):
   - `/spec` step 7, `/plan`'s stakeholder round and `/quick`'s mention;
   - the registration skill's questions and tokens;
   - the validation-summary template, with its index row, installer
     entry and regex;
   - the split prose in `CLAUDE.md.template`;
   - the three runtime tokens;
   - the hook's wiring in both settings templates.

   The hook stays as an unwired legacy shim. `register_project.py`'s
   flags stay, hidden and ignored with a warning.
6. **Shipped material** (FR-04, FR-11, FR-12):
   - `{{CANONICAL_LANG}}` becomes `{{LANGUAGE}}`;
   - templates, workflow docs and prompts write `summary`/`notFor`;
   - every prompt that makes the model write an artifact or frontmatter
     says: free text in `<language>`, while keys, enumerated values,
     `## Tasks`/`## Reconciliation`, reconciliation phrases and
     `Approved`/`Returned` stay English;
   - `CLAUDE.md.template` carries the reply/reasoning rule.
7. **`/setup-framework`** (FR-01, FR-07, FR-10; ADR 0023 §1, §3, §4, §7):
   - Domain 1 asks for the language (English first). If non-English, it
     states the `plan` estimate, translates, then resolves; it writes the
     record and the `language` setting.
   - Domain 5 asks only while the AI-repo config has no language, and
     adds `language` to the shared settings.
   - Domain 6 batch gains the language.
   - The mode A upgrade flow and the mode B merge-retranslate flow.
   - Migration is offered when `legacy_split` is true.
8. **Boundary and docs.**
   - `test_skeleton_boundary.py` asserts that this repo has no record,
     cache, `language` key or `.claude/project-config.json`, and that
     shipped files carry no split tokens.
   - Update `.claude/README.md`, the relevant workflow docs and the
     `CHANGELOG.md`.

## Scope check

Each item below is flagged, not folded in silently:

- **New components:** the `translator` agent and `translation.py`. They
  are implied by FR-05/FR-06 and NFR-04, and ADR 0023 settles them.
- **The legacy shim and the ignored flags** serve NFR-05.
- **AC-07 deviation.** AC-07 says the existing suite passes unchanged,
  but FR-12 renames the default routing keys. Two existing assertions
  test the old defaults, both in `tests/test_pipeline_cost.py`: the
  `` `resumo` `` nudge, and the shipped templates carrying
  `resumo:`/`naoResponde:`. Those two assertions are updated to the new
  keys, plus an alias test that keeps the old behaviour. Every other
  existing test passes unchanged. **The human confirms this together
  with ADR 0023.**
- **Out of reach of a unit test:** translation quality, and a fresh
  session actually replying in the language (AC-04, AC-06). Both are
  checked by hand (see the Definition of Done).

Constitution: no conflict. Everything is stdlib, with no new dependency
(Principle V), and no secrets are involved.

## Definition of Done

- [ ] `python -m unittest discover -s tests -t tests` passes, with the
  Test plan below and the AC-07 deviation above.
- [ ] `reviewer` approved every coder-tier task.
- [ ] AC-01, AC-02, AC-03, AC-05, AC-07, AC-08, AC-09 and AC-10 are
  covered by tests.
- [ ] AC-04 and AC-06 are checked by hand: a pt-BR mode C dry install
  into a temp config dir translates a sample, every file passes
  `check`, and a session with `language` set replies in Portuguese.
- [ ] An English install is byte-identical to the pre-change install
  (NFR-01).
- [ ] Framework ADR 0023 is `accepted` before implementation starts.

## Test plan

- L01: `setup_language()` order — `framework.json` > setup config >
  legacy `canonical_lang` > English — FR-02, NFR-05
- L02: `describe` reports `language` {name, code, source} and
  `legacy_split` — FR-02
- L03: `register_project.py` neither asks for nor writes a language; the
  stakeholder flags are accepted, ignored and warned about — FR-01,
  NFR-05, AC-01
- L04: `routing_keys()` defaults to `summary`/`notFor` with aliases; a
  project override replaces the primary; the primary wins over an alias
  — FR-12, AC-10
- L05: `frontmatter_check` and `claude_md_index_check` treat a doc with
  `resumo`/`naoResponde` exactly as before, and nudges name the primary
  key — FR-12, AC-10
- L06: `plan` lists only new and changed sources; a CRLF-only difference
  is not a change; it gives a token estimate — FR-06, NFR-06, AC-09
- L07: an English setup makes `plan`/`apply` a no-op and writes no
  record — AC-09, NFR-06
- L08: `check` keeps frontmatter keys and enumerated values invariant;
  allow-listed free-text values may change; an unknown key fails safe —
  FR-11, AC-10
- L09: `check` rejects changed headings, ordinals, code blocks, inline
  code, placeholders, `/commands`, ids and links, and dropped English
  literals — FR-08, NFR-04, AC-03
- L10: a file that fails `check` stays English and is recorded
  `status: english` with its reasons — NFR-04
- L11: `apply` re-translates only changed `replace` sources; a `keep`
  file is translated only on create — FR-06, NFR-06
- L12: the cross-file step copies each translated summary into its
  `CLAUDE.md` index row — FR-11
- L13: `recover-placeholders` rebuilds the map from a resolved file, and
  reports a non-match — FR-06
- L14: mode B upgrade, simulated with git and fixtures: paths whose hash
  changed are re-translated whether or not they conflicted; unchanged
  ones keep the local translation; a failed one keeps upstream English —
  FR-06, AC-05
- L15: mode A upgrade: untouched outputs are replaced, edited outputs
  reported, `keep` files untouched, upstream deletions reported only —
  FR-06, FR-10
- L16: installer `--language pt-BR` with a fresh cache installs the
  translated bytes; a re-run is idempotent, with no hand-edit refusal —
  NFR-02, AC-05
- L17: installer with a stale or missing cache entry aborts before
  writing anything — FR-06
- L18: an English install is identical to today's install — NFR-01,
  AC-08
- L19: `language` scalar merge: absent → set and recorded; different →
  shown, not overwritten without the flag; uninstall removes it only
  while unchanged; settings restore byte-for-byte — FR-07, AC-06
- L20: split retired: neither settings template wires
  `validation_sync_check`; the shim is a no-op without split keys and
  acts with them; no `.validation-*.md` file is deleted — FR-03, NFR-05,
  AC-02, AC-08
- L21: boundary: this repo has no record, cache, `language` key or
  `.claude/project-config.json`; shipped files have no
  `{{CANONICAL_LANG}}`/`{{STAKEHOLDER_*}}` and use `summary`/`notFor` —
  FR-03, FR-12
- L22: on a Portuguese fixture project, `spec_status_sync`,
  `spec_index`, `decision_index`, the reconciliation phrases and the
  reviewer verdict all work exactly as in English — FR-08, AC-07

