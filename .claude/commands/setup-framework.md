---
description: Single entry point for adopting or maintaining this framework in a project — opens by choosing one of three mutually exclusive adoption modes (direct in-repo, external AI-repo, or user-level multi-project), then runs only that mode's
domains: bootstrapping CLAUDE.md and settings from the copied skeleton, installing recommended global plugins, merging framework scaffolding files into this repo without clobbering what's already there, optionally drafting the architecture blank slots from the existing codebase's own detected patterns, linking a separate target code repo to this AI-repo with zero footprint there (Domain 5), or merging the machinery into `~/.claude` for every project on this machine (Domain 6), and choosing the per-machine folder spec worktrees are created under (Domain 7). Add new setup domains here as the framework grows rather than creating a new top-level command per domain.
---

**Start with the adoption-mode question below — it decides which
domains run at all.** Each domain either changes this repo's own files
(bootstrap, scaffolding, architecture drafts), global machine-wide
state (plugins), or — Domains 5 and 6 only — a *different*,
user-supplied repo path, or this machine's user-level `~/.claude`
directory. Say which, and never write anything without the user
confirming that specific item first. Within a chosen mode, go through
its domains in order; skipping or declining one never blocks another.

For mode A (Domains 1-4), run this right after copying `.claude/`,
`docs/`, `CLAUDE.md.template`, `.mcp.json.example`, and
`.gitignore.framework-additions` into a new project's root — that's the
whole "adopt this framework" step besides this command and, if Domain 4
doesn't cover it, filling in the two architecture blank slots by hand.
For modes B and C, skip that copy step entirely: both run from *this*
repo, already fully set up, and reach a target repo without copying
anything into it.

## Adoption mode — ask this first, before any domain

Goal: settle the one thing that decides *where this framework's
machinery physically lives*, before anything writes a file. Per
framework ADR 0014 the three
shapes below are mutually exclusive, whole-repo commitments — not
optional add-ons to each other like Domains 2-4 — and running two of
them against the same repo is exactly the failure this question exists
to prevent.

**A wrong choice here is expensive to undo**, so explain the
trade-offs rather than listing three labels: switching later means
physically moving `docs/product/specs/`, `docs/decisions/` and
`CLAUDE.md` between a repo root, a cloned AI-repo and a user-level
projects root, re-resolving placeholders against a different repo, and
creating or tearing down links in every target repo pointing at the old
layout. Say that out loud when you ask.

1. **Detect what's already chosen and offer it as the default** rather
   than asking cold — re-running this command on an already-adopted
   setup is normal, and re-asking blind invites answering differently
   by accident:
   - a real `CLAUDE.md` and `.claude/settings.json` in *this* repo,
     with no `.claude/projects.local.json` → mode A, already
     bootstrapped here.
   - `.claude/projects.local.json` in this repo (and, beside it, one or
     more per-project subtrees at `docs/<name>/`) → mode B; this repo
     is already acting as an AI-repo.
   - `~/.claude/<prefix>/framework.json` with `install_mode: user-level`
     (expand `~` for the current OS; the prefix is usually `cfw`) →
     mode C is already installed on this machine, and this run is an
     upgrade. A bare `~/.claude/projects.local.json` with no namespace
     is a pre-ADR-0017 install: say so (see Domain 6's last paragraph).
   - Several at once → say so plainly and ask which one this run is
     about; never assume.
2. Ask with a single `AskUserQuestion` (one question, three options),
   giving each option its real cost, not just its name:

   - **(A) Direct in-repo — the skeleton lives in the code repo
     itself.** The `.claude/`, `docs/` and `CLAUDE.md.template` copied
     into this repo's root get bootstrapped in place. *Cost:* every
     Claude-related file is committed in the code repo's own git
     history, and the setup is per repo — a second project repeats the
     whole thing, and the two copies drift apart independently from
     then on. *Pick it when:* nothing forbids Claude files in the code
     repo and you're setting up one project.
   - **(B) External AI-repo — machinery in a separate repo, reached by
     links.** This repo stays the **AI-repo**; a separate target code
     repo gets three never-committed links (`.claude`, `docs`,
     `CLAUDE.md`) pointing back here. One AI-repo backs any number of
     target repos through per-project subtrees nested inside one
     shared `docs/` tree, at `docs/<name>/` (framework ADR 0013, layout per
     framework ADR 0015).
     *Cost:* the links are per machine and per clone — every
     developer, and every fresh checkout, must re-run Domain 5 before
     hooks route correctly; and both repos must sit on one filesystem
     (one drive letter on Windows) sharing a common ancestor
     directory. *Pick it when:* the code repo must carry zero
     Claude footprint in its history, and you want the framework
     itself versioned and shared with a team.
   - **(C) User-level, multi-project — machinery in `~/.claude`, no
     links anywhere.** `agents/`, `commands/`, `skills/`, `hooks/` and
     `settings.json` are merged into `~/.claude/`, which Claude Code
     loads for every session on this machine, so no target repo gets a
     link, a file, or any footprint at all. Individual projects
     register themselves lazily, the first time a pipeline command
     needs one. *Cost:* it's machine-wide and per developer — a
     teammate gets none of it — and nothing is versioned by default,
     so the machinery *and* (with the default projects root) every
     spec and ADR sit outside git unless you point the projects root
     at a folder you already version or sync. A relocated
     `CLAUDE_CONFIG_DIR` also puts `~/.claude` out of Claude Code's
     reach, which mode C cannot detect from inside a hook (framework ADR 0014).
     *Pick it when:* you want one setup covering every repo you touch
     on this machine, with no per-repo step at all.

3. Route on the answer, and run nothing else:
   - **A** → Domains 1-4, in order, exactly as written below. Nothing
     in them changes for this mode.
   - **B** → Domain 5.
   - **C** → Domain 6.
4. Domain 2 (global plugins) is the one exception to that routing:
   enabled plugins are per machine, not per repo, so offer it in *any*
   mode — after that mode's own domains in B and C.
5. Domain 7 (where spec worktrees live) closes modes A and B. Mode C
   asks the same question inside Domain 6's batch instead, because there
   the installer owns the config file it lands in.
6. An **upgrade** of an already-adopted setup, or **migrating** a setup
   `describe` reports with `legacy_split: true`, goes to "Upgrading and
   migrating" at the end of this command instead of the domains above.

## Setup language — one question, one translation pass (Domains 1, 5, 6)

Goal: one language per setup (framework spec 0005, framework ADR 0023).
It governs every artifact the framework generates or copies and the
assistant's replies. Domains 1, 5 and 6 reference this section instead
of repeating it; the upgrade flows below reuse its translation steps.

**Ask** (`AskUserQuestion`, one question): the setup language as name +
BCP 47 code, **English first and default** (`English`/`en`), plus the
user's own choice (e.g. `Portuguese`/`pt-BR`). In modes B and C it
covers every project behind the setup: registering or linking another
project never asks again. English (`en`, `en-*`) needs **no translation
pass and no record**: the copied files stay as they are.

**Translate** (non-English only). `translation.py` below is
`.claude/scripts/translation.py` of the checkout this run is from. It
never calls a model; the `translator` agent does, and Python checks.

1. **Pristine sources.** Translation always starts from untouched
   English, never from a previous translation or resolved text.
   - Mode A: before any placeholder is resolved, snapshot the copied
     `.claude/`, `docs/` and `CLAUDE.md.template` into
     `.claude/.translation-staging/en/` (same relative paths). `--source`
     below is that folder. The staging folder is gitignored.
   - Mode B: snapshot upstream's files the AI-repo was cloned from with
     `git archive <upstream ref> .claude docs CLAUDE.md.template` into
     the same folder; confirm the ref (`AskUserQuestion`).
   - Mode C: `--source` is this repository checkout; staged output goes
     to `.claude/.translation-staging/out/`. Only what the installer
     reads matters: `.claude/agents|commands|skills`, `docs/` and
     `CLAUDE.md.template`, never `translator.md` or `setup-framework.md`,
     which it does not install, and nothing under `evolution/`.
   The record is `--record .claude/translation-record.json` (modes A/B,
   committed) or `<namespace>/translations/record.json` (mode C).
2. **Plan and cost.** `python translation.py plan --source <src>
   --record <record> --language-code <code>` plus
   `--keep docs/constitution.md --keep docs/glossary.md.template` (user
   layers, translated only on create). Keep only the in-scope paths,
   sum their `estimated_tokens` and **state that estimate** (heuristic
   `token_heuristic`, `translator` runs on a cheaper model, about 40
   files). `AskUserQuestion`: translate, pick English instead, or pick
   another language. Nothing is translated before this confirmation.
3. **Term map first.** Draft framework vocabulary → target terms (spec,
   plan, tasks, ADR, constitution, worktree, census, reconciliation,
   review, drift, ...), show it, confirm it, and save it as
   `.claude/.translation-staging/terms.json`. Every batch gets it.
4. **Translate.** Dispatch the `translator` agent in parallel batches
   (a handful of files each, balanced by estimated tokens), giving
   each: the language, `terms.json`, the staging folder
   (`.claude/.translation-staging/out/`), and its files. It never edits
   sources. Translate `.claude/commands/setup-framework.md` itself last
   in mode A and B (this very file is being read).
5. **Check each staged file:** `python translation.py check --source
   <src>/<path> --translated <out>/<path>`. A failed or skipped file
   **stays English**: `apply --status english --reason "<the check's
   reason>"` (no `--staged`), and say so in the close-out.
6. **Apply** each passing file, **one at a time**: `python
   translation.py apply --source <src> --record <record> --language
   <name> --language-code <code> --path <path> --staged <out>/<path>
   --terms .claude/.translation-staging/terms.json` with
   `--policy keep` for the two user-layer files above.
   - Modes A/B add `--dest <the file's path in the repo>`: mode A
     writes in place over the copied English, mode B over the AI-repo's
     file (use its current, renamed name).
   - Mode C adds **no** `--dest`: `apply` fills the cache,
     `<namespace>/translations/<path>` (index `record.json`), which the
     installer reads.
7. **Index fix-up.** Once every file is applied, run `python
   translation.py sync-index --claude-md <repo>/CLAUDE.md.template --root
   <repo>` (modes A/B) so each `CLAUDE.md` index row carries its doc's
   translated summary. Mode C: run it on the cache copy
   (`--claude-md <cache>/CLAUDE.md.template --root <cache>`).
8. **Placeholders and record (modes A/B).** Placeholders are resolved
   after translation, as Domain 1 steps 2-5 say (mode B: see Domain 5's
   language step). Then write the placeholder map (NAME → resolved value,
   including `LANGUAGE`) to `.claude/.translation-staging/placeholders.json`
   and refresh each translated `replace` file's entry so `output_sha256`
   is the post-resolution hash: re-run step 6's `apply` with
   `--staged <the resolved file> --dest <the same file>` and
   `--placeholders .claude/.translation-staging/placeholders.json`.
   Failed (English) files get their placeholders resolved the same way.
   Show the record and confirm before the final write; it is committed.
9. **Settings.** Non-English only: Claude Code's `language` setting
   (`"language": "<name>"`), at the scope that matches the mode — mode A
   `.claude/settings.json` (Domain 1 step 8), mode B the shared
   `<ai-repo>/.claude/settings.json` (Domain 5 step 9), mode C the
   installer merges it (Domain 6 step 3).

Machine-parsed markers never change in any language: frontmatter keys
and enumerated values, `## Tasks`/`## Reconciliation`, FR/NFR/AC/T ids,
file names, commands and `{{PLACEHOLDER}}`s. `check` enforces it.

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
   - `.claude/settings.multi-project.json.example` as a whole
     (`{{HOOKS_DIR}}`, `{{PYTHON}}`, `{{PROJECTS_ROOT_PERMISSION_PATH}}`)
     — a template only Domain 5 and the user-level installer resolve,
     never Domain 1.
   - `{{LANGUAGE}}` **only when Domain 1 runs as Domain 5's prerequisite
     pass** (mode B): that pass never asks the language; Domain 5's
     language step resolves it. Steps 4 and 7 skip it there.

   The user-level installer (Domain 6) checks its own output against
   this same list and refuses to install if anything else survives
   (framework spec 0001 AC-04): there, the template sources a registration copies
   per project (`CLAUDE.md.template`, `architecture/*.md.template`,
   `0000-adr-template.md`) keep their placeholders too.
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
   - `{{LANGUAGE}}` — the setup language, asked once by the **Setup
     language** procedure above (English first and default). If it is
     not English, run that procedure's translation steps now, *before*
     applying any value (step 4): placeholders survive translation
     verbatim, so steps 1-4 then run unchanged on the translated files.
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
3. `{{DATE}}` — today's date, everywhere it appears — **never** inside
   `0000-adr-template.md`, per the exclusion above.
4. Apply every resolved value across **all** files it appears in
   (e.g. the same `{{PROJECT_NAME}}` in `CLAUDE.md.template` and in
   `docs/architecture/overview.md.template`) — a value filled in one place and left
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
8. Write `.claude/project-config.json` — mode A's machine-readable
   project config (framework ADR 0020). It's committed, like a mode B/C subtree's
   `project-config.json`, and it's what the hooks and scripts read here:
   the build/test gate (`run_build_test.py`, which `settings.json` now
   calls instead of holding the command literally), the setup language,
   the census, `review_policy`, routing-key names and per-project
   tools. Show it and confirm before writing:

   ```json
   {
     "build_test_cmd": "<the value resolved for BUILD_TEST_CMD>",
     "language": "<the language name, e.g. English>",
     "language_code": "<its BCP 47 code, e.g. en>",
     "main_integration_branch": "<the value resolved for MAIN_INTEGRATION_BRANCH>",
     "review_policy": "per-task",
     "census": {"enabled": false, "extractor": "none"}
   }
   ```

   Offer to enable the census (`docs/workflow/living-architecture-docs.md`)
   only if the project wants its architecture docs kept honest
   mechanically — and `dotnet-layered` as the extractor only for a .NET
   solution. Never put a per-machine or absolute path in this file.

   For a **non-English** language, also (each after confirming):
   - finish the record: re-run `apply` for every translated `replace`
     file as the Setup language procedure says (post-resolution
     `output_sha256`, placeholder map), and commit
     `.claude/translation-record.json` with the rest;
   - add `"language": "<the language name>"` to the new
     `.claude/settings.json` (Claude Code's own setting: the assistant
     then replies in that language). An English setup writes neither a
     record nor a `language` setting.

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
   framework ADR 0003 it now backs a
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
framework ADR 0006 for why this is safe
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
   Domain 1). Set its frontmatter `status: draft` (framework ADR 0019: `coder`
   and `reviewer` treat a draft's rules as advisory until
   `/update-docs promote` verifies them against code). Prepend this
   exact banner right after the frontmatter, before the first heading:

   ```text
   > **Detected automatically from existing code on {{DATE}} — a draft.
   > Read fully and correct anything wrong; `coder` and `reviewer` treat
   > its rules as advisory until `/update-docs promote` verifies them
   > against the code and marks it `active`.**
   ```

5. Never mark this done the way Domain 1's placeholders are done —
   this is a draft, not a resolved value. Say so explicitly in the
   close-out (see below).

## Domain 5 — External AI-repo mode (mode B): link a target code repo to this one

Goal: for a convention where all framework content (`.claude/`, `docs/`,
`CLAUDE.md`) must live in its own repo — call it the **AI-repo** — kept
separate from the actual code repo (the **target repo**), with *nothing*
Claude-related ever committed inside the target repo. This domain runs
from the AI-repo itself (this repo, already fully set up — nothing here
gets copied or modified except this project's own `docs/<name>/`
subtree, two small config files, the AI-repo's own setup language in
`.claude/project-config.json` (step 1a), and possibly a shared-ancestor
`CLAUDE.md` note in step 10) and configures one target repo to consume
it via local, never-committed links at the exact same relative
locations Domains 1-4 would otherwise have copied files to. Re-run it
once per target repo to link.

The target repo does **not** need to be a sibling of this one. It can
sit at any depth — e.g. a single package deep inside someone else's
monorepo, opened on its own in an editor, with this AI-repo many levels
above it, or entirely outside that monorepo. The only real requirement:
the two repos share *some* common ancestor directory (worst case, a
drive/filesystem root always counts) — that's where the bootstrap note
from step 10 has to live, since that's the only mechanism here that
doesn't depend on any link already existing.

**Every linked project always gets its own `docs/<name>/` subtree —
there is no "just one project" shortcut to choose.** Per framework ADR 0013 a
single project is simply N=1 in the same structure, so a simpler
one-off path would be a second code path maintained for no behavioural
gain, and linking a second target repo later would then need a
migration. Don't ask a single-vs-multi question anywhere in this
domain.

**There is no `projects/` folder** (framework ADR 0015 replaced framework ADR 0013's
two-tree layout). This AI-repo has exactly one `docs/` tree: shared
material at its root, each linked project one level down inside it.

```text
<ai-repo>/
  .claude/                     <- shared machinery, one copy, every project
  docs/                        <- THE shared root; the target repo's `docs` link points here
    constitution.md            <- supreme, cross-project (framework ADR 0007/0015)
    workflow/                  <- shared
    glossary.md                <- shared
    product/requirements-template.md
    <name>/                    <- one linked project
      CLAUDE.md
      project-config.json
      constitution.md          <- optional, project-owned, additive; NOT pre-created
      product/specs/
      architecture/module-structure.md, frontend.md
      decisions/               <- only 0000-adr-template.md to start
```

Because the link points at the shared root, a *relative* path like
`docs/product/specs/0001-x.md` inside a linked target repo lands in the
**shared** `product/`, colliding across every project — not in that
project's own subtree. Shared-material reads stay relatively
transparent; project content does not. That is why
`.claude/skills/project-registration/SKILL.md` rebinds every
project-content path to a resolved absolute one in this mode too, and
why nothing here should ever tell a command to write project content
at a relative `docs/...` path.

This domain is mode B, chosen by the adoption-mode question above; mode
C (Domain 6) is its user-level sibling, and mode A is Domains 1-4.
Unlike Domains 1-4, this domain's target is **not** this repo's own
root — it's a path the user supplies, anywhere on the same filesystem.
Besides the setup-wide language in the AI-repo's own config (step 1a), it
writes exactly two small per-project config files (steps 7 and 8) with
different lifecycles; see the note at the end of this domain for what each is for
and why the three links themselves still need none.

1. Prerequisite check: this domain links straight to *this* repo's own
   `CLAUDE.md` and `.claude/settings.json` — not to `CLAUDE.md.template`
   or `settings.example.json`. If either real file doesn't exist yet
   (i.e. this AI-repo copy hasn't been bootstrapped at all), stop and
   say so plainly: run Domain 1 on this repo first (even though several
   of its placeholders — build/test command, backend/frontend split —
   don't really apply to a content-only AI-repo; answer them with
   whatever's closest or "not applicable," the goal here is just turning
   the two templates into real files, not a fully-tailored Domain 1
   pass). Don't attempt a silent partial rename yourself — that's
   Domain 1's job, not this one's.

   **1a. Setup language** — once per AI-repo, never per project. Read
   `<ai-repo>/.claude/project-config.json` (or `describe`'s `language`):
   - **It already has a language** → say which, do not ask, and go on:
     every project linked here inherits it.
   - **It has none** (first setup of this AI-repo) → ask with the
     **Setup language** procedure above. Resolve the `{{LANGUAGE}}` the
     prerequisite pass left in the shared files (show the files, confirm,
     then replace it with the language name). For a non-English choice,
     then translate: the AI-repo's files are already resolved, so run
     `translation.py recover-placeholders --source <pristine snapshot>
     --resolved <ai-repo> --record <record>` first (it asks about any
     disagreement or non-match and fails on files edited for other
     reasons: ask the user, never guess), substitute that map into each
     staged translation before `apply --dest <ai-repo file>`, and commit
     the translated files and `.claude/translation-record.json`. Write
     `language`/`language_code` into
     `<ai-repo>/.claude/project-config.json` (the AI-repo's setup-wide
     config, committed; create it as `{"language": …, "language_code": …}`
     if it does not exist, and preserve every other key). Step 9 adds
     the `language` setting.
   - It has only a legacy split (`describe` says `legacy_split: true`)
     → offer "Migrating a legacy split setup" before asking.
2. Ask for the target repo's path. Suggest candidates first: list this
   repo's own sibling directories that contain a `.git` folder and
   aren't this repo itself, offered alongside a free-text "other path"
   option (a deeply nested monorepo package won't show up as a sibling
   guess — that's expected, just let the user type it).
3. Resolve both paths to absolute form and compute their **lowest
   common ancestor** (walk each path's components from the root down
   until they diverge; the last directory both still share). On
   Windows, stop and ask instead if the two paths are on different
   drive letters — there's no common ancestor to compute, so this mode
   needs both repos on the same drive. Otherwise, this always resolves
   on one filesystem, however far up it lands. Propose it as where the
   bootstrap `CLAUDE.md` note from step 10 will live, and let the user
   override to a different, higher ancestor of the target repo instead
   if they'd rather consolidate several target repos' notes at one
   well-known level (e.g. an actual monorepo root) than at whatever the
   raw lowest-common-ancestor computation happens to land on.
4. Compute the relative path from the target repo to this AI-repo (e.g.
   `../../../ai-repo-folder-name` from three levels down) — always
   relative, never absolute, so the same links work unmodified on every
   machine that clones both repos under the same relative layout.
   Reused for every item in step 6.
5. Shared `docs/` root, then this project's subtree inside it.
   - **First, confirm the shared root exists** at `<ai-repo>/docs/`.
     Since the AI-repo is this repo, already bootstrapped by Domain 1
     (step 1 checked that), it normally does and already holds
     `constitution.md`, `workflow/`, `glossary.md` and
     `product/requirements-template.md`. This is created **once
     per AI-repo, never per project** — if any of those four are
     missing, say which and stop; that means Domain 1 hasn't finished
     here, and a target repo linked now would reach a half-empty shared
     root. Never re-seed or overwrite a shared file that already
     exists: every already-linked project reads it.
   - Default `<name>` to the target repo's own folder name and confirm
     it (`AskUserQuestion`), allowing an override — it becomes a
     directory name and the value a human reads in step 7's routing
     file, so it's worth getting readable.
   - **Reserved names.** `<name>` may not be `workflow`, `product`,
     `architecture`, `decisions` or `glossary` — each would collide
     with a folder the shared root already owns one level up (ADR
     0015). Reject the name, say which shared folder it collides with,
     and ask again; never silently rename it yourself.
   - **If `docs/<name>/` already exists**, this is a re-link (fresh
     clone, second machine, moved target repo): say so, leave every
     file in it untouched, and continue at step 6. Never recreate or
     reset an existing subtree — it holds real specs and ADRs.
   - **If it doesn't exist**, create and seed it, showing exactly what
     will be created and confirming first (`AskUserQuestion`). Note
     there is no second `docs/` level inside the subtree — the subtree
     *is* inside `docs/`:
     - `docs/<name>/product/specs/` — empty. `spec_index.py` writes its
       `README.md` when the first spec lands; don't hand-write one.
     - `docs/<name>/architecture/` — the shared root's own
       `docs/architecture/module-structure.md.template` and
       `frontend.md.template`, copied as templates, unresolved (Domain
       4's drafting is mode A's flow, not this one's).
     - `docs/<name>/decisions/0000-adr-template.md` — copied from the
       shared `docs/decisions/0000-adr-template.md`, that file only,
       verbatim with its own `{{DATE}}` left literal. Per framework ADR
       0013 each project's ADR numbering starts fresh at 0001. The
       framework's own ADRs aren't part of the skeleton at all: they live
       in the framework repository's `evolution/decisions/`, outside
       `docs/`, so no project ever receives them.
     - `docs/<name>/CLAUDE.md` — from `CLAUDE.md.template`, with this
       project's placeholders resolved using Domain 1 step 2's
       detect-then-confirm pattern run against the **target** repo, not
       this one. Fill `{{LANGUAGE}}` from the AI-repo's language
       (`describe`), never by asking.
     - **No `constitution.md` here.** The supreme
       `docs/constitution.md` at the shared root already binds this
       project; `docs/<name>/constitution.md` is purely additive and
       project-owned (framework ADR 0015), so it is created only if and when that
       project actually writes its own principles. Don't pre-create an
       empty stub — a stub file reads as "this project has a
       constitution" to every stage that checks for one. Say in the
       close-out that the slot exists and where it would go.
     - **Nothing shared gets copied in.** `workflow/`, `glossary.md`,
       the `product/` templates and `constitution.md` stay at the
       shared root and are reachable from the target repo through the
       `docs` link in step 6 — that is the whole reason the link points
       at the root rather than at this subtree (framework ADR 0015). Copying them
       per project is exactly the drift framework ADR 0015 rejected.
6. For each of `.claude`, `docs`, and `CLAUDE.md` — the same three
   artifacts Domain 1 would otherwise copy into the target repo's own
   root — check `<target repo>/<item>`. Each points at a different
   place inside this AI-repo, using the relative path from step 4:
   - `.claude` → `<relative path>/.claude` — the **one shared**
     `.claude/`, identical for every linked project, with no
     per-project indirection anywhere (framework ADR 0013).
   - `docs` → `<relative path>/docs` — the **shared root**, not this
     project's subtree. That is what keeps `docs/workflow/...`,
     `docs/constitution.md`, `docs/glossary.md` and
     `docs/product/requirements-template.md` reachable from the target
     repo at the exact paths every agent and doc in this framework
     cites (framework ADR 0015). This project's own content sits one level down,
     at `docs/<name>/`, and is reached by resolved absolute path, not
     relatively — see the note above step 1.
   - `CLAUDE.md` → `<relative path>/docs/<name>/CLAUDE.md`

   Then, per item:
   - **Missing**: create the link at the target computed just above.
     Try a real symlink first
     (`New-Item -ItemType SymbolicLink` on Windows, `ln -s` elsewhere).
     If that fails from a Windows privilege error (no Developer Mode,
     not elevated), fall back to a **junction**
     (`New-Item -ItemType Junction`, or `mklink /J`) for `.claude`/`docs`
     (directory-only, no privilege needed) or a **hard link**
     (`New-Item -ItemType HardLink`, or `mklink /H`) for the single file
     `CLAUDE.md` (same-volume only — true here, since both repos
     resolved to paths under one common ancestor in step 3). State
     plainly which mechanism was used for each item.
   - **Already a symlink/junction/hard link pointing at the correct
     resolved target**: no-op, report "already linked" for that item.
   - **Anything else** (wrong target, or — especially likely for
     `docs`, a very common folder name — a real pre-existing directory
     or file with actual content): stop and ask (`AskUserQuestion`)
     before touching it, per item. For a genuine `docs/` collision,
     offer the choice plainly: skip linking `docs` for this target repo
     (the shared material — `docs/workflow/*`, `docs/constitution.md`,
     `docs/glossary.md`, `docs/product/*-template.md` — then isn't
     reachable at the conventional `docs/...` relative path any hook or
     agent in this framework expects, and every command has to be given
     its absolute path instead, exactly as in mode C: a real capability
     loss, not a cosmetic one) or have the user relocate their existing
     `docs/` first. Never guess or silently merge two unrelated `docs/`
     trees. The project's *own* content is unaffected either way — it's
     reached by absolute path regardless.
7. **Routing entry** — do this **every time** this domain runs for a
   target repo, re-links included. It's per-machine state, gitignored
   by design (framework ADR 0013), so a fresh clone of this AI-repo never carries
   it and the hooks can't route until it's written.
   - File: `<ai-repo>/.claude/projects.local.json`. If it doesn't
     exist, create it containing exactly
     `{"projects_root": "<absolute path to <ai-repo>/docs>"}` — the
     shared root itself, since that is where per-project subtrees are
     created in this mode (framework ADR 0015).
   - Then set one key in it: this machine's absolute
     `CLAUDE_PROJECT_DIR` for the target repo (normalized — forward
     slashes, no trailing slash, the same normalization every
     directory-scoped hook in this framework already uses) → the
     absolute path to `<ai-repo>/docs/<name>`. Absolute on both
     sides deliberately: this file is never shared, so absolute paths
     in it are simply correct.
   - Preserve every other key — `projects_root` and other projects'
     entries — by rewriting the file from the parsed object, never
     regenerating it from scratch. If it exists but doesn't parse, stop
     and report; don't overwrite a file you couldn't read.
   - If a key for this target repo already exists pointing at a
     *different* subtree, show both values and confirm
     (`AskUserQuestion`) before changing it — that's re-pointing a
     project, not a routine refresh.
   - Confirm the write with `AskUserQuestion`, showing the exact
     key/value pair, same as every other write in this command.
8. **`docs/<name>/project-config.json`** — the committed,
   per-project half of framework ADR 0013's split. Unlike step 7 this is *not*
   rewritten on every run: it holds stable, team-relevant values, and
   its git history is what shows when a project was attached or
   reconfigured.
   - **If it doesn't exist** (first time this project is configured),
     ask for the same values Domain 1 asks for, reusing Domain 1 step
     2's detect-then-confirm pattern but run against the **target**
     repo:
     - `build_test_cmd` — detect from the target repo (`.sln`/`.csproj`
       → `dotnet test`; a `package.json` `test` script → `npm test`;
       both → chain them), show the detection for confirmation rather
       than silently trusting it; ask if neither is found.
     - **No language here.** The language is the AI-repo's, asked once
       in step 1a; a per-project config never carries it.

     Write them as a flat JSON object with exactly these keys:

     ```json
     {
       "build_test_cmd": "...",
       "main_integration_branch": "<detected from origin/HEAD>",
       "review_policy": "per-task",
       "census": {"enabled": false, "extractor": "none"}
     }
     ```

     `main_integration_branch` is what `/worktree`, `/implement` and
     `/review` use for the integration branch at runtime (framework spec 0001
     FR-06); `review_policy` and `census` are framework ADR 0020's and framework ADR 0019's
     per-project switches, defaults shown.

     No absolute paths and no per-machine data ever go in this file —
     that's what step 7's file is for.
   - **If it already exists**, read it, show the current values, and
     ask (`AskUserQuestion`) whether to keep them or change any. Keep
     is the default and the common case — a re-link on a new machine
     changes nothing here. **Never overwrite an already-answered
     `project-config.json` without that explicit confirmation:** it's
     committed and shared, so silently changing another developer's
     build/test command is a real regression, not a refresh.
   - If it exists but doesn't parse, stop and report it; don't replace
     it with a guess.
9. **The shared `<ai-repo>/.claude/settings.json`** — one file for
   every project linked to this AI-repo, created once, never per
   project.
   - **If it already exists**, leave it alone and say so. Linking a
     second target repo must not touch the settings every
     already-linked project is running on. **The one exception:** when
     step 1a just set a non-English language, show the one line
     `"language": "<name>"` and, after confirming, add it (preserving
     every other key; if the file doesn't parse, stop and report).
   - **If it doesn't exist**, create it from
     `.claude/settings.multi-project.json.example` — *not*
     `settings.example.json`, which bakes one project's build/test
     command into static text, impossible for a
     file shared by several projects (framework ADR 0013). Add the same
     `language` line when step 1a chose a non-English language. Resolve its three
     placeholders:
     - `{{HOOKS_DIR}}` → `${CLAUDE_PROJECT_DIR:-.}/.claude/hooks`, which
       is correct here precisely because the target repo's `.claude` is
       a real link to this AI-repo's `.claude`, so that path lands on
       the shared hooks transparently.
     - `{{PYTHON}}` → `python` (or `python3` where only that exists).
     - `{{PROJECTS_ROOT_PERMISSION_PATH}}` → `<ai-repo>/docs` in Claude
       Code's absolute permission form: `//` plus a POSIX path, a Windows
       drive written `//c/...` (framework spec 0001 FR-08). A relative rule can't
       match the absolute subtree paths project content is written to.
       The template's rule is `Edit(...)` on purpose: Claude Code never
       uses `Write(path)` rules for file permission checks, and `Edit`
       covers every file-editing tool (see `.claude/README.md`).
     Leave the `.example` file itself in place — it's a reusable
     template for the next AI-repo, not a one-shot rename like Domain
     1's.
   - Confirm with `AskUserQuestion`, showing the resolved values, before
     writing.
   - Worth stating in the close-out: in this variant the deterministic
     gate runs `run_build_test.py`, which reads `build_test_cmd` from
     step 8's file at runtime and propagates its exit code — so the gate
     still blocks on a failed build exactly as in mode A, it just stops
     being hardcoded into the settings file.
10. Shared-ancestor `CLAUDE.md` bootstrap note (the file every Claude
    Code session inside the target repo auto-loads via the
    directory-tree walk, independent of whether any link from step 6
    actually exists — this is what makes it work as a check *for* those
    links):
    - Path: `<ancestor>/CLAUDE.md` (the location confirmed in step 3).
    - **Doesn't exist**: create it from this template, filling
      `{{DATE}}`, `{{AI_REPO_NAME}}`, `{{TARGET_REPO_NAME}}`:

      ```markdown
      # {{AI_REPO_NAME}} — shared ancestor notes

      Created {{DATE}} by `/setup-framework` (Domain 5). This file sits
      above one or more repos below it and loads automatically for any
      Claude Code session started inside one of them, via directory-tree
      walking — see `{{AI_REPO_NAME}}/docs/decisions/` for why.

      ## AI framework setup checks

      Before doing anything else in a session started inside
      `{{TARGET_REPO_NAME}}/`: confirm `{{TARGET_REPO_NAME}}/.claude`,
      `{{TARGET_REPO_NAME}}/docs`, and `{{TARGET_REPO_NAME}}/CLAUDE.md`
      all exist as real symlinks/junctions/hard links pointing into
      `{{AI_REPO_NAME}}` (not missing, not empty real folders/files). If
      any aren't, STOP — do not proceed with the user's request — and
      tell the developer to run `/setup-framework` (Domain 5) from
      `{{AI_REPO_NAME}}/` to link this repo before continuing.
      ```

    - **Already exists**: check whether it already has a checklist entry
      naming this specific target repo (match on the target repo's
      folder name) under the `## AI framework setup checks` heading. If
      that heading doesn't exist yet, add it; if it exists but this
      target repo isn't named under it, append one more paragraph for
      it, in the same shape as the template above — this is exactly how
      one shared ancestor ends up covering several target repos at once,
      each with its own paragraph. Never touch anything else in the
      file — same append-only discipline as Domain 3's `.gitignore`
      merge, since this file is hand-read by every session under this
      ancestor and a mistake here has a wide blast radius.
    - Always show the exact text being added and get explicit
      confirmation (`AskUserQuestion`) before writing.
11. Optional safety net: ask whether to add `.claude`, `docs`, and
    `CLAUDE.md` to the target repo's own `.gitignore` — nothing stages
    them under normal use, but this guards against a future
    `git add -A` accidentally picking one up. Show the exact diff,
    confirm first, same as Domain 3. Skip asking for any entry the
    target repo's `.gitignore` already covers.
12. Never write anything else inside the target repo — no
    `.claude/settings.json` content, nothing beyond the three links from
    step 6 and the optional `.gitignore` lines from step 11. Every
    config file this domain writes (steps 7-9) lands inside the
    **AI-repo**, never inside the target repo. Zero footprint there is
    the entire point of this mode.

**Why the three links need no config file, but two other things do**:
every link in step 6 lands at the exact conventional path
(`<target repo>/.claude`, `/docs`, `/CLAUDE.md`) every hook, agent, and
command in this framework already expects — a symlink/junction/hard
link is transparent to normal file reads, so nothing anywhere else
needs to know linking is even involved, and there's no "which CLAUDE.md
is the framework's" ambiguity to resolve, since there's exactly one
reachable at that path once step 6 has run. (Since framework ADR 0015 that
transparency covers *shared* material only: the `docs` link resolves
`docs/workflow/...` and `docs/constitution.md` correctly, while this
project's own content needs the resolved `docs/<name>/...` path the
registry supplies.) Likewise the bootstrap
note's location (step 10) is recomputed fresh on every run by a
lowest-common-ancestor walk and is self-documenting once written (the
note itself lists which target repos it covers), so persisting it would
track something already derivable from the filesystem.

What is *not* derivable is which project a **shared** `.claude/`
belongs to for the current session, and that project's build/test
command — one `settings.json` serves every linked
project, so neither can be baked into it. (The language is setup-wide,
not per project, so it lives in the AI-repo's own
`.claude/project-config.json`.) framework ADR 0013 answers both with
the two files above, split by lifecycle: step 7's
`.claude/projects.local.json` is per-machine routing (gitignored,
absolute paths, regenerated by this domain on each machine), and step
8's `docs/<name>/project-config.json` is a committed project fact
worth versioning. A hook reads the first, then the second, and **fails
open at either step** — a missing routing entry or an unparsable
config degrades the session with a nudge to re-run this domain, it
never blocks it. Domain 6 (the user-level variant) reuses both files
verbatim, rooted at `~/.claude` instead of a cloned repo — which is
the whole reason the mechanism is a path-keyed lookup rather than
something inferred from the links themselves.

Close-out for this domain specifically: name the project `<name>` and
its subtree path, and whether the subtree was created fresh or already
existed. For each of `.claude`/`docs`/`CLAUDE.md`, state the resolved
relative link target and which mechanism created it
(symlink/junction/hard link), or that it was already linked, or that it
was skipped due to a real collision. State the routing entry written
(key → value), whether `project-config.json` was created, changed, or
left as-is, and whether the shared `.claude/settings.json` was created
from the multi-project variant or already existed. State whether the
shared-ancestor `CLAUDE.md` was created, appended to, or already
covered this target repo, and its resolved path. State the setup
language (asked now, or inherited from the AI-repo), whether a
translation pass ran (files translated, files left in English and why,
the token estimate shown) and whether the shared settings gained
`language`. State plainly that
the `docs` link points at the **shared root**, so this project's own
content is reached at `docs/<name>/` by resolved absolute path (the
`project-registration` skill does this rebinding for every pipeline
command), and that `docs/<name>/constitution.md` was deliberately not
created — the supreme `docs/constitution.md` already binds this
project, and the project's own additive one is written only if it ever
needs its own principles. Remind the user the three links and
`.claude/projects.local.json` are committed nowhere, so both must be
recreated (re-run this domain) on every fresh machine or fresh
clone/checkout of the target repo.

## Domain 6 — User-level mode (mode C): install the machinery into `~/.claude`

Goal: put this framework's machinery where Claude Code already loads it
for *every* session on this machine — the user-level `~/.claude`
directory — so no code repo needs a copied file, a link, or any
footprint at all.

This domain runs **once per machine** (and again to upgrade), and it
configures the machine, not a project. Projects register lazily, the
first time a pipeline command needs one (framework ADR 0014), or in bulk at the
end of this domain.

**All the mechanics live in one script**, `.claude/scripts/install_user_level.py`,
run from this repository (framework ADR 0017, framework spec 0001). This domain asks the
questions, shows the script's dry run, and only then lets it write.
The script is what guarantees, mechanically rather than by instruction:

- a **namespace prefix** (default `cfw`): agents, commands and skills
  land as `cfw-coder`, `/cfw-spec`, `cfw-project-registration`, so they
  can't collide with a user's own `spec`/`plan`; hooks, scripts, the
  registry, templates and the shared `docs/` root live in
  `~/.claude/<prefix>/`. The framework's own specs and ADRs
  (`evolution/`) are never installed. Every
  cross-reference in the installed text is rewritten consistently;
- **absolute hook paths** in `settings.json` — never a quoted `~`, which
  bash doesn't expand (D1) — and a spec-write permission generated
  against the absolute projects root (FR-08);
- **one config source**, `~/.claude/<prefix>/framework.json` (registry,
  shared root, projects root, template locations). The hooks read it,
  and the installed `project-registration` skill carries the same values
  in a generated binding block. Nothing is inferred from folder shape
  (D12);
- a **registration gate**: every hook is a no-op in a repo nobody
  registered, so an unrelated repo gets no `.claude/` file, no index, no
  build run (D2);
- **no per-project placeholder** in any installed file: per-project
  values become runtime tokens the registration skill defines, dates are
  stamped, and the install aborts if anything else survives (D9, AC-04);
- a **manifest and an uninstaller** (dry run by default) that remove
  exactly what was installed and restore `settings.json` byte for byte
  (D7);
- **idempotent, never clobbering**: a destination it doesn't own aborts
  the whole run before anything is written, and so does an installed
  file someone edited by hand (fix it in this repository first — NFR-01);
- the **constitution baseline** (`constitution-baseline.md`) is
  replaced on every upgrade, while the organization layer
  (`constitution.md`) and `glossary.md` are created once and never
  overwritten (framework ADR 0018).

There is **no Domain 1 prerequisite** (D8). The installer reads the raw
skeleton, never installs a `*.py.example` (`auto_format`,
`dependency_audit` are per-project by nature), and wires
`project_tools.py` instead, which runs whatever formatter/audit a
project declares in its own config.

1. **Config directory.** `~/.claude`, expanding `~` for this OS. **If
   `CLAUDE_CONFIG_DIR` is set**, stop and say so: Claude Code reads that
   directory instead. Offer to install there (`--config-dir`) or stop.
   Never install where it won't be read.
2. **Ask once** (`AskUserQuestion`, one batch):
   - **Prefix** — default `cfw`. Explain that every command becomes
     `/<prefix>-spec`, `/<prefix>-quick`, ...
   - **Projects root** — where each registered project's `<name>/`
     subtree is created:
     - **`~/.claude/<prefix>/docs/`, the default** — nests projects in
       the shared root exactly as in mode B (framework ADR 0015). **It sits outside
       any repository you'd think to version**, so a machine loss takes
       every spec and ADR with it. Say this when offering it.
     - **Any folder you already version or sync** — removes that risk,
       and nothing in the mechanism cares where subtrees sit.
   - **Worktrees root** — the folder `/worktree` creates every spec
     worktree under, as `<root>/<repo folder name>/<short-name>`. Offer
     the same choices as Domain 7 step 2 (sibling of the repo, a
     suggested dedicated folder, or another path). On an upgrade, offer
     the `worktrees_root` already in `framework.json` as the default.
     Domain 7's step 6 offer (root `CLAUDE.md` note) applies here too.
   - **Language** — the **Setup language** question above, English
     first. On an upgrade, offer the `language` already in
     `framework.json` as the default ("keep"). It covers every project
     registered under this install; registering one never asks again.
   - **Anything to retire** — only if the dry run shows a collision
     with something the user wants out of the way. `--retire <path>`
     moves it into `~/.claude/<prefix>/backups/retired/`; the
     uninstaller lists it and can restore it.
3. **Translate first, then dry run.** For a non-English language, fill
   the translation cache **before** the dry run: run the **Setup
   language** procedure's mode C steps from *this* repository checkout
   (plan, estimate and confirmation, term map, `translator` batches,
   `check`, `apply` with no `--dest`, so the cache lands in
   `<namespace>/translations/` with `record.json`). The installer reads
   that cache and **aborts on a stale or missing entry**, so a
   language that changed or a newer checkout means re-running `plan`
   and translating what it lists. English fills no cache.

   Then **dry run** and show the result:
   `python .claude/scripts/install_user_level.py --prefix <p> --projects-root "<root>" [--worktrees-root "<folder>"] [--language <name> --language-code <code>]`
   (leave a flag out to keep the current value; `--worktrees-root ""`
   goes back to sibling worktrees; the two language flags go together
   and are kept across upgrades). Non-English also merges Claude Code's
   `language` setting into `settings.json`. If the dry run shows a
   *different* `language` already there, it is left alone: tell the
   user and, only if they want it replaced, add `--set-language-setting`
   (uninstall restores the old value).
   It lists every file it would create, update or keep, the
   `settings.json` additions, and any legacy pre-namespace install it
   found. A collision or a hand-edited installed file makes it refuse.
   Relay that verbatim and stop until the user resolves it.
4. **Confirm** (`AskUserQuestion`), then run the same command with
   `--apply`.
5. **Optional — register existing repos now** (framework spec 0001 FR-11). Ask
   whether to register several existing repos in one pass instead of
   lazily. If yes, follow the installed `<prefix>-project-registration`
   skill's "Bulk registration" section: shared answers once, one plan
   file, `register_project.py --plan` (dry run, then `--apply`).
6. **Optional — migrate an existing doc base** (FR-12). If the user
   already keeps architecture docs, specs or ADRs somewhere else for a
   project, offer to import them into that project's subtree:
   `python ~/.claude/<prefix>/scripts/migrate_context.py --source <old> --dest <subtree>`
   (dry run first; `--map OLD=NEW` and `--rename-key OLD=NEW` for what
   the heuristics get wrong; `--apply` once the report shows zero
   introduced broken links and zero docs missing required keys). The
   source is never modified, and the report proves it. Mark imported
   architecture docs `status: draft` unless the user has just verified
   them.
7. **Close-out** — say all of this:
   - The prefix and the namespace path; what was created, updated or
     kept; what `settings.json` gained (and that uninstall restores it
     byte for byte).
   - The projects root, and whether it carries the default's backup risk.
   - The worktrees root, or that spec worktrees sit beside their repo.
   - The setup language and code; for a non-English one, how many files
     were translated and which stayed English (and why), the token
     estimate shown, and that `settings.json` gained (or kept, or
     replaced with `--set-language-setting`) the `language` setting.
   - That **no code repo was touched** — and that hooks do nothing in a
     repo until it's registered.
   - **Loudest:** unless step 5 ran, no project is registered and none
     needs to be — the first `/<prefix>-spec`, `/<prefix>-plan`,
     `/<prefix>-quick`, ... in an unregistered repo registers it on the
     spot.
   - How to upgrade (re-run this domain from an updated checkout; see
     "Upgrading and migrating") and how to uninstall:
     `python ~/.claude/<prefix>/scripts/uninstall.py` (then `--apply`).

**Upgrading from the hand-built install of 2026-09-30.** That copy has
no manifest this installer recognizes, so the dry run reports its files
as collisions. Run that install's own uninstaller first (dry run, then
apply) — it keeps the registry and project subtrees — and then install.
A kept registry and kept project subtrees in the namespace are adopted,
not treated as collisions.

## Domain 7 — Where spec worktrees live (per machine)

Goal: choose the folder `/worktree` (and `/implement`, which reuses its
steps) creates every spec worktree under, so they don't land wherever
the repo happens to sit. Runs in modes A and B, after that mode's
domains. Mode C asks the same question in Domain 6 step 2.

The choice is **per machine, never per project**: it's an absolute path
on this disk, so it never goes in the committed `project-config.json`.
It lives in `.claude/framework.local.json` (gitignored), in the
`.claude/` that holds the hooks: this repo's own in mode A, the
AI-repo's in mode B. In mode B one value therefore covers every target
repo linked to it. Each worktree lands at
`<root>/<repo folder name>/<short-name>`. The repo level keeps two
projects' same-named specs apart.

1. **Detect.** Run
   `python "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/_project_paths.py" describe`
   and read `worktrees_root`. Set → offer it as the default ("keep").
   Unset → worktrees currently go beside the repo (`../<short-name>`).
2. **Ask** (`AskUserQuestion`, one question), saying where a sample
   spec would land under each option:
   - **Beside the repo (`../<short-name>`)** — the original layout.
     Nothing is written. Fine for one repo, but it fills the repo's
     parent folder with one folder per spec in flight.
   - **A dedicated folder (suggested)** — suggest
     `<repo's parent>/worktrees`. **If the repo sits inside a synced
     folder** (a path under OneDrive, Dropbox, Google Drive or iCloud),
     say so, and suggest a folder outside it instead (e.g. `C:/dev/worktrees`
     on Windows, `~/dev/worktrees` elsewhere). Otherwise every
     worktree's build output and dependencies sync too.
   - **Another folder** — free text.
3. **Validate** before writing. The path must be absolute; expand `~`
   yourself. It must not be inside this repo or, in mode B, inside a
   linked target repo: a worktree nested in its own repo shows up as
   untracked content there. It doesn't need to exist yet, since
   `git worktree add` creates missing parents. Where it may sit depends
   on the mode:
   - **Mode A:** any drive, because git worktrees don't need the same
     volume and nothing is linked into them.
   - **Mode B:** each worktree there gets `.claude`, `docs` and
     `CLAUDE.md` linked in by `link_worktree.py` (framework ADR 0022), so
     check the root can hold them. On the same volume as the AI-repo
     everything works. On another local NTFS volume junctions still
     reach `.claude` and `docs`, but the hard-linked `CLAUDE.md` needs
     the same volume, so unless symlinks are available there, steer the
     user to a root on the AI-repo's volume. A network drive or exFAT
     can't hold junctions at all: refuse it. (This reverses mode A's
     "any drive" for mode B only.)
4. **Write**, after confirming the exact JSON (`AskUserQuestion`).
   Read `.claude/framework.local.json` if it exists and set only
   `worktrees_root`, preserving every other key; create it as
   `{"worktrees_root": "<path, forward slashes>"}` if not. "Beside the
   repo" removes the key, and deletes the file only if nothing else is
   left in it. If the file exists but doesn't parse, stop and report
   it; don't overwrite it.
5. **Gitignore check.** The file must never be committed. In mode A,
   Domain 3's merge already brings in `.claude/framework.local.json`
   from `.gitignore.framework-additions`. In mode B, check the
   AI-repo's own `.gitignore` covers it, and if not, offer the one-line
   addition (show it, then confirm).
6. **Optional — worktrees-root `CLAUDE.md` bootstrap note.** Offered
   whenever a worktrees root was set in step 4, in every mode (skip it
   for "beside the repo"). A session started inside a worktree whose
   links are missing has no framework config, so this file, which it
   auto-loads by walking up the directory tree, is what tells it so.
   Same append-only, confirm-first discipline as Domain 5 step 10:
   - Path: `<worktrees_root>/CLAUDE.md`.
   - **Doesn't exist**: create it from this template, filling `{{DATE}}`
     and `{{AI_REPO_NAME}}` (the repo holding `.claude/scripts/`: this
     repo in mode A, the AI-repo in mode B):

     ```markdown
     # Spec worktrees — notes

     Created {{DATE}} by `/setup-framework` (Domain 7). This file sits
     above every spec worktree and loads automatically for any Claude
     Code session started inside one, via directory-tree walking
     (framework ADR 0022).

     ## AI framework setup checks

     Before doing anything else in a session started inside a worktree
     here: confirm its `.claude`, `docs` and `CLAUDE.md` exist as real
     links into `{{AI_REPO_NAME}}` (not missing, not empty real
     folders/files). If any aren't, STOP — do not proceed with the
     user's request — and tell the developer to run
     `python "<ai-repo>/.claude/scripts/link_worktree.py" --repair` from
     the main checkout (`<ai-repo>` is the path to `{{AI_REPO_NAME}}`)
     to relink the worktree before continuing.
     ```

   - **Already exists**: if it has no `## AI framework setup checks`
     heading, append the heading and paragraph above; if it has one,
     append the paragraph only when no paragraph there already mentions
     `link_worktree.py`. Never touch anything else in the file.
   - Always show the exact text being added and get explicit
     confirmation (`AskUserQuestion`) before writing.

Declining leaves worktrees beside the repo, exactly as before this
domain existed. Re-run it any time to move future worktrees. Existing
worktrees stay where they are (`git worktree move` relocates one by
hand).

## Upgrading and migrating (any mode)

Goal: bring a non-English setup up to a newer framework version
translating **only what changed upstream** (framework spec 0005 FR-06,
NFR-06), and move a legacy split setup to one language. Every write is
confirmed first (`AskUserQuestion`), as everywhere in this command. An
English setup has no record: an upgrade translates nothing, and
`upgrade-plan` reports a no-op. The translation steps are the **Setup
language** procedure's; this section only says what to run and when.

**Mode A upgrade.** There is no installer: the user points this run at a
newer checkout of the framework.

1. `python translation.py upgrade-plan --mode a --source <newer checkout>
   --record .claude/translation-record.json --language-code <code>`.
   Ignore listed paths outside `.claude/`, `docs/` and
   `CLAUDE.md.template` (the checkout's README, `evolution/`, ...).
2. `retranslate` (source changed, output still untouched): state the
   estimate, confirm, then translate from the newer English, check,
   re-resolve placeholders from the record's `placeholders` map (ask
   about any NAME the map lacks, as Domain 1 step 2 does), `apply`
   with `--dest`, overwriting the old translation.
3. `edited` (source changed, output edited locally): show each file's
   local diff against the recorded version and **ask per file**:
   overwrite with a fresh translation, or keep the local file.
4. `keep` files (constitution, glossary): **never touched**. `new`:
   translated like a first setup (renamed as Domain 1 step 5 does).
   `deleted_upstream`: reported only, never deleted.
5. Non-translatable files (JSON, scripts, `*.example`) follow the
   usual hand copy; a changed `settings.example.json` is shown, never
   overwritten over a customised `settings.json`.

**Mode B upgrade.** The AI-repo is a git clone of the framework, so this
runs inside an open merge. Needs a clean tree and a known upstream remote.

1. `git fetch <upstream>` then `git merge --no-commit <upstream>/<branch>`
   (conflicts are expected; the merge stays open).
2. `python translation.py upgrade-plan --mode b --repo <ai-repo> --record
   .claude/translation-record.json`. If the record has no `placeholders`
   map (an AI-repo set up before the record existed), run
   `recover-placeholders` first, with the pristine sources of the
   merge base (`git archive $(git merge-base HEAD MERGE_HEAD)`), and ask
   about any disagreement or non-match.
3. For **every `changed` path the report lists, and only those**, whether
   it conflicted or merged cleanly (the hash decides, not git):
   `python translation.py take-upstream --repo <ai-repo> --path <p> ...`
   passing exactly the listed paths; never any other path, never a
   blanket checkout. Unchanged paths keep the AI-repo's version.
4. Translate those English files (and the `new` ones; snapshot
   `git archive MERGE_HEAD` as `--source`), `check` each, substitute the
   placeholder map into each staged file, then `apply --dest`. A file
   that fails keeps upstream's English (with the map applied, recorded
   `apply --status english --reason`), so the merge always completes.
   `deleted_upstream` is reported, never deleted.
5. Resolve any remaining conflicts by hand with the user, show the
   result, confirm, and **commit the merge** (the translated files and
   `.claude/translation-record.json` go in it).

**Mode C upgrade.** Re-run Domain 6 from the updated checkout. Its step
3 refills the cache first: the installer aborts on stale cache entries,
so translate exactly what `plan` lists (changed and new sources only)
before the dry run.

**Changing the language later.** Run the **Setup language** procedure
with the new language: `plan` then lists every `replace` file and the
translation starts from English, never from the previous translation.
Existing project artifacts (specs, ADRs, architecture docs) are never
rewritten silently; offer translating them, file by file, and only on a
yes (framework spec 0005 FR-10).

**Migrating a legacy split setup.** When `python
"${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/_project_paths.py" describe`
reports `legacy_split: true` (`canonical_lang`/`stakeholder_lang` and no
setup language), offer to migrate, never force it:

1. Ask the setup language with the **Setup language** procedure
   (suggest the old canonical language as the default).
2. Record it where the mode keeps it (mode A `.claude/project-config.json`,
   mode B the AI-repo's, mode C `framework.json` through Domain 6's
   `--language`), run the translation steps if non-English, and after
   confirming drop the old `canonical_lang`/`stakeholder_lang*` keys.
3. **Keep every `.validation-*.md` file; never delete one.** A settings
   file still wiring `validation_sync_check.py` is harmless (the hook is
   a legacy shim); offer to unwire it.
4. Translating existing project artifacts is **offered, never forced**.

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

Name the adoption mode chosen (A, B or C) first — it's what explains
which domains ran and which were never applicable. Then state the setup
language and code and whether a translation pass ran (files translated,
files left in English and why, the token estimate shown, the `language`
setting written), or that English needed none. Then end with a
one-line summary per domain covered: what got filled in/installed/
merged, what was declined, what was already covered, and — loudest of
all — the state of the two architecture files:

- If Domain 4 didn't run (declined, nothing to detect, or mode B/C
  where it isn't part of the flow): they're still blank slots to fill
  by hand before the first real `/spec`, same as always. In mode B
  they're the ones seeded into `docs/<name>/architecture/`; in mode C,
  the ones a lazy registration creates under
  `<projects root>/<name>/architecture/`.
- If Domain 4 drafted them: say so plainly, and that they're a
  **draft from detected patterns, not a finished document** — the user
  needs to read and correct `module-structure.md`/`frontend.md` before
  `coder`/`reviewer` start trusting them, same urgency as the
  fill-by-hand case, not less.
- If Domain 5 ran: name the target repo linked and its
  `docs/<name>/` subtree, the resolved relative link path and
  mechanism (symlink/junction/hard link) for each of
  `.claude`/`docs`/`CLAUDE.md` — noting that `docs` points at the
  **shared root**, so this project's own content is reached at
  `docs/<name>/` by resolved absolute path — including any skipped due
  to a real collision, the routing entry written, whether `project-config.json`
  was created/changed/left alone, whether the shared
  `.claude/settings.json` was created from the multi-project variant or
  already existed, and the shared-ancestor `CLAUDE.md`'s state
  (created/appended/already covered) plus its resolved path — plus the
  standing reminder that neither the links nor
  `.claude/projects.local.json` is committed anywhere, so both must be
  recreated on any fresh machine or fresh clone/checkout of the target
  repo.
- If Domain 7 ran: the worktrees root written to
  `.claude/framework.local.json` (and an example path a spec would get),
  or that worktrees stay beside the repo — and that the choice is per
  machine, so a teammate or a fresh machine makes its own. In mode B,
  whether the root can hold the links (same volume or symlinks). Also
  whether the `<worktrees_root>/CLAUDE.md` bootstrap note was created,
  appended, already covered or declined.
- If Domain 6 ran: the prefix and namespace installed into, what the
  installer created/updated/kept (and any collision it refused on), what
  `settings.json` gained, the chosen projects root and whether it carries
  the default's backup risk, the worktrees root (or none), the language
  and cache state (translated/English files, `language` setting), whether
  bulk registration or a migration ran — and, loudest, that unless they did, **no project was
  registered and none needs to be**: the first `/<prefix>-*` pipeline
  command run in an unregistered repo registers it on the spot.
