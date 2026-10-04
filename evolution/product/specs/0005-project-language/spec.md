---
doc_type: spec
id: 0005
status: implemented
area: localization
relates_to: []
resumo: How does one language, chosen at setup, govern every artifact the framework writes or copies (docs, templates, agent prompts) and the assistant's replies?
naoResponde: How hooks, scripts and census internals are written. They stay as is.
context_budget: ~1300 tokens
tier: structural
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

