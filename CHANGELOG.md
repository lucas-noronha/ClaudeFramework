# Changelog

## Unreleased — specs 0001, 0002 and 0003 (2026-10-03)

Three specs written after the first real mode C adoption (2026-09-30),
implemented together:

- [0001 — Mode C hardening](evolution/product/specs/0001-mode-c-hardening.md)
- [0002 — Living architecture docs](evolution/product/specs/0002-living-architecture-docs.md)
- [0003 — Proportional pipeline cost](evolution/product/specs/0003-proportional-pipeline-cost.md)

Decisions: ADR [0017](evolution/decisions/0017-user-level-install-mechanics.md),
[0018](evolution/decisions/0018-constitution-baseline-layer.md),
[0019](evolution/decisions/0019-living-architecture-docs.md),
[0020](evolution/decisions/0020-proportional-pipeline-cost.md), and
[0021](evolution/decisions/0021-separate-evolution-from-skeleton.md) for the split below — accepted 2026-10-03; the three specs are `implemented`.

### Highlights

- **Mode C is now a script, not a prose procedure.**
  `install_user_level.py` installs under a namespace prefix (`/cfw-spec`,
  `cfw-coder`), records a manifest, and is idempotent. `uninstall.py`
  removes exactly what was installed and restores `settings.json` byte
  for byte.
- **Zero footprint in unregistered repos.** Every hook goes through a
  registration gate under a user-level install.
- **Architecture docs get a census engine**, a `draft → active`
  lifecycle, routing frontmatter, and `/update-docs`.
- **`/quick` fast lane**, a build/test gate that skips read-only
  subagents, a validation-summary check that starts nothing unless
  needed, a per-project `review_policy`, and `/metrics`.
- **37 automated tests** (`tests/`) exercise the acceptance criteria in
  throwaway folders.

### Also in this release (outside the three specs)

- **Changed — the framework's own specs and ADRs moved to `evolution/`**
  (framework ADR 0021). The skeleton projects receive is now exactly
  `.claude/`, `docs/`, `CLAUDE.md.template`, `.mcp.json.example` and
  `.gitignore.framework-additions`. `docs/decisions/` ships only the
  0000 template, and `docs/product/specs/` ships empty. Shipped files say
  "framework ADR NNNN" / "framework spec NNNN" instead of a path or a bare
  number that a project's own ADRs would collide with. The installer no
  longer installs framework ADRs, which reverses spec 0001 FR-01's
  "reference ADRs". `evolution/` has a project subtree's shape, so the
  pipeline can run on the framework itself (`register_project.py
  --subtree`). `tests/test_skeleton_boundary.py` enforces the boundary.
- **Fixed — hooks silently ignored non-ASCII paths on Windows.** Every
  hook read stdin with `json.load(sys.stdin)`, which on Windows decodes
  with cp1252. Claude Code sends UTF-8, so a path like
  `...\OneDrive\Área de Trabalho\...` arrived mangled and every
  directory-scoped hook (indexes, guards, status sync, metrics) quietly
  did nothing. All hooks now read stdin through
  `_project_paths.read_hook_input()`, which decodes UTF-8 explicitly.
  Found while verifying the `SubagentStop` fields below; covered by
  `TestRealHookInput`.
- **Fixed — permission and hook-filter rules that never matched**
  (verified 2026-10-03 against Claude Code 2.1.252, in fresh headless
  sessions):
  - The spec-write allow rule was `Write(docs/product/specs/*)` in both
    settings templates, and Claude Code never uses `Write(path)` rules
    for file permission checks. Both now use `Edit(...)`, which covers
    every file-editing tool. The generated mode C rule
    `Edit(//c/.../*/product/specs/*)` matched, in a path with spaces and
    an accent.
  - `settings.example.json` put every `if` on the hook group, where
    Claude Code ignores it, so mode A's 12 filters never filtered
    anything; the hooks stayed correct only because they also self-gate
    in code. Each `if` now sits on its handler, where it works.
- **Changed — `/plan` settles the spec's status.** For a `draft` spec it
  asks "approve now?" (approve and plan / not yet / abandon) and flips
  the frontmatter itself, listing any unchecked stakeholder-validation
  items first. Nobody edits `status: approved` by hand anymore. `/spec`,
  the requirements template and the feature guide say so.
- **Added — a per-machine worktrees root.** `/setup-framework` now asks
  where spec worktrees go: Domain 7 in modes A/B, written to the
  gitignored `.claude/framework.local.json`, or Domain 6's batch in
  mode C (`install_user_level.py --worktrees-root`, kept across
  upgrades). `/worktree` resolves the path with
  `_project_paths.py worktree-path <short-name>` →
  `<root>/<repo folder name>/<short-name>`. With no root set it stays
  `../<short-name>`, as before. Useful for keeping worktrees out of a
  synced folder such as OneDrive. Covered by `tests/test_worktrees_root.py`.
- **Added — worktree sessions in every adoption mode.** A linked
  worktree now resolves to its main checkout from git's own files
  (`_project_paths.py`), so hooks, registration and `framework.local.json`
  work inside it. Handoff is kept per checkout, metrics per project with a
  `checkout` tag so `/metrics` attributes per worktree; `session_brief`
  names repo and branch. New `.claude/scripts/link_worktree.py`
  (`--dry-run`, `--repair`) mirrors mode B's `.claude`/`docs`/`CLAUDE.md`
  links into the worktree; `/worktree` runs it and offers copying
  `settings.local.json` in mode A. Mode C's registration gate opens in a
  worktree of a registered repo. `/setup-framework` Domain 7 checks the
  mode B volume/symlinks. Claude Code's own `--worktree` in mode B lands
  in the AI-repo's `.claude/worktrees/` (now gitignored); `/worktree` is
  the supported path. See
  [spec 0004](evolution/product/specs/0004-worktree-sessions.md) and
  [ADR 0022](evolution/decisions/0022-worktree-sessions.md).
- **Added — one setup language.** `/setup-framework` asks once for the
  language (English first, the default). It governs every artifact the
  pipeline writes, the copied templates, workflow docs, constitution
  layers and the `.claude/` prompts, and the assistant's replies (the
  `language` setting plus a `CLAUDE.md` rule). English costs nothing: files
  are copied as-is. Any other language is translated by the model at setup
  (new `translator` agent, new `translation.py` with `plan`/`check`/`apply`/
  `sync-index`/`recover-placeholders`/`upgrade-plan`/`take-upstream`) and, on
  upgrade, only for files that changed upstream; a file that fails the
  deterministic fidelity check stays English. Frontmatter keys and
  enumerated values, `## Tasks`/`## Reconciliation`, reconciliation phrases
  and `Approved`/`Returned` stay English, so hooks work unchanged (covered by
  `tests/test_portuguese_project.py`). The mode C installer takes
  `--language`/`--language-code`; `.claude/.translation-staging/` is
  gitignored. See
  [spec 0005](evolution/product/specs/0005-project-language.md) and
  [ADR 0023](evolution/decisions/0023-setup-language.md).

### Upgrade notes (read before adopting)

- **The canonical/stakeholder split is retired (ADR 0023).**
  `stakeholder_lang`, the `.validation-<code>.md` companion and the
  validation-summary template are gone, and `validation_sync_check.py` is
  an unwired legacy shim. An existing split keeps working until you pick a
  language; `/setup-framework` offers the migration. No `.validation-*.md`
  file is ever deleted. The default routing keys are now `summary`/`notFor`;
  `resumo`/`naoResponde` are still read as aliases, so no doc needs migrating.
- **Constitution split (ADR 0018).** Principles I–V moved to the new
  `docs/constitution-baseline.md`, and `docs/constitution.md` (now
  version 2.0.0) is the organization/project layer, numbered from VI.
  An existing project keeps working; to adopt the split, add the
  baseline file and remove I–V from your `constitution.md` as a MAJOR
  amendment.
- **Mode A settings changed (ADR 0020).** The gate now runs
  `run_build_test.py`, which reads `build_test_cmd` from the new optional
  `.claude/project-config.json`. The two validation-summary `agent` hooks
  were replaced by the command hook `validation_sync_check.py`. (No
  project had adopted mode A yet, so there is nothing to migrate.)
- **Mode C commands are prefixed** (`/cfw-spec`, ...). The hand-built
  install from 2026-09-30 has no manifest this installer recognizes, so
  remove it with its own uninstaller first. The registry and project
  subtrees are kept and adopted.
- **`settings.multi-project.json.example`** gained `{{PYTHON}}` and
  `{{PROJECTS_ROOT_PERMISSION_PATH}}`. Domain 5 (mode B) resolves them.
- **Line endings:** a new `.gitattributes` (`* text=auto eol=crlf`)
  stores LF in the index and checks out CRLF.

### Spec 0001 — Mode C hardening

Each defect from the first adoption, and where it's fixed:

| # | Defect | Fix |
|---|---|---|
| D1 | `python "~/.claude/hooks/x.py"` — `~` never expands inside quotes | Installer writes absolute, quoted hook paths with an explicit interpreter |
| D2 | Unregistered repos fell back to mode A and got `.claude/` files and `docs/` indexes | `hook_should_run()` gate in `_project_paths.py`; every hook entry point calls it first |
| D3 | `skill_index` globbed personal skills and wrote into `~/.claude/skills/` | Scoped to `<prefix>-*` skills; index written to `<namespace>/skills-index.md` |
| D4 | `spec_index` header links valid only in this repo's layout | Links computed from where the index sits; plain label when the target is absent |
| D5 | `census.sh` hard-coded roots and project list | Census engine driven by the registry plus each project's `census.enabled` (spec 0002) |
| D6 | Command names collided with the user's own | Namespace prefix; every cross-reference rewritten |
| D7 | No manifest, no uninstall | `manifest.json` + `uninstall.py` (dry run by default, byte-exact settings restore, `--restore-retired`) |
| D8 | Domain 6 required Domain 1; per-project hooks can't be shared | No prerequisite; `*.py.example` never installed; new `project_tools.py` runs commands from project config |
| D9 | Literal `{{MAIN_INTEGRATION_BRANCH}}`/`{{DATE}}` reached agents | Runtime tokens defined by the registration skill; `main_integration_branch` in `project-config.json`; dates stamped; installer aborts on leftovers |
| D10 | Spec hook `if` filter and allow rule never matched absolute subtree paths | Hooks self-gate on resolved paths; permission generated as `Edit(//<projects root>/*/product/specs/*)` — `Edit`, because Claude Code ignores `Write(path)` permission rules (verified, see below) |
| D11 | Hook prompt looked for `<subtree>/docs` | Agent hook removed; the pre-check resolves real paths (spec 0003) |
| D12 | Registration inferred locations from folder shape | `framework.json` is the single config source; generated "Install binding" block; `_project_paths.py describe` probe |
| D13 | One constitution file mixed framework and organization principles | Baseline layer (ADR 0018) |
| D14 | An agent reported a gitignored file as "secrets committed" | `coder`/`reviewer` must verify with `git ls-files`/`check-ignore`/`log --all` first |

**Added**
- `.claude/scripts/install_user_level.py`, `uninstall.py`,
  `register_project.py` (single and bulk, FR-11), `migrate_context.py`
  (FR-12).
- `.claude/hooks/project_tools.py`.
- `_project_paths.py`: `framework_config()`, `hook_should_run()`,
  `resolve_shared_docs_root()`, `load_project_config()`,
  `detect_main_branch()`, the `describe` CLI.
- `docs/constitution-baseline.md`.

**Changed**
- `/setup-framework`: Domain 6 rewritten around the installer (plus bulk
  registration and migration); Domain 1's permanent-placeholder list
  extended, and it now writes `.claude/project-config.json`; Domain 5
  resolves the new placeholders and writes `main_integration_branch`,
  `review_policy` and `census`.
- `project-registration` skill: one probe (`describe`), registration via
  script, bulk section, runtime-token definitions, three constitution
  layers.
- `constitution_amendment_check.py` recognizes the baseline file.

### Spec 0002 — Living architecture docs

**Added**
- `.claude/scripts/census.py`: the inventory reads the integration ref
  via read-only git (never the working tree, never `fetch`). It tracks
  drift against the previous run and which docs cite each item, runs
  inline `census-probe` checks for rules and findings, and keeps a ledger
  (watermark, pending, documented).
- `census_extractors/dotnet_layered.py`: handlers, endpoints,
  collections, config keys (resolved through `const`/`static readonly`
  fields), and enum members. Extractor `none` is supported for every
  other stack.
- `/update-docs`: freshness → census → drift → commits since the
  watermark → findings → watermark. `promote <doc>` runs the
  independent `draft → active` verification.
- `docs/workflow/living-architecture-docs.md`: "describing is not
  prescribing", the Pitfall / Convention / Finding markers, no inventory
  numbers in prose, the lifecycle, probes, the ledger.

**Changed**
- Architecture templates and the requirements template carry `resumo`
  and `naoResponde`. The key names are configurable via `routing_keys`.
- `frontmatter_check.py` nudges when an architecture doc has no
  `resumo`. `claude_md_index_check.py` nudges when the CLAUDE.md index
  row differs from it (the doc wins).
- `coder`: `draft` rules are advisory, `active` rules binding; never
  copy a documented deviation; report docs a change makes untrue.
- `reviewer`: advisory vs. blocking by doc status, a separate "rule may
  be stale" finding, and a new doc-verification scope.
- `/implement` step 8: for census projects, update affected docs and
  write a pending ledger entry (never the watermark).
- Domain 4 drafts are written `status: draft`.

### Spec 0003 — Proportional pipeline cost

**Added**
- `/quick`: `triage` on free text. Trivial → `quickfix` + gate, no
  spec, no review. Standard → a one-file lite spec, then `/implement`.
  Structural → the full path.
- `/metrics` and `.claude/scripts/metrics.py`: subagents, gate runs and
  failures, reviewer verdicts and rework per feature, with the fast lane
  and the full path side by side.
- `.claude/hooks/validation_sync_check.py`: a deterministic pre-check
  (language split, approved, requirements hash). It asks for a sync only
  when the requirements actually changed.

**Changed**
- `run_build_test.py` always runs for `coder`/`quickfix`. For any other
  agent it runs only when that agent's transcript shows code edits;
  read-only agents skip it. It logs `gate_run`.
- `pipeline_metrics.py` logs every `subagent_dispatched`, and accepts
  prefixed reviewer names.
- `review_policy` (`per-task` | `final-only` | `structural-only`) is
  honoured by `/implement`. When per-task reviews were skipped, `/review`
  writes the Reconciliation entries itself.
- `triage` is callable outside `/plan` (amends ADR 0004). `quickfix`
  accepts free-text requests.

### Requirement traceability

| Requirement | Where | Verified by |
|---|---|---|
| 0001 FR-01 prefix + rewriting | `install_user_level.py` (`Rewriter`) | `test_ac01_*`, installer self-check |
| 0001 FR-02 manifest + uninstall | `install_user_level.py`, `uninstall.py` | `test_ac03_*`, `test_retire_and_restore` |
| 0001 FR-03 gate | `_project_paths.hook_should_run`, every hook | `test_ac02_*` |
| 0001 FR-04 absolute hook paths | settings template + installer | `test_hook_commands_are_absolute_*` |
| 0001 FR-05 index scoping and links | `skill_index.py`, `spec_index.py` | `test_skill_index_stays_inside_namespace`, `test_registration_creates_subtree_*` |
| 0001 FR-06 no literal placeholders | installer tokens, `main_integration_branch` | `test_ac04_*` |
| 0001 FR-07 Domain 6 without Domain 1 | `project_tools.py`, installer | install tests run on the raw skeleton |
| 0001 FR-08 path-scoped hooks/permissions | self-gating hooks, `permission_path()` | hook-level tests; **Claude Code matching not verified** |
| 0001 FR-09 one config source | `framework.json`, binding block, `describe` | `test_registration_creates_subtree_*` |
| 0001 FR-10 layered constitution | `constitution-baseline.md`, installer policies | `test_ac06_*` |
| 0001 FR-11 bulk registration | `register_project.py --plan` | `test_bulk_registration_*` |
| 0001 FR-12 migration | `migrate_context.py` | `test_ac07_*` (synthetic tree) |
| 0001 NFR-01/03 | hand-edit and collision refusal, idempotency | `test_nfr01_*`, `test_nfr03_*` |
| 0001 NFR-02 verify security claims | `coder.md`, `reviewer.md` | instruction only |
| 0002 FR-01/02 engine, ref not worktree | `census.py`, extractors | `test_ac01_feature_branch_*`, `test_ac02_*`, `test_ac03_*` |
| 0002 FR-03/04 update-docs, ledger | `update-docs.md`, `implement.md`, `census.py ledger` | `test_ac04_*` |
| 0002 FR-05 routing frontmatter | templates, two hooks | `test_ac06_*`, `test_claude_md_row_*` |
| 0002 FR-06/07/09 rule, lifecycle, stale rule | workflow doc, `coder.md`, `reviewer.md`, `update-docs.md` | instruction only |
| 0002 FR-08 rule probes | `census.py` probes | `test_probes_rule_and_finding` |
| 0003 FR-01 fast lane | `quick.md`, `triage.md`, `quickfix.md` | instruction only |
| 0003 FR-02 gate filter | `run_build_test.py` | `TestGateFilter` |
| 0003 FR-03 validation pre-check | `validation_sync_check.py` | `test_ac05_validation_sync_*` |
| 0003 FR-04 review policy | `implement.md`, `review.md` | instruction only |
| 0003 FR-05 metrics | `metrics.py`, `pipeline_metrics.py` | `test_ac05_lanes_side_by_side` |

### Not verified here

- *Verified on 2026-10-03, no longer open:* the generated permission
  `Edit(//c/<projects root>/*/product/specs/*)` matches on Windows, in a
  fresh session with the rule loaded. A deny probe blocked exactly the
  covered paths, and a negative control went through. The original
  `Write(//c/...)` form never matched (see Fixed above).
- *Verified on 2026-10-03, no longer open:* `SubagentStop` input carries
  `agent_id`, `agent_type` and `agent_transcript_path`, as the hooks
  reference documents. A probe hook captured two real stops (`Explore`
  and `general-purpose`), and both transcripts exist and record
  `tool_use` entries in the shape `run_build_test.py` parses. Replaying
  the captured payloads through the gate: Explore → skipped; the writer
  → ran when its file was inside the project, skipped when outside.
- AC-01/AC-05 of spec 0001 end to end inside a real Claude Code session.
  The tests cover them at script and hook level.
- AC-07 on a real context folder. It was tested on a synthetic tree.
- Spec 0002 AC-01/AC-02 on the adopter's real .NET repos. They were
  tested on synthetic repos.
- Behaviour that lives only in agent and command instructions (the
  traceability rows marked "instruction only").
