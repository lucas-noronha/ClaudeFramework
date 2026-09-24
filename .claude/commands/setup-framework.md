---
description: Single entry point for adopting or maintaining this framework in a project — bootstrapping CLAUDE.md and settings from the copied skeleton, installing recommended global plugins, merging framework scaffolding files into this repo without clobbering what's already there, and optionally drafting the architecture blank slots from the existing codebase's own detected patterns. Add new setup domains here as the framework grows rather than creating a new top-level command per domain.
---

Each domain below either changes this repo's own files (bootstrap,
scaffolding, architecture drafts) or global, machine-wide state
(plugins) — say which, and never write anything without the user
confirming that specific item first. Go through each domain in order;
skipping or declining one never blocks another. Run this right after
copying `.claude/`, `docs/`, `CLAUDE.md.template`, `.mcp.json.example`,
and `.gitignore.framework-additions` into a new project's root — that's
the whole "adopt this framework" step besides this command and,
if Domain 4 doesn't cover it, filling in the two architecture blank
slots by hand.

## Domain 1 — Bootstrap this project from the copied skeleton

Goal: resolve every `{{PLACEHOLDER}}` in the copied skeleton to a real
value, consistently across every file it appears in, then rename the
template/example files that are ready to become the real thing.

1. Find every placeholder: `grep -rn "{{[A-Z_]*}}" .claude docs
   CLAUDE.md.template` (adjust the tool to whatever's available).
   **Exclude these from everything below — they're permanent, not
   placeholders awaiting a one-time fill:**
   - `docs/decisions/0000-adr-template.md` — a copyable skeleton future
     ADRs are born from; its own `{{DATE}}` must stay literal.
   - `{{TERM}}` in `docs/glossary.md.template` — delete that whole
     example row instead of filling it (the file already says so).
   - `{{AZURE_DEVOPS_ORG}}` / `{{AZURE_DEVOPS_PAT_ENV_VAR}}` in
     `docs/workflow/plugin-integrations.md` — a copy-paste example for
     *if* the user adds that MCP later, not this project's own value.
2. Resolve each remaining placeholder's value, detecting from the
   repo before asking (show detected values for confirmation rather
   than silently trusting them):
   - `{{PROJECT_NAME}}` — repo root folder name, or the `name` field
     from a `package.json`/`.csproj` if one exists at the root.
   - `{{MAIN_INTEGRATION_BRANCH}}` — `git symbolic-ref
     refs/remotes/origin/HEAD` or the current branch; fall back to
     asking if there's no git remote yet.
   - `{{BACKEND_DIR}}` / `{{FRONTEND_DIR}}` — look for common split
     names (`backend`/`api`/`server` vs `frontend`/`client`/`web`) or
     a `.sln`/`package.json` at a subfolder root. If the project isn't
     a monorepo, say so and follow this framework's own guidance to
     delete the split (both placeholders, and the doc sections that
     only make sense with one) instead of forcing a value.
   - `{{BUILD_TEST_CMD}}` — detect `.sln`/`.csproj` → `dotnet test`;
     a `package.json` `test` script → `npm test`; both → chain them
     (`dotnet test {{BACKEND_DIR}} && npm --prefix {{FRONTEND_DIR}}
     test`, per `docs/workflow/feature-development-guide.md`); neither
     → ask.
   - Ecosystem-specific commands inside
     `.claude/hooks/dependency_audit.py.example`'s `MANIFEST_COMMANDS`
     map — delete the entries for ecosystems this project doesn't have
     (e.g. drop the `Cargo.toml`/`go.mod` rows on a project with no Rust
     or Go); the ones that stay use the same `{{SOLUTION_FILE}}` value
     already resolved above, nothing new to ask for there.
   - `{{SOLUTION_FILE}}` — the `.sln` filename found, if any.
   - `{{FRONTEND_LINTER}}` — detect an eslint/prettier/biome config
     file; otherwise ask.
   - `{{CANONICAL_LANG}}` — ask, default suggestion English.
   - `{{STAKEHOLDER_LANG}}` / `{{STAKEHOLDER_LANG_CODE}}` — ask, with
     "same as canonical — skip the split" as an explicit option; if
     chosen, set both to the canonical language/code (the
     canonical/stakeholder split's own steps already no-op when
     they're equal).
   - `{{ONE_TO_TWO_SENTENCE_PROJECT_DESCRIPTION}}`,
     `{{FRONTEND_STACK}}`, `{{BACKEND_STACK}}`, `{{DATABASE}}`,
     `{{AUTH_PROVIDER}}`, `{{ONE_LINE_SYSTEM_SHAPE}}` — try a light
     detection pass (package.json/.csproj dependencies) as a
     suggestion, but ask to confirm; these are easy to get
     confidently wrong from file scanning alone.
   - `{{OTHER_TOP_LEVEL_DIR}}`, `{{ANY_OTHER_CROSS_CUTTING_CONCERN}}` —
     ask only if relevant; both sections say to delete them if they
     don't apply, so offer that as the default.
   Batch these into a small number of `AskUserQuestion` calls — don't
   ask one at a time for a dozen fields.
3. `{{DATE}}` — today's date, everywhere it appears (including inside
   `docs/decisions/0001-*.md` and `0002-*.md`'s own frontmatter — safe
   before any hook is wired up; **never** inside `0000-adr-template.md`,
   per the exclusion above).
4. Apply every resolved value across **all** files it appears in
   (e.g. the same `{{PROJECT_NAME}}` in `CLAUDE.md.template` and in
   `docs/decisions/0001-*.md`) — a value filled in one place and left
   as a literal placeholder in another is worse than not filling it at
   all, since it looks resolved at a glance.
5. Rename the files that are now ready to stop being templates (moving
   the content, not copying — the `.template`/`.example` name should
   stop existing once this runs):
   - `CLAUDE.md.template` → `CLAUDE.md`
   - `.claude/settings.example.json` → `settings.json`
   - `.claude/hooks/auto_format.py.example` → `auto_format.py`
   - `.claude/hooks/dependency_audit.py.example` → `dependency_audit.py`
     (after trimming `MANIFEST_COMMANDS` per step 2 above)
   - `docs/architecture/overview.md.template` → `overview.md`
   - `docs/glossary.md.template` → `glossary.md` (also delete the
     `{{TERM}}` example row per step 1)
6. **Do not** rename or fill
   `docs/architecture/module-structure.md.template` and
   `frontend.md.template` **in this domain** — resolving placeholders
   is one-shot, objective substitution; describing a project's real
   dependency rules is a standing judgment call, a different kind of
   work entirely. Domain 4 below can draft these from the existing
   code, but only as a draft a human still has to read — never treat
   this step as having finished them. If Domain 4 doesn't run (declined,
   or nothing to detect), flag both files clearly in the close-out
   summary as the manual step left before `/spec`.
7. Re-run the grep from step 1 over the renamed set — if anything
   still matches outside the excluded files, that's a bug in this
   domain, not something to leave for the user to find later.

## Domain 2 — Global plugins

1. Read `docs/workflow/plugin-integrations.md` for the current Core
   and Optional lists.
2. Read `~/.claude/settings.json` (expand `~` for the current OS) and
   check its `enabledPlugins` map for which Core plugins are already
   enabled.
3. If every Core plugin is already enabled, say so and move to the
   next domain.
4. Otherwise, use `AskUserQuestion` (multi-select) listing exactly the
   missing Core plugins, each with the one-line "what it gives you"
   from the catalog table — let the user pick any subset, or none. If
   `superpowers` is among the missing ones, list it first: per
   `docs/decisions/0003-superpowers-sdd-wrapping.md` it now backs a
   complementary pass across nearly the whole SDD lifecycle (`/spec`,
   `/tasks`, `coder`/`quickfix`, `/review`, `/worktree`), not just
   `coder` — worth calling out even to a user who'd otherwise skip the
   batch.
5. For each plugin the user selected, run:
   `claude plugin install <name>@claude-plugins-official -y`
   (default scope is `user`, i.e. every project on this machine — do
   not pass `--scope project` or `--scope local` here, that would
   contradict what was asked for). Report success/failure per plugin
   plainly; a failure for one plugin doesn't block installing the
   others.
6. Re-run the same file-extension scan `plugin_gap_check.py` does (or
   just note its last session-start suggestion, if any) and mention any
   Optional, language-specific plugin relevant to this repo that isn't
   enabled. Use `AskUserQuestion` with three options per plugin:
   **Install**, **Not now**, or **Don't ask again** — the third one
   writes the plugin's name into the `dismissed` array of
   `.claude/.plugin-gap-dismissed.json` (create the file with
   `{"dismissed": []}` first if it doesn't exist yet) so
   `plugin_gap_check.py` stops suggesting it every session. Keep this
   separate from the Core batch since it's situational, not universal.
7. For Optional entries that are MCP servers rather than marketplace
   plugins (e.g. `azure-devops`) — never attempt to install or
   configure these automatically, they need org-specific values (a
   PAT, an org name). Point at the copy-paste example in
   `docs/workflow/plugin-integrations.md` instead and let the user add
   it to their own `.mcp.json`.

Declining everything in this domain is a valid outcome — every Core
plugin's value has a written fallback in
`.claude/skills/plugin-awareness/SKILL.md`, so nothing in the pipeline
degrades.

## Domain 3 — Merge framework scaffolding files into this repo, then clean up

This framework ships a couple of files most real projects already have
one of (`.gitignore`, `.mcp.json`). They're named so copying the
framework skeleton in never silently overwrites yours
(`.gitignore.framework-additions`, `.mcp.json.example`) — this domain
does the merge instead of you doing it by hand, then removes the
now-redundant source file. Leaving `.gitignore.framework-additions` or
`.mcp.json.example` sitting in the project after this domain runs is a
bug in it, not an acceptable leftover.

1. **`.gitignore`**: if the repo has no `.gitignore` yet, rename
   `.gitignore.framework-additions` to `.gitignore` directly (nothing
   left to delete separately — the rename already removes the source
   name). If one already exists, append only the lines from
   `.gitignore.framework-additions` that aren't already present
   (compare trimmed lines, ignore comment lines when checking for
   duplicates) under a `# Claude Code framework` header, then delete
   `.gitignore.framework-additions` — its content now lives in the
   real file, keeping both is redundant and stale the moment one
   diverges from the other.
2. **`.mcp.json`**: if the repo has no `.mcp.json` yet, rename
   `.mcp.json.example` to `.mcp.json` directly. If one already exists,
   parse both as JSON and merge — add any `mcpServers` entry from the
   example whose key isn't already present in the real file (never
   overwrite an existing server entry with the same name — the user's
   own config wins), then delete `.mcp.json.example`. If the JSON in
   either file doesn't parse, stop and report it instead of guessing
   or deleting anything.
3. Before writing anything in this domain, use `AskUserQuestion` to
   confirm — show exactly what would be added (the new lines, the new
   `mcpServers` keys) so the user approves the actual diff, not a
   vague "merge scaffolding?" prompt.
4. Skip a file entirely if there's nothing to add (already fully
   covered) — say so, don't ask about a no-op. Still delete the source
   `.example`/`.framework-additions` file in that case too, once its
   content is confirmed already present in the real file.

## Domain 4 — Architecture anamnesis (optional, draft only)

Goal: give the two architecture blank slots a real, project-specific
starting draft when there's existing code to describe — never a
finished document, never a guess presented as settled. See
`docs/decisions/0006-architecture-anamnesis.md` for why this is safe
where an earlier version of this framework's guessed-architecture
approach wasn't: the earlier one shipped one fixed opinion as this
framework's own default; this one describes *this* project's own code
and stays a draft until a human reads it.

1. Skip this whole domain, silently, if
   `docs/architecture/module-structure.md.template` and
   `frontend.md.template` no longer exist (Domain 1 already resolved
   them) or already contain real content someone wrote by hand — never
   overwrite either case.
2. Otherwise, ask (`AskUserQuestion`) whether to run it: reading a
   sample of the existing codebase to draft these has a real token
   cost, and is pointless on a scaffold with no code yet. If declined,
   stop here — Domain 1 step 6's fallback (flag both files in the
   close-out) applies.
3. If accepted, for each side that exists (`{{BACKEND_DIR}}`,
   `{{FRONTEND_DIR}}`, or the repo root if it isn't a monorepo):
   - Detect the top-level layout and naming conventions already in use
     (e.g. `controllers`/`services`/`repositories`, feature folders,
     `components`/`pages`/`hooks`).
   - Sample a handful of representative files per detected layer — not
     an exhaustive read — and check their actual imports to state the
     dependency direction observed (e.g. "controllers import services,
     never the reverse"), citing the specific files checked as
     evidence, not asserting it as a proven universal rule.
   - If nothing coherent is detectable (genuinely empty scaffold, or
     patterns too inconsistent to state a rule from), say so plainly
     and stop for that side — leave its file as the original blank
     slot, don't force a draft where there's nothing real to describe.
4. Where a real pattern was found, fill `module-structure.md`/
   `frontend.md`'s "Layout" / "Dependency rules" / "Where new code
   goes" sections from it and rename `.template` → `.md` (move the
   content, don't leave the template file behind — same convention as
   Domain 1). Prepend this exact banner right after the frontmatter,
   before the first heading:

   ```text
   > **Detected automatically from existing code on {{DATE}} — read
   > fully and correct anything wrong before trusting this. `coder` and
   > `reviewer` treat this file as ground truth.**
   ```

5. Never mark this done the way Domain 1's placeholders are done —
   this is a draft, not a resolved value. Say so explicitly in the
   close-out (see below).

<!--
## Domain N — <name>

Add a new numbered domain here the next time this framework grows
another optional capability worth a one-time or occasional setup step
— machine-level (a new plugin category) or repo-level (another
scaffolding file to merge, a hook toggle, etc.). Keep each domain
self-contained: its own check, its own `AskUserQuestion`, its own
confirm-before-acting gate, and a written fallback elsewhere (a skill,
a doc) for what happens if the user declines. Don't create a new
top-level command for it — that's exactly the kind of one-off
proliferation this command exists to avoid.
-->

## Close

End with a one-line summary per domain covered: what got filled in/
installed/merged, what was declined, what was already covered, and —
loudest of all — the state of the two architecture files:

- If Domain 4 didn't run (declined, or nothing to detect): they're
  still blank slots to fill by hand before the first real `/spec`, same
  as always.
- If Domain 4 drafted them: say so plainly, and that they're a
  **draft from detected patterns, not a finished document** — the user
  needs to read and correct `module-structure.md`/`frontend.md` before
  `coder`/`reviewer` start trusting them, same urgency as the
  fill-by-hand case, not less.
