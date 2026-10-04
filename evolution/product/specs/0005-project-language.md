---
doc_type: spec
id: 0005
status: implemented
area: localization
relates_to: []
resumo: How does one language, chosen at setup, govern every artifact the framework writes or copies (docs, templates, agent prompts) and the assistant's replies?
naoResponde: How hooks, scripts and census internals are written. They stay as is.
context_budget: ~1300 tokens
---

# Project language — one language for every project artifact and the conversation

## Feature name

The framework asks once, at setup, for the language. That language then governs every artifact
the framework generates or copies, including its own agent, command and skill prompts, and the
language the assistant uses with the user. One setup has one language: in modes B and C, every
project behind that setup shares it.

## Business context

**Today, before this spec**, a team that doesn't work in English gets a mixed result:

- `canonical_lang` covers specs, `CLAUDE.md`, ADRs and architecture docs.
- `stakeholder_lang` covers only the `.validation-<code>.md` companion of a spec.
- The material the framework copies into a project (requirement and validation templates,
  workflow docs, both constitution layers, glossary, the ADR template, the `CLAUDE.md` template
  prose, architecture templates) is never translated. It always arrives in English, whatever
  language the project uses.
- Nothing sets the language of the assistant's replies. The user has to repeat it every
  session, and the setup never asks.

The result is a project whose documentation, templates and conversation switch between two
languages, whoever its owners are. This spec changes that: everything the framework copies is
translated into the chosen language (FR-05).

In one sentence: the people who own a project should read and write all of its documentation,
and talk to the assistant, in their own language, chosen once.

Several projects behind one mode B or C setup usually belong to one ecosystem or to one
person's workflow, so one consistent language for the whole setup is the expected case.

## Functional requirements

- FR-01: Setup asks for the **language** (name + code) once per setup:
  - Domain 1 in mode A, for that repo;
  - Domain 5 in mode B, for the AI-repo, the first time it is set up;
  - Domain 6 in mode C, for the user-level install.

  In modes B and C, linking or registering another project never asks again. The project
  inherits the setup's language. **English is the default**, offered first.
- FR-02: The language is stored where the setup's configuration lives: mode A's
  `.claude/project-config.json`, the mode B AI-repo's shared config, and mode C's
  `framework.json`. Every hook, script and pipeline command reads it from there.
- FR-03: **One language, no split.** The canonical/stakeholder split ends:
  - `stakeholder_lang`, `stakeholder_lang_code` and the `.validation-<code>.md` companion are
    retired;
  - `validation_sync_check` and the validation-summary template go away;
  - `canonical_lang` is replaced by the setup language.
- FR-04: Every artifact the pipeline **generates** is written in the setup language:
  - specs, lite specs, the "Technical plan", Definition of Done, Test plan and "Tasks" content;
  - ADRs, architecture docs and their drafts;
  - `CLAUDE.md`, glossary entries and reconciliation lines;
  - census-written prose, PR descriptions and commit messages the framework proposes.
- FR-05: Every artifact the framework **copies or installs** reaches the setup in the setup
  language, with no exception:
  - templates, workflow docs, the constitution layers, the glossary, the ADR template and
    `CLAUDE.md.template`;
  - the `.claude/` agent, command and skill prompts.

  English is the source in the framework repository:
  - **English setup:** the material is copied as-is, with no translation pass and no
    translation cost.
  - **Any other language:** the model translates the material at setup time. That setup pays
    the translation cost.
- FR-06: For a non-English setup, every framework upgrade translates whatever changed
  upstream, and only that. Copied material never reverts to English.
- FR-07: The assistant replies to the user in the setup language. Setup writes Claude Code's
  native `language` setting at the scope that matches the mode. `CLAUDE.md` also states the
  rule, as guidance for the reasoning, which the setting doesn't cover.
- FR-08: Machine-parsed markers stay invariant in every language, in generated and translated
  files alike:
  - frontmatter keys and their enumerated values (`status: approved`, `doc_type`, ...; see
    FR-11);
  - section headings that hooks parse (`## Tasks`, `## Reconciliation`);
  - FR/NFR/AC/T identifiers, file names, paths and command/agent/skill names;
  - `{{PLACEHOLDER}}` tokens and runtime tokens.
- FR-09: Internal tooling is out of the language rule: hooks, scripts, census extractors and
  their output keys, and installer messages.
- FR-10: Changing the language later never rewrites existing project artifacts silently.
  Translating them is offered, never forced. The copied/installed material is re-translated
  through the FR-06 path.
- FR-11: **Frontmatter** follows the same split as the rest of a file:
  - keys stay in English;
  - enumerated values that tooling reads stay in English (`status: approved`,
    `doc_type: spec`, `area: <tag>`);
  - free-text values (the routing summary, "when not to open this", titles, descriptions) are
    written, or translated, in the setup language.
- FR-12: The default routing keys get English names: `resumo` → `summary` and `naoResponde` →
  `notFor`.
  - Every shipped template, generated doc and hook default uses the new names.
  - The old names keep being read as aliases, so existing docs need no migration.
  - A project's own `routing_keys` override keeps working.

## Non-functional requirements

- NFR-01: An existing project with no project language configured behaves exactly as today
  (English).
- NFR-02: An upgrade keeps copied and installed material in the setup language (FR-06).
  Translated files are recognized as the framework's own, so translating never trips the
  installer's hand-edit refusal (framework spec 0001 NFR-01/NFR-03).
- NFR-03: Choosing a language never breaks a hook, an index or a test. FR-08 is what
  guarantees this.
- NFR-04: A translated prompt keeps the meaning and every step of its English source. The
  translation pass verifies that structure (headings, numbered steps, code blocks, markers)
  is preserved, and reports any file it could not translate faithfully, leaving it in
  English.
- NFR-05: Existing setups with a split configured keep working until they choose a language.
  Retiring the split (FR-03) never deletes an existing `.validation-*.md` file.
- NFR-06: Translation cost is proportional:
  - zero for an English setup;
  - for any other language, paid once at setup and then only for files that changed upstream
    at each upgrade. Unchanged files are never re-translated.

  Setup states the expected cost before translating, so a non-English choice is made
  knowingly.

## Explicitly out of scope

- Translating the framework's own repository (`evolution/`, README, CHANGELOG).
- Per-user or per-project languages inside one mode B/C setup.
- The model's extended-thinking language beyond what the `language` setting and `CLAUDE.md`
  instructions can steer. Claude Code documents no control for it.

## Roles and permissions involved

The person running `/setup-framework` chooses the language for the whole setup. Every project
and everyone working in it inherits it.

## Related specs

(none — first spec in area `localization`)

## Acceptance criteria

- [ ] AC-01: Setting up in Portuguese in each mode (A, B, C) asks the language once. Linking or
  registering a second project in B/C does not ask again. (FR-01, FR-02)
- [ ] AC-02: No split remains. `/spec` writes one spec file, no `.validation-*.md`, and no
  split question is asked anywhere. (FR-03)
- [ ] AC-03: `/spec`, `/plan`, `/tasks`, `/adr` and `/quick` write their artifacts in
  Portuguese. Frontmatter keys, `status` values, `## Tasks`, `## Reconciliation` and FR/AC
  ids stay as-is. (FR-04, FR-08)
- [ ] AC-04: The copied or shared templates, workflow docs, constitution, `CLAUDE.md` and the
  agent, command and skill prompts the setup holds are in Portuguese. (FR-05)
- [ ] AC-05: A framework upgrade re-translates changed sources. The installer does not refuse
  translated files as hand edits. (FR-06, NFR-02)
- [ ] AC-06: The settings that setup writes carry `language`, and a fresh session replies in
  Portuguese. (FR-07)
- [ ] AC-07: Every hook and index works on a Portuguese setup exactly as on an English one,
  and the existing test suite passes unchanged, except the two assertions on the old default
  routing keys, which FR-12 updates to `summary`/`notFor` (an alias test keeps the old
  behaviour covered). (FR-08, FR-09, FR-12, NFR-03)
- [ ] AC-08: A setup with no language configured is unchanged. An existing split setup keeps
  working until migrated, and no `.validation-*.md` file is deleted. (NFR-01, NFR-05)
- [ ] AC-09: An English setup runs no translation pass. A non-English upgrade re-translates
  only the files that changed upstream. (FR-05, FR-06, NFR-06)
- [ ] AC-10: A generated or translated doc's frontmatter has English keys, English enumerated
  values, and free-text values in the setup language. A new doc uses `summary`/`notFor`. A doc
  still using `resumo`/`naoResponde` is indexed and checked exactly as before. (FR-11, FR-12)

## Impact on existing architecture

- Retires the canonical/stakeholder split. Its rationale is cited from framework ADR 0001 in
  `CLAUDE.md.template`, and framework ADR 0013/0015 build `project-config.json` around it.
- Adds a model translation pass to setup and to every upgrade:
  - in mode C, it interacts with the installer's manifest and hand-edit refusal (framework
    ADR 0017);
  - in mode A, it interacts with what the skeleton ships (framework ADR 0021).
- Moves the language from per-project config to per-setup config in modes B/C (framework ADR
  0013, 0015).

Expected to need a new framework ADR at `/plan`.

## Reconciliation

- [task 1] FR-02: matches spec (after one fix)
- [task 1] NFR-05: matches spec (`legacy_split` requires an actual split; shim uses the same predicate)
- [task 2] FR-12: matches spec
- [task 2] AC-07: matches spec as amended (only the two old-default assertions changed; the templates one accepts either key until task 12)
- [task 2] AC-10: matches spec
- [task 3] FR-05: matches spec (record schema; `dest`/`output_sha256` only in modes A/B)
- [task 3] FR-06: matches spec (`plan` lists new and changed only, with a token estimate; replace/keep honoured)
- [task 3] NFR-06: matches spec (LF-normalized, BOM-free hash; unchanged sources never re-translated)
- [task 3] AC-09: matches spec (English `plan`/`apply` are no-ops with no record; `en` and `en-US` tested)
- [task 4] FR-08: matches spec
- [task 4] FR-11: matches spec
- [task 4] NFR-04: matches spec
- [task 4] AC-03: matches spec
- [task 4] AC-10: matches spec
- [task 5] FR-06: matches spec (`recover-placeholders`)
- [task 5] FR-11: matches spec (cross-file step realized as a `sync-index` subcommand run after `apply`)
- [task 6] FR-06: matches spec
- [task 6] FR-10: matches spec
- [task 6] AC-05: matches spec (mode B re-translates changed paths, conflicted or clean; `take-upstream` trusts the caller to pass only listed paths, which `/setup-framework` must state)
- [task 7] FR-05: matches spec
- [task 7] FR-08: matches spec
- [task 7] FR-11: matches spec
- [task 7] NFR-04: matches spec (prompt also states the check's length-ratio bound and verdict-word count)
- [task 8] FR-05: matches spec
- [task 8] FR-06: matches spec
- [task 8] NFR-01: matches spec
- [task 8] NFR-02: matches spec
- [task 8] AC-05: matches spec
- [task 8] AC-08: matches spec
- [task 9] FR-07: matches spec
- [task 9] AC-06: matches spec
- [task 11] FR-01: matches spec
- [task 11] NFR-05: matches spec
- [task 11] AC-01: matches spec
- [task 13] FR-01: matches spec
- [task 13] FR-07: matches spec
- [task 13] FR-10: matches spec
- [task 13] NFR-06: matches spec
- [task 13] AC-01: matches spec
- [task 13] AC-04: matches spec
- [task 13] AC-06: matches spec
- [task 14] FR-08: matches spec
- [task 14] AC-07: matches spec
- [task 12] FR-03: matches spec
- [task 12] FR-04: matches spec
- [task 12] FR-07: matches spec
- [task 12] FR-08: matches spec
- [task 12] FR-11: matches spec
- [task 12] FR-12: matches spec
- [task 10] FR-03: matches spec
- [task 10] NFR-05: matches spec (shim acts only with split keys and no setup language, never deletes companions, fails open)
- [task 10] AC-02: matches spec
- [task 10] AC-08: matches spec

## Technical plan

**Tier:** structural. **ADR:** framework ADR 0023
(`evolution/decisions/0023-setup-language.md`, `proposed`). `/tasks` and
`/implement` wait until it is accepted. ADR 0023 settles the mechanics;
this plan only orders them.

### Approach, in dependency order

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

### Scope check

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

### Definition of Done

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

### Test plan

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

## Tasks

Layers are framework layers: **hooks/scripts** (Python, tested) and **commands/docs** (prose read
by agents). No task touches sensitive data or a new table. Shared files that force an order:
`_project_paths.py` (tasks 1, 2), `translation.py` (3–6), `install_user_level.py` (8, 9, 11),
command prompts (10, 12, 13). Every task follows framework ADR 0023.

- [x] 1. **Language lookup** — hooks/scripts: `_project_paths.py` `setup_language()` (`framework.json` → `<framework_home>/project-config.json` → legacy `canonical_lang` → English) and `describe`'s `language` {name, code, source} and `legacy_split`. — Depends on: none — Tests: L01, L02
- [x] 2. **Routing keys** — hooks/scripts: `_project_paths.routing_keys()` (primary `summary`/`notFor`, aliases `resumo`/`naoResponde`, project override replaces the primary, primary wins); `frontmatter_check.py` and `claude_md_index_check.py` use it, and nudges name the primary key; update the two old-default assertions in `tests/test_pipeline_cost.py` per the AC-07 deviation. — Depends on: 1 — Tests: L04, L05
- [x] 3. **`translation.py` core** — hooks/scripts: new `.claude/scripts/translation.py` (stdlib): the record (LF-normalized `source_sha256`, `status`, `policy`, A/B `dest`/`output_sha256`, term map, placeholder map), `plan` (new and changed only, with a token estimate), `apply` (`replace` vs `keep`), and the English no-op. Uses Portuguese fixtures, never a model. — Depends on: none — Tests: L06, L07, L11
- [x] 4. **`translation.py check`** — hooks/scripts: the deterministic fidelity check of ADR 0023 §5. Frontmatter keys and order invariant, values invariant except the allow-list, frontmatter-shaped fences; headings, ordinals, checkboxes, tables and the length ratio; byte-identical code blocks except `markdown`/`md`/`text`; identical multisets of inline code, placeholders and tokens, `/commands`, ids, links, HTML comments and `framework ADR|spec NNNN`; the English literals. A failure stays English, recorded `status: english` with its reasons. — Depends on: 3 — Tests: L08, L09, L10
- [x] 5. **Cross-file step and placeholder recovery** — hooks/scripts: `apply` translates `CLAUDE.md.template` last and copies each translated summary into its index row; `recover-placeholders` rebuilds the map by matching pristine sources (with `{{NAME}}` as capture groups) and reports non-matches. — Depends on: 4 — Tests: L12, L13
- [x] 6. **Upgrade support** — hooks/scripts: `translation.py` support for the mode A upgrade (untouched output → retranslate, edited → report, `keep` untouched, deletions reported only) and the mode B merge (every recorded path whose `source_sha256` at `MERGE_HEAD` changed, conflicted or not; failure keeps upstream English). — Depends on: 5 — Tests: L14, L15
- [x] 7. **`translator` agent** — commands/docs: new `.claude/agents/translator.md` (model sonnet, tools Read/Write). It translates pristine English into staging with the term map and the marker rules, and never edits sources. — Depends on: 4 — Tests: none (prose; checked by `reviewer`)
- [x] 8. **Installer: language and cache** — hooks/scripts: `install_user_level.py` `--language`/`--language-code` (kept across upgrades, into `framework.json`); `build_plan` reads the fresh cache, `english`-status files read the source, and a stale or missing entry aborts before any write; manifest `source_sha256`/`translation`; the `translator` agent excluded from the install; `uninstall.py` removes `translations/`. English output byte-identical. — Depends on: 1, 3 — Tests: L16, L17, L18
- [x] 9. **Installer: `language` setting** — hooks/scripts: `merge`/`unmerge` learn recorded scalars (absent → set, `added_scalars`; different → shown, overwritten only with `--set-language-setting`; removed only while unchanged; byte restore kept). — Depends on: 8 — Tests: L19
- [x] 10. **Retire the split (prose, hook, templates)** — commands/docs plus one hook. Remove `/spec` step 7 and its reminder, `/plan`'s stakeholder round, `/quick`'s mention, and the registration skill's language questions, bulk keys and tokens. Delete `docs/product/validation-summary-template.md`, and remove its installer entry and shared-path regex in the same task, so the install tests stay green (moved here from task 11). Remove the split prose in `CLAUDE.md.template`. Unwire `validation_sync_check.py` in both settings templates, and turn it into the legacy shim. Never delete a `.validation-*.md`. — Depends on: none — Tests: L20
- [x] 11. **Retire the split (scripts)** — hooks/scripts: `register_project.py` neither asks for nor writes a language; the three stakeholder flags and legacy plan keys are hidden, accepted and ignored with a warning. Also remove the installer's split `RUNTIME_TOKENS`. And make the `language` overwrite non-sticky: an upgrade without `--set-language-setting` never overwrites a value the user changed (found in task 9's review). — Depends on: 9, 10 — Tests: L03
- [x] 12. **Shipped material** — commands/docs: `{{CANONICAL_LANG}}` → `{{LANGUAGE}}`; `summary`/`notFor` in every shipped template, workflow doc and prompt; every prompt that makes the model write an artifact or frontmatter says free text is in `<language>`, while keys, enumerated values, `## Tasks`/`## Reconciliation`, reconciliation phrases and `Approved`/`Returned` stay English; `CLAUDE.md.template` gets the reply/reasoning rule. Also drop the stale `.validation-` companion prose in `docs/product/requirements-template.md` (found in task 10's review). `test_skeleton_boundary.py` gains the boundary asserts. — Depends on: 2, 10 — Tests: L21
- [x] 13. **`/setup-framework`** — commands/docs: Domain 1 language question (English first; non-English → `plan` estimate, confirm, translate, then resolve, record, `language` setting); Domain 5 asks only while the AI-repo config has none, and adds `language` to the shared settings; Domain 6 batch gains the language (`--language`); the mode A upgrade and mode B merge-retranslate flows (`take-upstream` only for paths `upgrade-plan` listed); migration offered when `legacy_split`. Also drop `product/validation-summary-template.md` from mode B's shared-root bootstrap check (Domain 5, "five" → "four"), which would otherwise stop mode B setup (found in task 10's review). — Depends on: 6, 7, 9, 11, 12 — Tests: none (prose; checked by `reviewer`)
- [x] 14. **Portuguese-project hook test and docs** — hooks/scripts tests plus docs: a Portuguese fixture project exercising `spec_status_sync`, `spec_index`, `decision_index`, the reconciliation phrases and the reviewer verdict; `.claude/README.md` rows (`translation.py`, `translator`), the relevant workflow docs, and a `CHANGELOG.md` entry. — Depends on: 13 — Tests: L22
