---
doc_type: adr
id: 0023
status: accepted
date: 2026-10-04
supersedes: null
superseded_by: null
context_budget: ~3600 tokens
---

# ADR 0023 — One language per setup, translated by the model before any deterministic rewrite and tracked by source hash

Like ADR 0001–0022, this documents a decision about *this framework's
own* tooling. It **amends** six earlier ADRs:

- ADR 0013 and 0015: the language leaves `project-config.json` and
  moves to the setup's own config.
- ADR 0017: the installer reads a translation cache, records the
  language in `framework.json`, and merges one scalar setting.
- ADR 0019: the default routing keys get English names.
- ADR 0020: `validation_sync_check.py` leaves every settings template.
- ADR 0021: translated copies exist only in adopters' setups.

It also adds one subagent role under ADR 0001's split. It supersedes
none of them.

## Context

Spec 0005 is approved, and its FR/NFR/AC are fixed:

- One language per setup, English by default, at zero cost.
- The model translates every Markdown file the framework copies or
  installs.
- An upgrade re-translates only what changed upstream.
- The canonical/stakeholder split is retired.
- Setup writes Claude Code's `language` setting.
- Machine-parsed markers stay invariant, and so do frontmatter keys and
  enumerated values. Free-text frontmatter values are translated
  (FR-11).
- The routing keys become `summary`/`notFor`, with the old names read
  as aliases (FR-12).
- Hooks and scripts are otherwise untouched.

Four facts of the current code shape the answer:

- **The installer is exact Python, and only the model can translate.**
  Every install step that has to be exact is deterministic Python (ADR
  0017). Mode C's `Rewriter` prefixes `/spec` and backticked role names,
  and turns relative paths into absolute per-machine ones. The manifest
  hashes the final bytes and refuses to overwrite a file whose hash
  moved.
- **Modes A and B already diverge from the skeleton.**
  - Mode A has no upgrade path. The skeleton is copied by hand, and
    Domain 1 resolves placeholders in place.
  - Mode B's AI-repo is a git clone of this repository, already carrying
    local commits from that same in-place resolution. A translated file
    is a whole-file rewrite, so any upstream change to it conflicts on
    pull.
- **Hooks parse more English than FR-08's examples list.**
  - `pipeline_metrics.py` counts `[task …] …: matches spec`,
    `: diverged` and `[task …] out of scope` lines.
  - `pipeline_metrics.py` reads a reviewer verdict only from a reply
    starting `Approved` or `Returned`.
  - `census.py` reads `<!-- census-probe … -->` comments.
  - `spec_status_sync.py` reads the `- [x]` lines under `## Tasks`.
  - `claude_md_index_check.py` requires a `CLAUDE.md` index row to equal
    its doc's routing summary *verbatim*. That is a link *between* files,
    for example the `CLAUDE.md.template` row and
    `living-architecture-docs.md`'s summary.

  A Portuguese "Aprovado" loses a verdict silently.
- **The existing suite encodes what the spec changes.**
  - `test_user_level_install.py` and `test_worktree_mode_c.py` pass
    `--canonical-lang/--stakeholder-*` flags.
  - `test_ac05` calls `validation_sync_check.py` directly.
  - `test_pipeline_cost.py` asserts the `` `resumo` `` nudge and
    `resumo:`/`naoResponde:` in the shipped templates.

  AC-07 asks for an unchanged suite.

One stray reference: `CLAUDE.md.template` cites framework ADR 0001 for
the split's rationale, which 0001 doesn't contain. The citation simply
goes.

## Options considered

- **Translate after install, on the installed files.** Rejected.
  - Every translated file would trip the hand-edit refusal.
  - The prefix and per-machine paths would be baked into the
    translation, so a new `--prefix` or config dir would force a full
    re-translation.
- **Keep mode B translations out of the tracked paths** (an overlay
  folder, `skip-worktree`). Rejected.
  - Claude Code loads `.claude/agents|commands|skills` from fixed
    tracked paths.
  - `skip-worktree` is lost silently on checkout or reset.
- **Install mode B by copy from a pristine checkout, like mode C.**
  Rejected. It reverses ADR 0013/0014's premise that the AI-repo *is*
  the framework, versioned and shared.
- **Let the setup session translate by itself.** Rejected. About 40
  files would flood the main context, at the session's model price.
  `setup-framework.md` alone is about 1100 lines.
- **A committed `.claude/framework.json` as mode B's language home.**
  Rejected. In mode C that name means "the installer wrote this".
- **Rename the routing keys and migrate existing docs.** Rejected. FR-12
  asks for aliases and no migration.
- **Chosen:**
  - Translate the pristine English *before* any deterministic rewrite.
  - A dedicated `translator` subagent with a fixed, cheaper model.
  - In mode B, translations as ordinary commits, upgraded by taking
    upstream and re-translating by source hash.
  - The language stored in the config each mode already treats as
    setup-wide.

## Decision

1. **Where the language lives.**
   - **Keys.** Two keys:
     - `language`: the language's English name, the value Claude Code's
       `language` setting takes.
     - `language_code`: BCP 47. `en` or `en-*` means English.
   - **Mode A:** `<repo>/.claude/project-config.json`.
   - **Mode B:** `<ai-repo>/.claude/project-config.json`.
     - It is committed, Domain 1 already writes it, and every linked
       repo reaches it through the `.claude` link.
     - Domain 5 asks for the language only while this file has none.
       Domain 1's prerequisite pass never asks.
   - **Mode C:** `framework.json`. The installer gains `--language` and
     `--language-code`, kept across upgrades like `worktrees_root`.
   - **Lookup.** `_project_paths.setup_language()` checks, in order:
     1. `framework.json`;
     2. `<framework_home>/project-config.json`;
     3. the project's legacy `canonical_lang` (NFR-05);
     4. English.

     `describe` gains `language: {name, code, source}` and
     `legacy_split`.
   - **Registration.** A subtree config never carries the language.
     `register_project.py` and the `project-registration` skill neither
     ask for it nor write it. They fill `CLAUDE.md`'s `{{LANGUAGE}}` from
     `describe`.
   - **Placeholder.** `{{LANGUAGE}}` replaces `{{CANONICAL_LANG}}` in
     shipped prompts.
     - Domains 1 and 5 resolve it statically.
     - In mode C it stays a runtime token, `<language>`, that the
       registration skill defines from `describe`. That way a legacy
       project's `canonical_lang` still counts until the setup picks a
       language.
2. **Translation mechanics.**
   - **What is translated.** Every shipped `.md` and `.md.template` file.
     JSON, Python, `.example` files and generated indexes
     (`skills/README.md`) are never translated.
   - **The script.** A new stdlib script,
     `.claude/scripts/translation.py`, with four subcommands:
     - `plan` lists new and changed sources against the record, with a
       token estimate. Setup states that estimate and confirms before
       any translation (NFR-06).
     - `check` runs the item 5 checks.
     - `apply` writes the file and the record.
     - `recover-placeholders` supports item 3.
   - **Term map.** Made first (framework vocabulary → target terms),
     stored in the record, and given to every batch.
   - **The `translator` agent** (model `sonnet`, Read/Write only)
     translates **pristine English sources** into staging, in parallel
     batches. A file that fails `check` stays English, recorded
     `status: english` with its reasons.
   - **The record.**
     - Per source path:
       - `source_sha256`, over UTF-8 text with CRLF→LF and no BOM, so
         working-tree EOL is never mistaken for a change;
       - `status` and `policy` (`replace` or `keep`);
       - in modes A and B, also `dest` and `output_sha256`.
     - Also stored: the language, the term map, and in modes A/B the
       resolved-placeholder map.
     - Location:
       - modes A/B: `.claude/translation-record.json`, committed;
       - mode C: `<namespace>/translations/record.json`, beside the
         cache.
   - **Rules.**
     - An unchanged `source_sha256` is never re-translated (NFR-06).
     - A `keep` file is translated only when it is created.
     - A new language re-translates every `replace` file from English,
       never from the previous translation. `keep` files and project
       artifacts are offered, never forced (FR-10).
   - **Mode C order: translate, then rewrite, then hash.**
     1. Setup fills the cache before the installer's dry run.
     2. With a non-English language, `build_plan` reads the cached text
        in place of the source whenever the record's `source_sha256`
        matches. Where the record says `english`, it reads the English
        source.
     3. Today's frontmatter, reference and runtime-token passes then run
        unchanged. The invariant markers are what keep their regexes
        matching.

     A translatable source with no fresh entry **aborts the run** (FR-06
     enforced), except a `keep` file that already exists.

     The manifest still hashes the final bytes, so translated files are
     framework-owned and the hand-edit refusal is unchanged (NFR-02). It
     also gains `source_sha256` and `translation` per file. Uninstall
     removes `translations/`. With English, no cache is read and the
     output is today's.
3. **Mode B upgrade.** Translations are ordinary AI-repo commits.
   - The upgrade:
     1. `git fetch` upstream.
     2. `git merge --no-commit`.
     3. For **every recorded path whose `source_sha256` at `MERGE_HEAD`
        differs from the record**, whether it conflicted or merged
        cleanly:
        1. Take upstream's English (`git checkout MERGE_HEAD -- <path>`).
        2. Translate it and `check` it.
        3. Re-apply the placeholder map, then `apply`.
     4. Commit the merge.
   - The hash decides, not git's conflict status. A hunk inside a code
     block can merge cleanly into a stale translation.
   - Unchanged paths keep the AI-repo's version. A failed translation
     keeps upstream's English, so the merge always completes.
   - An AI-repo bootstrapped before this ADR has no placeholder map.
     `recover-placeholders` rebuilds it by matching each pristine
     source, with `{{NAME}}` as capture groups, against the current
     file. It asks about any disagreement or non-match.
4. **Mode A.**
   - **Setup.** Domain 1 asks for the language. For a non-English
     choice:
     1. Translate the pristine copied files.
     2. Resolve placeholders and rename.
     3. Write the record, with the placeholder map and the
        post-resolution `output_sha256`.
   - **Upgrade.** `/setup-framework` is pointed at a newer checkout and
     runs `plan` against it. Then:
     - A changed source with untouched output is re-translated,
       re-resolved and overwritten.
     - A changed source with locally edited output is shown and asked
       about.
     - `keep` files are never touched.
     - New upstream files are translated.
     - Files deleted upstream are reported, never deleted.
   - **English.** An English setup writes no record.
5. **Fidelity check (NFR-04, FR-08, FR-11).** `check` is deterministic.
   - **Frontmatter.**
     - Keys: identical, in the same order.
     - Values: identical, except for an **allow-list of free-text
       keys**: `description`, `argument-hint`, `title`, and the routing
       keys with their aliases (item 9). Any key not on the list keeps
       its value, enumerated or not (`status`, `doc_type`, `area`, `id`,
       `name`, `model`, `tools`, `applies_to`, `context_budget`, …), so
       an unknown key fails safe.
     - The same rule applies to frontmatter-shaped fenced blocks
       (`yaml`, or ones that start with `---`).
   - **Structure.**
     - Same heading count and levels.
     - Same numbered-item ordinals, checkbox count and table shape.
     - A length ratio within bounds.
   - **Fenced code blocks.** Byte-identical, except blocks tagged
     `markdown`/`md`/`text`. Those are prose templates written into user
     files, so they are translated and checked recursively.
   - **Identical multisets** of:
     - inline code spans;
     - `{{PLACEHOLDER}}`s and runtime tokens;
     - `/command`s;
     - FR/NFR/AC/T ids;
     - link targets and URLs;
     - HTML comments;
     - `framework ADR|spec NNNN` references, kept verbatim.
   - **English literals**, verbatim and in equal counts:
     - `## Tasks` and `## Reconciliation`;
     - the reconciliation outcome phrases;
     - the reviewer's `Approved`/`Returned`.

     Every prompt that makes the model write these, or write frontmatter,
     says that keys, enumerated values and these literals stay English,
     and that free text uses the setup language.
   - **Cross-file step.** `apply` translates `CLAUDE.md.template` last,
     then copies each indexed doc's translated summary into its index
     row's first cell. The doc wins, which is the hook's own rule.
6. **Retiring the split.**
   - **Removed:**
     - `/spec` step 7 and its reminder;
     - `/plan`'s stakeholder round;
     - `/quick`'s mention;
     - the registration skill's two language questions, its bulk-plan
       keys and its token list;
     - `docs/product/validation-summary-template.md`, with its index
       row, its installer entry and its shared-path regex;
     - the split prose in `CLAUDE.md.template`;
     - the three split `RUNTIME_TOKENS`;
     - `validation_sync_check.py`'s wiring in **both** settings
       templates. Mode C's merge/unmerge drops it on upgrade.
   - **Kept, for NFR-05 and AC-07:**
     - The hook file stays as an **unwired legacy shim**. It acts only
       when a config has split keys and no setup language.
     - Mode A/B settings that still wire the hook never hit Python's
       exit 2 for a missing script, which would be a blocking hook
       error.
     - `register_project.py`'s three flags stay, hidden, accepted and
       ignored with a warning. So do legacy plan keys.
     - Every hook's `.validation-` exclusion stays. No `.validation-*.md`
       file is ever deleted.
   - **Migration.** Setup offers it when `legacy_split` is true.
7. **The `language` setting.**
   - **Mode A:** Domain 1 writes it to `.claude/settings.json`.
   - **Mode B:** Domain 5's language step adds it to the shared
     `<ai-repo>/.claude/settings.json`, after confirmation. This is the
     one exception to step 9's "leave it alone".
   - **Mode C:** the installer's `merge` learns scalar keys:
     - absent → set, recorded in `added_scalars`;
     - equal → not recorded;
     - different → shown in the dry run, and overwritten only with
       `--set-language-setting`.

     `unmerge` removes the key only while it still holds the recorded
     value. The byte-for-byte restore of the pre-install backup is
     unchanged.
   - **`CLAUDE.md.template`** states the rule: artifacts, replies and,
     where steerable, reasoning in `{{LANGUAGE}}`. It also lists the
     markers that stay verbatim.
8. **This repository is never translated.**
   - Its shipped tree stays English.
   - No `translation-record.json`, `translations/`, `language` key or
     `.claude/project-config.json` is committed here.
     `tests/test_skeleton_boundary.py` asserts this.
   - Translated copies exist only in adopters' setups, where "framework
     ADR NNNN" stays a verbatim token. That keeps ADR 0021's
     disambiguation.
9. **Routing keys (FR-12).**
   - **Shared helper.** `_project_paths.routing_keys(project)` returns
     each role's primary key (`summary`, `not_for`) and its read
     aliases:
     - Defaults: `summary` with alias `resumo`, and `notFor` with alias
       `naoResponde`.
     - A project's `routing_keys` override replaces the primary key, as
       it does today. The aliases stay readable. When a doc has both
       names, the primary one wins.
   - **Hooks.** `frontmatter_check.py` and `claude_md_index_check.py`
     both use the helper. Today the latter hard-codes `resumo` and
     ignores aliases. Nudges name the primary key.
   - **Shipped material.** Every shipped template, workflow doc and
     prompt writes `summary`/`notFor`, which are English keys under
     FR-11. Existing docs are never rewritten.

## Rationale

The model handles only what a program can't, which is carrying meaning
into another language. Everything around it stays deterministic:

- which files need translating (the source hash);
- whether a translation is faithful (the structure and frontmatter
  check);
- where it lands (the rewriter and manifest, both unchanged).

Translating before the rewrite keeps the cache machine-independent. It
also turns the installer's own leftover-placeholder and
unprefixed-command checks into a second fidelity net.

Keying on the English source's hash makes NFR-06 exact in every mode,
including mode B's git merge, where conflict status alone gives the
wrong answer.

An allow-list for translatable frontmatter keeps FR-11's split
fail-safe: a key nobody classified stays invariant instead of being
translated into something no hook can read.

Storing the language in each mode's setup-wide config follows ADR
0013's rule that data lives where its lifecycle lives. Mode B was
already setup-wide in practice: Domain 1 resolved `{{CANONICAL_LANG}}`
once, into the shared commands.

## Consequences

- **Cost.** A non-English setup pays for about 40 files once, then only
  for files that change. The estimate is a heuristic, shown before any
  translation runs.
- **Mixed language, accepted under FR-09.** These stay English:
  - hook messages and generated indexes;
  - the installer's binding block inside the translated registration
    skill, and the namespace README;
  - inline code spans;
  - "framework ADR NNNN";
  - `area` tags, which spec authors must now pick in English.
- **Terminology drift.** Files are translated independently and agree
  only through the term map. The `CLAUDE.md` index fix-up covers
  summaries only.
- **Mode C setting scope.** The `language` setting is user scope, so it
  affects every session on the machine. A repo's own
  `.claude/settings.json` overrides it.
- **Mode C reasoning line.** The subtree `CLAUDE.md` isn't auto-loaded,
  so its reasoning line reaches the model only when a command loads it.
- **Mode C ordering.** The translation step must run before the dry
  run, or the installer refuses. A Domain 6 upgrade of a legacy split
  install is when its user picks a language.
- **Mode B fragility.** The mode B merge flow is the most fragile part:
  - it runs inside an open merge;
  - it needs a known upstream remote;
  - placeholder recovery fails on files edited for other reasons, and
    those files are asked about;
  - a translated `setup-framework.md` drives its own upgrade.
- **AC-07 is not literally achievable.**
  - The shim and the ignored flags keep the split's tests passing.
  - FR-12 changes what `test_pipeline_cost.py` asserts (the
    `` `resumo` `` nudge, and `resumo:`/`naoResponde:` in templates).
    Those assertions move to the new names, and alias tests are added.
    That is a spec-mandated change, not a regression.
  - Removing the shim or the flags later is a separate decision.
- **Literals need a test.** Item 5's English literals must be asserted
  by a test on a Portuguese-shaped spec and reviewer reply, or the
  metrics fail silently.
- **New components.** The `translator` agent and `translation.py`.
  - Like `setup-framework`, the agent is never installed in mode C.
  - `.claude/.translation-staging/` joins
    `.gitignore.framework-additions`.

## References

`evolution/product/specs/0005-project-language.md`,
`evolution/decisions/0001-tooling-agents-commands-skills.md`,
`evolution/decisions/0013-multi-project-ai-repo.md`,
`evolution/decisions/0015-unified-docs-tree-and-layered-constitution.md`,
`evolution/decisions/0017-user-level-install-mechanics.md`,
`evolution/decisions/0019-living-architecture-docs.md`,
`evolution/decisions/0020-proportional-pipeline-cost.md`,
`evolution/decisions/0021-separate-evolution-from-skeleton.md`,
`.claude/scripts/install_user_level.py`, `.claude/scripts/register_project.py`,
`.claude/hooks/_project_paths.py`, `.claude/hooks/validation_sync_check.py`,
`.claude/hooks/pipeline_metrics.py`, `.claude/hooks/frontmatter_check.py`,
`.claude/hooks/claude_md_index_check.py`, `.claude/commands/setup-framework.md`,
`.claude/commands/spec.md`, `.claude/skills/project-registration/SKILL.md`,
`CLAUDE.md.template`, `tests/test_skeleton_boundary.py`,
`tests/test_user_level_install.py`, `tests/test_pipeline_cost.py`
