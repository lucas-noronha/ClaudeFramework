---
doc_type: adr
id: 0017
status: accepted
date: 2026-10-03
supersedes: null
superseded_by: null
context_budget: ~1300 tokens
---

# ADR 0017 — Mode C installs through a script: namespace prefix, registration gate, one config source, manifest and uninstall

Like ADR 0001–0016, this documents a decision about *this framework's
own* tooling. **Amends ADR 0014's mode C mechanics**; 0014's decision —
three upfront modes, lazy registration — stands unchanged.

## Context

Mode C was first used for real on 2026-09-30, on a Windows machine with
personal `~/.claude` commands and five .NET repos
(`evolution/product/specs/0001-mode-c-hardening.md`). Domain 6, as written,
produced a broken install that only worked after hand-fixes to the
installed copy: hook commands with a quoted `~` that bash never expands
(D1); hooks falling back to mode A in every unregistered repo and writing
`.claude/` files and `docs/` indexes into it (D2); a skill index that
globbed the user's personal skills (D3); index links valid only in this
repo's layout (D4); command names colliding with the user's own (D6); no
way to uninstall (D7); a Domain 1 prerequisite that could never be met
for per-project hooks (D8); literal per-project placeholders reaching
agents (D9); path-scoped hook filters and permissions that never match
an absolute subtree path (D10/D11); and a registration skill inferring
the shared root from folder shape (D12). The fixes lived only on that
machine, so a re-install from this repository would have silently undone
them.

The common cause: Domain 6 described a multi-step file merge in prose
and left an agent to perform it. Every one of those steps had an exact,
checkable right answer.

## Options considered

- **Patch Domain 6's prose for each defect.** Rejected: twelve more
  instructions for an agent to follow exactly, on every machine, with no
  way to verify the result or to undo it.
- **Keep unprefixed names, and resolve collisions by asking per file**
  (Domain 6's "keep mine / rename mine"). Rejected: either the user's
  commands or the pipeline break, by construction.
- **A deterministic installer script, run from this repository, with a
  namespace prefix, a manifest, an uninstaller, and a gate in the shared
  path helper (chosen).**

## Decision

- **`.claude/scripts/install_user_level.py`** performs the whole mode C
  install. Domain 6 asks the questions, shows its dry run, and runs it
  with `--apply`. It is idempotent, it aborts before writing anything on
  a destination it doesn't own, and it refuses to overwrite an installed
  file edited since install: a fix belongs in this repository first.
- **Namespace prefix** (default `cfw`): agents, commands and skills are
  installed as `<prefix>-<name>`. Hooks, scripts, the registry, templates
  and the shared `docs/` root live in `~/.claude/<prefix>/`. (This
  framework's own ADRs were also installed there as reference until ADR
  0021 kept them out of every install.) The installer rewrites every
  cross-reference: slash commands, backticked agent and skill names,
  `applies_to`, machinery paths, and shared-doc paths made absolute.
- **`framework.json`** in the namespace is the single config source:
  install mode, prefix, registry, shared root, projects root, template
  and scripts locations. `_project_paths.py` reads it before any
  inference. The installed `project-registration` skill gets the same
  values in a generated "Install binding" block, and
  `python _project_paths.py describe` prints the whole resolution for
  commands. Hooks and commands share one implementation.
- **Registration gate.** `hook_should_run()`: under a user-level install,
  every hook is a no-op unless `CLAUDE_PROJECT_DIR` is registered. Modes
  A and B are unaffected (no `framework.json`, gate always open).
- **Manifest + uninstaller.** Every file written is recorded with its
  hash, and every `settings.json` addition is recorded exactly.
  `scripts/uninstall.py` (dry run by default) removes only unchanged
  files, restores `settings.json` byte for byte from the pre-install copy
  when nothing else changed, keeps the registry and project subtrees, and
  lists anything retired at install with a restore option.
- **Absolute, interpreter-explicit hook commands**
  (`<python> "<abs hooks>/x.py"`), and a spec-write permission generated
  against the absolute projects root in Claude Code's `//` form
  (`Edit(//c/...)` on Windows). The multi-project settings template gains
  `{{PYTHON}}` and `{{PROJECTS_ROOT_PERMISSION_PATH}}` beside
  `{{HOOKS_DIR}}`.
- **Per-project values never reach an agent as a placeholder.** In
  installed shared files they become runtime tokens
  (`<main_integration_branch>`, `<canonical_lang>`, ...) the registration
  skill defines. `main_integration_branch` joins `project-config.json`,
  detected from `origin/HEAD` at registration. Dates are stamped. The
  installer verifies the result and aborts on anything left.
- **Per-project hooks become config.** `*.py.example` hooks are never
  installed; `project_tools.py` runs the formatter and dependency-audit
  commands a project declares in its config, so Domain 6 no longer
  depends on Domain 1.
- **Registration and import get scripts.** `register_project.py` does
  lazy registration's deterministic part, one repo or a bulk plan.
  `migrate_context.py` imports an existing doc base into the ADR 0015
  layout, never modifying the source, and verifies its links and
  frontmatter.

## Rationale

Each defect had one right answer a program can compute and test.
Moving them from instruction to code makes the install verifiable
(`tests/test_user_level_install.py` exercises every acceptance criterion
against a throwaway config directory), reversible, and identical on
every machine. The prefix removes the collision class outright instead
of negotiating it per file. One config source ends the
"infer from folder shape" bugs.

## Consequences

- Commands are `/cfw-spec`, `/cfw-quick`, ... under a user-level install.
  Docs written for modes A/B say `/spec`; the installer rewrites the
  installed copies, not this repository.
- A user-level install now needs a framework checkout to install or
  upgrade from. Uninstall works without one.
- The old un-namespaced mode C layout (`~/.claude/projects.local.json`,
  `~/.claude/docs`) is still read by `_project_paths.py`, but the
  installer doesn't migrate it. The hand-built 2026-09-30 install must be
  removed with its own uninstaller before installing.
- `__pycache__` appears inside the namespace once hooks run. That's
  inside the namespace by design, and the uninstaller removes it.
- **Verified 2026-10-03** (Claude Code 2.1.252, fresh headless
  sessions): the generated permission matches on Windows **as
  `Edit(//c/...)`**. Claude Code never uses `Write(path)` permission rules
  for file checks, so both settings templates now allow spec writes with
  `Edit(...)`, which covers every file-editing tool. The `SubagentStop`
  fields were verified the same day (see ADR 0020). AC-05 itself is
  exercised at hook level by tests.
- Mode B keeps resolving the AI-repo's own `{{MAIN_INTEGRATION_BRANCH}}`
  statically via Domain 1. Out of spec 0001's scope; same runtime fix
  would apply.

## References

`evolution/product/specs/0001-mode-c-hardening.md`,
`evolution/decisions/0014-setup-framework-adoption-modes.md`,
`evolution/decisions/0015-unified-docs-tree-and-layered-constitution.md`,
`evolution/decisions/0018-constitution-baseline-layer.md`,
`.claude/scripts/install_user_level.py`, `.claude/scripts/uninstall.py`,
`.claude/hooks/_project_paths.py`, `.claude/commands/setup-framework.md`
