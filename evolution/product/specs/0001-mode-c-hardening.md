---
doc_type: spec
id: 0001
status: draft
area: adoption-modes
relates_to: []
context_budget: ~2600 tokens
---

# Mode C (user-level) hardening — lessons from the first real adoption

## Feature name

Harden the user-level adoption mode (ADR 0014 mode C) so it installs cleanly on a machine
that already has personal Claude Code config. It must leave zero footprint in unregistered
repos, stay removable, and carry its own fixes back to this repository.

## Business context

Mode C was exercised for the first time on 2026-09-30, on a Windows machine with an existing
`~/.claude` (personal commands, skills, MCP permissions) and five .NET repos. The install
worked only after a series of manual fixes applied to the *installed copy*. Those fixes now
live only under `~/.claude/cfw/` and have not reached this repository. The next adopter would
hit every defect again, and a re-install from this repo would silently undo the fixes on the
first machine.

Defects observed, with where they were fixed (all in the installed copy):

| # | Defect | Effect | Fixed by |
|---|---|---|---|
| D1 | `settings.multi-project.json.example` + Domain 6 step 5 write `python "~/.claude/hooks/x.py"`; bash does not expand `~` inside quotes | every hook fails to start | absolute path at install time |
| D2 | With no registry entry, `_project_paths` falls back to mode A. Under a user-level install this means `session_handoff`/`state_file_path` write `<repo>/.claude/…` and `spec_index`/`decision_index` write `docs/*/README.md` into **any** repo opened | footprint in unrelated repos, contradicting mode C's premise | `_cfw_gate.py`: every hook no-ops unless the project is registered |
| D3 | `skill_index.py` globs every `~/.claude/skills/*` and writes `~/.claude/skills/README.md` | indexes the user's personal skills; writes outside the framework | scoped glob + index inside the namespace |
| D4 | `spec_index.py` README header links `../../decisions/0008-…` and `../requirements-template.md`, valid only in this repo's layout | broken links in every project subtree | links re-pointed |
| D5 | `census.sh`, when adopted, deduced the repos root as `docs/../..` and hard-coded its project list | breaks as soon as the docs root moves | driven by the registry + a per-project `census` flag |
| D6 | Framework command names (`spec`, `plan`, `tasks`, `implement`) collide with the user's existing `~/.claude/commands`. Domain 6 only offers "keep mine" or "rename mine" | either the pipeline or the user's own commands break | installed under a `cfw-` prefix; references rewritten |
| D7 | No manifest and no uninstall path | the framework cannot be removed without archaeology | `manifest.json` + `uninstall.py` (dry-run default; exact `settings.json` restore verified) |
| D8 | Domain 6 prerequisite demands Domain 1 (no `*.py.example`, no placeholders). `auto_format.py` and `dependency_audit.py` are per-project by nature and cannot be resolved into shared machinery | mode C blocked on a step that cannot apply | both excluded from the user-level install |
| D9 | Per-project placeholders stay unresolved in shared files with no runtime resolution: `{{MAIN_INTEGRATION_BRANCH}}` (worktree, implement, review, parallel-work); `{{DATE}}` in shared docs' frontmatter | literal placeholders reach agents | `<main-branch>` + a "detect via `origin/HEAD`" note; dates stamped at install |
| D10 | The validation-summary agent hook and the `Write(docs/product/specs/*)` allow rule use a project-relative pattern. In modes B/C specs are written to an absolute subtree path | the hook never fires; the permission never matches | rewritten to the subtree's absolute pattern (**unverified** that `if` matches `//c/...` on Windows) |
| D11 | The same hook prompt says the mode C docs root is `<subtree>/docs`, contradicting ADR 0015 (no `docs/` level inside a subtree) | the hook looks in a folder that doesn't exist | prompt corrected |
| D12 | `project-registration` locates the shared root and `CLAUDE.md.template` relative to "the registry's `.claude`". That breaks when the registry sits in a namespace folder or `projects_root` is outside `~/.claude` | ambiguous resolution | explicit override block prepended to the installed skill |
| D13 | The shared `constitution.md` is one file mixing the framework's baseline principles (I–V) with the organization's own (VI–XI) | the next framework upgrade either overwrites the org's amendments or never updates the baseline | not fixed |
| D14 | A subagent reported "secrets committed" from a file that is gitignored and was never in history | a false security claim reached the user | caught by a manual `git ls-files`/history check |

## Functional requirements

- FR-01: Mode C installs from this repository with a **namespace prefix** chosen at install
  time (default `cfw`). Agents, commands and skills are prefixed; hooks, registry, scripts,
  templates and reference ADRs live in `~/.claude/<prefix>/`. Every cross-reference
  (commands, `subagent_type`, skill names, paths) is rewritten consistently.
- FR-02: The install writes a manifest of every file created and every `settings.json` entry
  added. A bundled uninstaller removes exactly that, in dry-run by default. It never touches
  the context root's project subtrees, and it lists anything retired at adoption (with
  backups) so the user can restore it.
- FR-03: Every hook in a user-level install is gated: it is a no-op unless
  `CLAUDE_PROJECT_DIR` has a registry entry. No hook may fall back to mode A behaviour under
  mode C (D2).
- FR-04: Hook commands use an absolute interpreter-safe path, never a quoted `~` (D1).
- FR-05: Index hooks (`skill_index`, `spec_index`, `decision_index`) only read and write
  inside the framework's own namespace or the project subtree. Generated links resolve from
  where the index file actually sits (D3, D4).
- FR-06: Placeholders that are per-project are either resolved at runtime from
  `project-config.json` (add `main_integration_branch`, detected at registration) or
  documented as runtime-detected. None may reach an agent as a literal `{{…}}` (D9).
- FR-07: Domain 6 does not require Domain 1. Per-project hooks (`auto_format`,
  `dependency_audit`) move to a per-project opt-in, driven by `project-config.json`, rather
  than shared machinery (D8).
- FR-08: Path-scoped hooks and permissions in modes B/C are generated against the resolved
  subtree path, and verified to match on each OS (D10, D11).
- FR-09: `project-registration` receives the registry, shared root, projects root and
  template locations from one config source written at install. Nothing is inferred from
  folder shape (D12).
- FR-10: The constitution is layered as framework baseline (upgraded with the framework,
  never hand-edited) → organization/shared (amended via Governance) → project (additive).
  An upgrade replaces only the baseline layer (D13; extends ADR 0015).
- FR-11: Bulk registration: register N existing repos in one pass, reusing the lazy
  registration's questions once for shared answers (build command, languages).
- FR-12: A "migrate existing context" path that imports an existing doc base into the ADR 0015
  layout, preserving bodies, without destroying the source:
  - map old folders to `architecture/`, `product/specs/` and `decisions/`;
  - number specs per project;
  - rename frontmatter keys to the framework's;
  - rewrite every relative link;
  - verify zero broken links.

## Non-functional requirements

- NFR-01: Every fix applied to an installed copy lands in this repository first, with an ADR
  where it changes a decision. A re-install must never regress a machine (the divergence
  that exists today).
- NFR-02: A security-relevant finding from any agent (committed secret, leaked credential)
  is verified against git (`ls-files`, `check-ignore`, history) before it is reported as
  fact (D14).
- NFR-03: The install is idempotent, and it refuses to overwrite on any collision.

## Explicitly out of scope

- Modes A and B, except where a shared file (hook, template) is fixed for all modes.
- Supporting a relocated `CLAUDE_CONFIG_DIR` beyond the existing stop-and-ask.

## Roles and permissions involved

Framework maintainer (owns this repo); adopting developer (runs the install on their machine).

## Related specs

- 0002-living-architecture-docs — relationship: shares the census adoption (D5), which 0002
  generalizes.
- 0003-proportional-pipeline-cost — no direct overlap, same install surface.

## Acceptance criteria

- [ ] AC-01: A fresh install on a machine with colliding personal commands completes with no
      overwrite and no manual edits. `/<prefix>-spec` runs end to end.
- [ ] AC-02: Opening an unregistered repo and editing files leaves `git status` of that repo
      unchanged, and nothing is written outside the namespace and the context root.
- [ ] AC-03: Uninstall followed by a byte comparison restores `settings.json` exactly. No
      `<prefix>-*` file remains; project subtrees are untouched.
- [ ] AC-04: No installed file contains an unresolved per-project `{{…}}` placeholder. Only
      the explicitly permanent ones listed in Domain 1 step 1 may remain.
- [ ] AC-05: The validation-summary hook fires on an approved spec edit in a mode C subtree
      (currently unverified).
- [ ] AC-06: Upgrading the framework replaces the constitution's baseline layer and leaves
      the organization layer byte-identical.
- [ ] AC-07: The migration path, run on a copy of a real context folder, reports zero broken
      links and zero docs missing `doc_type`/`status`/`context_budget`. The source stays
      unchanged.

## Impact on existing architecture

- Amends ADR 0014 (mode C mechanics: prefix, gate, manifest) and ADR 0015 (layered
  constitution gains a baseline layer).
- Changes `/setup-framework` Domain 6 and `settings.multi-project.json.example`.
- Replaces the ad-hoc install/migration scripts used on 2026-09-30 with framework-owned ones.

## Reconciliation
