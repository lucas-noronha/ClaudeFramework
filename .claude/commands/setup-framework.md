---
description: Single entry point for adopting or maintaining this framework in a project — opens by choosing one of three mutually exclusive adoption modes (direct in-repo, external AI-repo, or user-level multi-project), then runs only that mode's
domains: bootstrapping CLAUDE.md and settings from the copied skeleton, installing recommended global plugins, merging framework scaffolding files into this repo without clobbering what's already there, optionally drafting the architecture blank slots from the existing codebase's own detected patterns, linking a separate target code repo to this AI-repo with zero footprint there (Domain 5), or merging the machinery into `~/.claude` for every project on this machine (Domain 6). Add new setup domains here as the framework grows rather than creating a new top-level command per domain.
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
`docs/decisions/0014-setup-framework-adoption-modes.md` the three
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
   - `~/.claude/projects.local.json` exists (expand `~` for the current
     OS) → mode C is already set up on this machine.
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
     shared `docs/` tree, at `docs/<name>/` (ADR 0013, layout per
     ADR 0015).
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
     reach, which mode C cannot detect from inside a hook (ADR 0014).
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

## Domain 5 — External AI-repo mode (mode B): link a target code repo to this one

Goal: for a convention where all framework content (`.claude/`, `docs/`,
`CLAUDE.md`) must live in its own repo — call it the **AI-repo** — kept
separate from the actual code repo (the **target repo**), with *nothing*
Claude-related ever committed inside the target repo. This domain runs
from the AI-repo itself (this repo, already fully set up — nothing here
gets copied or modified except this project's own `docs/<name>/`
subtree, two small config files, and possibly a shared-ancestor
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
there is no "just one project" shortcut to choose.** Per ADR 0013 a
single project is simply N=1 in the same structure, so a simpler
one-off path would be a second code path maintained for no behavioural
gain, and linking a second target repo later would then need a
migration. Don't ask a single-vs-multi question anywhere in this
domain.

**There is no `projects/` folder** (ADR 0015 replaced ADR 0013's
two-tree layout). This AI-repo has exactly one `docs/` tree: shared
material at its root, each linked project one level down inside it.

```text
<ai-repo>/
  .claude/                     <- shared machinery, one copy, every project
  docs/                        <- THE shared root; the target repo's `docs` link points here
    constitution.md            <- supreme, cross-project (ADR 0007/0015)
    workflow/                  <- shared
    glossary.md                <- shared
    product/requirements-template.md, validation-summary-template.md
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
It writes exactly two small config files (steps 7 and 8) with different
lifecycles; see the note at the end of this domain for what each is for
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
     `product/requirements-template.md` +
     `product/validation-summary-template.md`. This is created **once
     per AI-repo, never per project** — if any of those five are
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
       verbatim with its own `{{DATE}}` left literal. Per ADR
       0013 each project's ADR numbering starts fresh at 0001; this
       framework's own ADRs stay in the shared `docs/decisions/`.
     - `docs/<name>/CLAUDE.md` — from `CLAUDE.md.template`, with this
       project's placeholders resolved using Domain 1 step 2's
       detect-then-confirm pattern run against the **target** repo, not
       this one.
     - **No `constitution.md` here.** The supreme
       `docs/constitution.md` at the shared root already binds this
       project; `docs/<name>/constitution.md` is purely additive and
       project-owned (ADR 0015), so it is created only if and when that
       project actually writes its own principles. Don't pre-create an
       empty stub — a stub file reads as "this project has a
       constitution" to every stage that checks for one. Say in the
       close-out that the slot exists and where it would go.
     - **Nothing shared gets copied in.** `workflow/`, `glossary.md`,
       the `product/` templates and `constitution.md` stay at the
       shared root and are reachable from the target repo through the
       `docs` link in step 6 — that is the whole reason the link points
       at the root rather than at this subtree (ADR 0015). Copying them
       per project is exactly the drift ADR 0015 rejected.
6. For each of `.claude`, `docs`, and `CLAUDE.md` — the same three
   artifacts Domain 1 would otherwise copy into the target repo's own
   root — check `<target repo>/<item>`. Each points at a different
   place inside this AI-repo, using the relative path from step 4:
   - `.claude` → `<relative path>/.claude` — the **one shared**
     `.claude/`, identical for every linked project, with no
     per-project indirection anywhere (ADR 0013).
   - `docs` → `<relative path>/docs` — the **shared root**, not this
     project's subtree. That is what keeps `docs/workflow/...`,
     `docs/constitution.md`, `docs/glossary.md` and
     `docs/product/requirements-template.md` reachable from the target
     repo at the exact paths every agent and doc in this framework
     cites (ADR 0015). This project's own content sits one level down,
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
   by design (ADR 0013), so a fresh clone of this AI-repo never carries
   it and the hooks can't route until it's written.
   - File: `<ai-repo>/.claude/projects.local.json`. If it doesn't
     exist, create it containing exactly
     `{"projects_root": "<absolute path to <ai-repo>/docs>"}` — the
     shared root itself, since that is where per-project subtrees are
     created in this mode (ADR 0015).
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
   per-project half of ADR 0013's split. Unlike step 7 this is *not*
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
     - `canonical_lang` — ask, default suggestion English.
     - `stakeholder_lang` / `stakeholder_lang_code` — ask, with "same
       as canonical — skip the split" as an explicit option; if chosen,
       set both to the canonical language and code (every step that
       reads them already no-ops when they're equal).

     Write them as a flat JSON object with exactly these keys:

     ```json
     {
       "build_test_cmd": "...",
       "canonical_lang": "...",
       "stakeholder_lang": "...",
       "stakeholder_lang_code": "..."
     }
     ```

     No absolute paths and no per-machine data ever go in this file —
     that's what step 7's file is for.
   - **If it already exists**, read it, show the current values, and
     ask (`AskUserQuestion`) whether to keep them or change any. Keep
     is the default and the common case — a re-link on a new machine
     changes nothing here. **Never overwrite an already-answered
     `project-config.json` without that explicit confirmation:** it's
     committed and shared, so silently changing another developer's
     build/test command or language split is a real regression, not a
     refresh.
   - If it exists but doesn't parse, stop and report it; don't replace
     it with a guess.
9. **The shared `<ai-repo>/.claude/settings.json`** — one file for
   every project linked to this AI-repo, created once, never per
   project.
   - **If it already exists**, leave it alone and say so. Linking a
     second target repo must not touch the settings every
     already-linked project is running on.
   - **If it doesn't exist**, create it from
     `.claude/settings.multi-project.json.example` — *not*
     `settings.example.json`, which bakes one project's build/test
     command and language values into static text, impossible for a
     file shared by several projects (ADR 0013). Resolve its single
     placeholder: `{{HOOKS_DIR}}` →
     `${CLAUDE_PROJECT_DIR:-.}/.claude/hooks`, which is correct here
     precisely because the target repo's `.claude` is a real link to
     this AI-repo's `.claude`, so that path lands on the shared hooks
     transparently. Leave the `.example` file itself in place — it's a
     reusable template for the next AI-repo, not a one-shot rename like
     Domain 1's.
   - Confirm with `AskUserQuestion`, showing the resolved
     `{{HOOKS_DIR}}` value, before writing.
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
reachable at that path once step 6 has run. (Since ADR 0015 that
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
command and language split — one `settings.json` serves every linked
project, so neither can be baked into it. ADR 0013 answers both with
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
covered this target repo, and its resolved path. State plainly that
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

## Domain 6 — User-level mode (mode C): merge the machinery into `~/.claude`

Goal: put this framework's machinery where Claude Code already loads it
for *every* session on this machine — the user-level `~/.claude`
directory — so no code repo needs a copied file, a link, or any
footprint at all. Zero footprint in the target repo is automatic here,
with no symlink/junction mechanism involved.

This domain runs **once per machine**, and it configures the machine,
not a project. Per ADR 0014, individual projects register themselves
lazily, the first time a pipeline command actually needs one — see step
8's close-out, which is the part a reader is most likely to assume
happened here and didn't.

Like Domain 5, this domain's target is **not** this repo — it's this
machine's user-level config directory, which may already hold personal
skills, commands and settings that are none of this framework's
business. The rule throughout: **never clobber an existing file.** Same
discipline Domain 3 applies to `.gitignore`/`.mcp.json`, generalized
from a line-merge to a whole-folder merge.

1. Prerequisite check: mode C copies the **real, resolved** machinery
   this repo has, not templates. Scan `.claude/agents/`,
   `.claude/commands/`, `.claude/skills/` and `.claude/hooks/` for
   anything still unresolved — a remaining `*.py.example`
   (`auto_format.py.example`, `dependency_audit.py.example`) or an
   unresolved `{{PLACEHOLDER}}` outside Domain 1 step 1's
   permanent-exclusion list. If any is found, stop and say plainly: run
   Domain 1 on this repo first, then re-run this domain. Don't rename
   or resolve anything yourself — that's Domain 1's job, not this
   one's. (`settings.example.json` is the one exception: mode C never
   uses it, step 5 uses `.claude/settings.multi-project.json.example`
   instead.)
2. Resolve the user-level config directory: `~/.claude`, expanding `~`
   for the current OS (`%USERPROFILE%\.claude` on Windows,
   `$HOME/.claude` elsewhere). **If `CLAUDE_CONFIG_DIR` is set on this
   machine**, stop and say so before doing anything: Claude Code then
   reads *that* directory instead of `~/.claude`, so anything installed
   here would simply never be loaded. Per ADR 0014 this framework takes
   no responsibility for detecting or migrating around that
   customization from inside a hook — but at setup time it is visible,
   so offer the choice explicitly (`AskUserQuestion`): install into
   `$CLAUDE_CONFIG_DIR` instead (in which case every `{{HOOKS_DIR}}`
   below resolves to that directory's absolute `hooks/` path rather
   than `~/.claude/hooks`, and the user owns keeping it correct if they
   move it again), or stop here. Never install into `~/.claude` knowing
   it won't be read.
3. Dry-run the merge and show it before touching anything. Build the
   exact list of files that would be copied:
   - `.claude/agents/*.md` → `<user config>/agents/`
   - `.claude/commands/*.md` → `<user config>/commands/`
   - `.claude/skills/*/` → `<user config>/skills/` (whole skill
     folders, `SKILL.md` and any reference files). Copy
     `skills/README.md` only if the destination has none —
     `skill_index.py` regenerates it from the skills actually present.
   - `.claude/hooks/*.py` → `<user config>/hooks/` (resolved `.py`
     files only; step 1 already guaranteed no `.py.example` is left)
   - **The shared `docs/` root** → `<user config>/docs/`, created once
     per machine and shared by every project registered later (ADR
     0015). Exactly this material, and nothing else from this repo's
     `docs/`:
     - `docs/constitution.md` → `<user config>/docs/constitution.md`
       — the supreme, cross-project one (ADR 0007/0015).
     - `docs/workflow/*` → `<user config>/docs/workflow/`
     - `docs/glossary.md` → `<user config>/docs/glossary.md`
     - `docs/product/requirements-template.md` and
       `docs/product/validation-summary-template.md` →
       `<user config>/docs/product/`
     - `docs/architecture/module-structure.md.template` and
       `frontend.md.template` → `<user config>/docs/architecture/`,
       and `docs/decisions/0000-adr-template.md` →
       `<user config>/docs/decisions/`. **Template sources only** —
       a lazy registration copies these into each new project's own
       subtree, and in mode C the shared root is the only place it can
       find them. Do **not** copy this framework's own ADRs
       (`0001-*.md` onward) or any resolved `architecture/*.md`: those
       are this repo's content, not a template.
     - `CLAUDE.md.template` (from this repo's root, if it's still
       there alongside the resolved `CLAUDE.md`) →
       `<user config>/CLAUDE.md.template`. Same reason: lazy
       registration resolves a new project's `CLAUDE.md` from it and
       has nowhere else to look in mode C. If this repo no longer has
       it (Domain 1 renames it), say so — registration will then have
       to ask the user for its path.

     If `docs/glossary.md` is still `glossary.md.template` here, or
     `constitution.md` is missing, stop and say so: that's Domain 1
     unfinished, same as step 1's check.

   Classify every file as **new** (nothing of that name at the
   destination) or **collision** (a file of that name already exists),
   and present both lists with `AskUserQuestion` before copying
   anything.
4. Copy the **new** files. For every **collision**, stop and ask per
   file — never overwrite, never merge two files' contents:
   - **Keep mine** (skip this file) — the default. Say plainly what it
     costs: skipping `commands/spec.md`, for instance, means `/spec`
     keeps doing whatever the user's existing file does, which breaks
     the pipeline at that stage rather than degrading it.
   - **Let me rename mine first** — pause, let the user move their file
     aside, then re-check that name and copy.

   A personal `~/.claude/skills/` entry or an unrelated command with a
   colliding name is the user's, exactly as Domain 3 treats an existing
   `mcpServers` entry. Report per file which of the two happened.

   The same applies to the shared `docs/` files: a
   `<user config>/docs/constitution.md` that already exists is almost
   always this framework's own, amended by the user since a previous
   run (ADR 0007's Governance procedure) — never overwrite it, and say
   plainly that it was kept.
5. `<user config>/settings.json`:
   - **Doesn't exist**: write it from
     `.claude/settings.multi-project.json.example`, resolving its one
     placeholder `{{HOOKS_DIR}}` → `~/.claude/hooks` (literally, tilde
     included — every hook in this framework runs in shell form, which
     expands `~`; the existing `${CLAUDE_PROJECT_DIR:-.}` syntax is
     itself bash parameter expansion, so bash-compatible execution was
     already load-bearing before mode C, see ADR 0014). If step 2
     resolved a relocated `CLAUDE_CONFIG_DIR`, use that directory's
     absolute `hooks/` path instead. Don't use `settings.example.json`:
     it bakes one project's build/test command and language values into
     static text, which cannot work for a file shared by every project
     on the machine.
   - **Already exists**: merge additively, never replacing.
     - Parse both. If either doesn't parse, stop and report — don't
       guess, don't overwrite.
     - For each hook event (`SessionStart`, `SessionEnd`,
       `PreToolUse`, `PostToolUse`, `SubagentStop`), append this
       framework's groups to the existing array. If a group with the
       same `matcher` + `if` already exists, add only the individual
       entries whose `command` (or, for an `agent` hook, whose
       `statusMessage`) isn't already present in it. Never remove,
       reorder, or rewrite an existing entry, and never replace an
       existing hook that shares a trigger — add alongside it.
     - For `permissions.allow`, append only strings not already there.
     - Leave every other key in the user's file untouched.
   - Either way, show the exact diff and confirm (`AskUserQuestion`)
     before writing.
6. Ask once for the **projects root** — the folder under which every
   registered project's `<name>/` subtree (its `CLAUDE.md`,
   `project-config.json`, `product/specs/`, `architecture/` and
   `decisions/`) gets created. This is asked once per machine, here,
   and never again: a lazy registration later reads the answer, it
   never re-asks it (ADR 0014). Present the trade-off, don't just
   prompt for a path:
   - **`<user config>/docs/`, offered as the default** — the shared
     root step 3 just created, with each project nesting one level
     inside it exactly as in mode B (ADR 0015). Nothing else to decide,
     everything in one place. **But it sits outside any repository
     you'd think to version**, so a machine loss takes every spec, ADR
     and architecture doc for every project with it. Say this when
     offering it — it's the one real cost of the default, and the
     mechanism no longer forces it.
   - **Any folder you already version or sync** — a personal notes
     repo, a synced drive folder, anything. Removes the backup risk
     entirely, and costs nothing: routing entries store an absolute
     subtree path either way, so nothing in the mechanism cares where
     the subtrees actually sit. The shared `docs/` root stays at
     `<user config>/docs/` regardless — only the per-project subtrees
     move, and commands find shared material by the registry's
     `.claude` location, not by the projects root.

   Accept any absolute folder path. Create it if it doesn't exist
   (confirm first). Don't validate it beyond "a writable directory on
   this machine".
7. Write `<user config>/projects.local.json` — the same file Domain 5
   writes inside an AI-repo, here sitting **directly inside
   `~/.claude`** as a sibling of `agents/`, `commands/`, `skills/`,
   `hooks/` and `settings.json`. There's no extra nesting in this mode:
   `~/.claude` plays exactly the role `<ai-repo>/.claude` plays in
   Domain 5.
   - **Doesn't exist**: create it containing exactly
     `{"projects_root": "<the absolute path chosen in step 6>"}`.
     Nothing else — no project entries; that's step 8's whole point.
   - **Exists with the same `projects_root`**: no-op, report "already
     configured".
   - **Exists with a *different* `projects_root`**: stop and ask
     (`AskUserQuestion`), showing both paths. Changing this after
     projects already exist under the old root is genuinely disruptive:
     their routing entries keep pointing at the old subtrees while
     every new registration lands somewhere else. If the user does want
     the change, say plainly that this command moves nothing — existing
     subtrees stay where they are and keep working until moved by hand.
     Never change it silently.
   - **Exists but doesn't parse**: stop and report; never overwrite it.
   - Preserve any existing project entries verbatim in every case.
8. Close-out for this domain specifically — say all of this:
   - Which files were copied, and which collisions were skipped, naming
     what each skip costs.
   - That the shared `docs/` root now lives at `<user config>/docs/`
     (`constitution.md`, `workflow/`, `glossary.md`, the two `product/`
     templates, plus the `architecture/`/`decisions/` template sources
     and `CLAUDE.md.template` that lazy registration needs) — one copy
     for every project on this machine, and the place a command looks
     for shared material by absolute path, since mode C has no `docs`
     link anywhere. Note that this framework's *own* ADRs
     (`0001-*.md` onward) were deliberately not copied: they document
     the framework, not any registered project.
   - What happened to `settings.json`: created from the multi-project
     variant (with the resolved `{{HOOKS_DIR}}` value), or merged
     additively, listing exactly which entries were added.
   - The chosen projects root, and whether it carries the default's
     backup risk.
   - That **no code repo was touched at all** — no link, no file, no
     `.gitignore` line anywhere.
   - **Loudest: no project has been registered, and none needs to be
     registered here.** Registration is lazy by design (ADR 0014): the
     first time you run `/spec`, `/plan`, `/tasks`, `/implement`,
     `/review`, `/adr` or `/reconcile` inside an unregistered repo,
     that command pauses — via the `project-registration` skill it
     invokes as its own first step — asks for the project name,
     build/test command and language settings, creates
     `<projects root>/<name>/` with its `product/specs/`,
     `architecture/`, `decisions/`, `CLAUDE.md` and
     `project-config.json`, writes the routing entry, and *then*
     continues with what you actually asked for. Re-running
     `/setup-framework` per project is **not** how mode C works.

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
which domains ran and which were never applicable. Then end with a
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
- If Domain 6 ran: the user-level directory installed into, what was
  copied vs. skipped on a collision (including the shared `docs/` root
  — `constitution.md`, `workflow/`, `glossary.md`, the two `product/`
  templates), how `settings.json` was created/merged, the chosen
  projects root and whether it carries the
  default's backup risk — and, loudest, that **no project was
  registered and none needs to be**: the first pipeline command run in
  an unregistered repo registers it on the spot via the
  `project-registration` skill.
