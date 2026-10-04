---
name: project-registration
description: Resolves where this session's project docs actually live before a pipeline command reads or writes anything, rebinding project-content paths to a registered project's own subtree (framework ADR 0015 modes B and C), and registers an unregistered project on the spot when the framework runs user-level (framework ADR 0014 mode C) — one repo, or several in one pass. Invoked explicitly as the first step of /spec, /plan, /tasks, /implement, /review, /adr, /reconcile, /quick and /update-docs — never left to self-trigger.
---

Full rationale → framework ADR 0014
(three adoption modes, lazy registration),
framework ADR 0015
(one unified `docs/` tree — **read this one if anything below surprises
you**) and framework ADR 0017 (the
install namespace, `framework.json`, the registration gate). Hooks do the
same lookup in code via `.claude/hooks/_project_paths.py`. This skill
runs that same module, so a command and a hook never disagree about
which project a session belongs to.

**Non-negotiable invariant:** a pipeline command must never create
project content (a spec, an ADR, an edit to `CLAUDE.md` or
`architecture/*`) inside a target repo that this framework is not
supposed to touch, and must never create it in the **shared** `docs/`
root, where it would collide with every other project. If you can't
confirm where this session's project docs live, stop and ask — do not
write and hope.

## The layout you are resolving against (framework ADR 0015)

```text
<ai-repo>/  (or the install namespace, e.g. ~/.claude/cfw, in mode C)
  .claude/ or hooks/, scripts/ <- the machinery, and projects.local.json
  docs/                        <- THE SHARED ROOT: constitution-baseline.md,
                                  constitution.md, workflow/, glossary.md,
                                  product/*-template.md, decisions/0000-adr-template.md
    <project-name>/            <- ONE PROJECT'S SUBTREE = what the registry points at
      CLAUDE.md
      project-config.json
      constitution.md          <- optional, project-owned, may not exist
      product/specs/
      architecture/module-structure.md, frontend.md
      decisions/
```

There is **no second `docs/` level inside a subtree**: a spec is
`<subtree>/product/specs/0001-x.md`. And in mode B the target repo's
`docs` link points at the shared root, so a relative
`docs/product/specs/...` lands in the *shared* `product/` and collides
across projects. Relative paths are safe for shared *reads* in mode B,
and wrong for project content in both B and C.

## Step 1 — Probe (one call, always first)

If this file starts with an **Install binding** block (a user-level
install writes one, framework ADR 0017), the paths in it are authoritative. Use its
probe command. Otherwise run:

```bash
python "${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/_project_paths.py" describe
```

It prints JSON: `mode`, `registered`, `subtree`, `shared_docs_root`,
`projects_root`, `registry`, `claude_md_template`, `scripts_dir`,
`project_config` and `main_integration_branch`. Decide on `mode`:

- **`A`** — skeleton copied into this repo, no registry entry. **Stop
  here. Say nothing.** Every relative path the command uses
  (`docs/product/specs/...`, `CLAUDE.md`, ...) is already right.
  Also the answer for a session in an AI-repo's own root. **Never
  register a repo whose own `docs/` is already reachable.**
- **`B`** or **`C`** — registered. Go to step 4.
- **`C-unregistered`** — a user-level install, or a registry, but no
  entry for this repo. Go to step 3. Never create `docs/` in the target
  repo to "fix" this: a real `docs/` there is exactly the footprint mode
  C exists to avoid.
- **`unconfigured`** — no `docs/`, no registry, no install. **Stop the
  command** and say so plainly: mode C was never set up on this machine,
  or this mode B repo's `.claude`/`docs`/`CLAUDE.md` links are missing or
  broken. Point at `/setup-framework` (Domain 6 for mode C, Domain 5 to
  re-link mode B). Never invent a projects root, never write into the
  target repo.

If `registered` is true but `subtree` doesn't exist on disk, stop and
say so — a stale entry. Don't recreate it, don't fall back to relative
paths.

## Step 2 — (merged into step 1)

The registry lookup, its tolerant key matching (separators, trailing
slash, Windows case) and the `framework.json` override all happen inside
`describe`. Don't redo them by hand.

## Step 3 — Register this project, then continue

Pause the command here, before doing any of what it was asked to do.
Registration is a prerequisite, not a side quest — one question batch,
one report line.

**Ask once** (a single `AskUserQuestion` call, four questions):

- [ ] **Project name** — default: the repo's own folder name. It becomes
      `<projects_root>/<name>/`. **Reserved, reject and ask again:**
      `workflow`, `product`, `architecture`, `decisions`, `glossary` —
      each collides with a folder the shared root owns (framework ADR 0015).
- [ ] **Build/test command** — offer the detected value as the default:
      `.sln`/`.csproj` → `dotnet test`; a `package.json` `test` script →
      `npm test`; both → the two chained; neither → ask outright.
- [ ] **Canonical language** — default English.
- [ ] **Stakeholder language** — offer **"same as canonical — skip the
      split"** explicitly; then the stakeholder values equal the
      canonical ones and every split step no-ops.

**Then let the registration script do the mechanical part** — it is
deterministic and it refuses anything unsafe (reserved name, an existing
subtree, an unparseable registry). Dry run first, then `--apply`:

```bash
python "<scripts_dir>/register_project.py" --repo "$CLAUDE_PROJECT_DIR" \
  --name <name> --build-test-cmd "<cmd>" --canonical-lang <lang> \
  --stakeholder-lang <lang> --stakeholder-lang-code <code> [--apply]
```

It creates, under `<projects_root>/<name>/`: an empty `product/specs/`;
`architecture/` with the shared templates copied unfilled;
`decisions/0000-adr-template.md` only (this project's ADRs start at
0001; framework ADR 0013); `project-config.json` (build/test command, languages,
`main_integration_branch` detected from `origin/HEAD`,
`review_policy: per-task`, census off); and `CLAUDE.md` from the
template with every value it can know filled in. It writes the routing
entry, preserving every other key. It **never** creates a
`constitution.md` in the subtree: the shared layers already bind the
project, and a project layer exists only once the project writes its
own principles.

The script reports which placeholders it left in `CLAUDE.md` (stack,
database, auth, description). Fill those by detecting from the repo's
root manifests the way Domain 1 does, asking only what detection can't
answer. If canonical and stakeholder language are equal, delete the
template's language-split paragraph, as the template itself says.

If the subtree already exists, the script stops. Ask whether it's the
same project (re-run with `--existing-subtree same`: routing entry only)
or a different one that needs another name.

Report in one line ("registered `<name>` → `<subtree>`"), then go to
step 4 and then on to the command's actual work.

### Bulk registration (framework spec 0001 FR-11)

To register several existing repos in one pass, ask the shared questions
(languages, and a build/test command only if one fits them all) **once**.
Then write a plan file and run the same script over it:

```json
{"shared": {"canonical_lang": "English", "stakeholder_lang": "English",
            "stakeholder_lang_code": "en"},
 "projects": [{"repo": "C:/src/orders", "name": "orders"},
              {"repo": "C:/src/billing", "build_test_cmd": "dotnet test Billing.sln"}]}
```

```bash
python "<scripts_dir>/register_project.py" --plan plan.json [--apply]
```

A project with no `build_test_cmd` of its own gets the detected one. The
dry run lists every repo whose detection found nothing: ask only about
those. Then fill each `CLAUDE.md`'s remaining placeholders the same way
as above.

## Step 4 — Rebind this command's paths, for the rest of this command

This applies to **mode B and mode C alike**. No link or filesystem trick
redirects anything: the only thing that makes a write land in the right
place is that your own Read/Write/Edit calls name the resolved absolute
path. From the probe's output, hold:

- **`<subtree>`** — this project's own content, and nothing else.
- **`<shared>`** — `shared_docs_root`: framework material shared by every
  project.

State the binding in one short line of your reply, e.g.:

> For this session: this project's docs are `<subtree>/`, shared
> framework material is `<shared>/`, `CLAUDE.md` means
> `<subtree>/CLAUDE.md`.

For every remaining step of this command:

- [ ] **Use the absolute path, not the relative one — in mode B too.**
      A spec is `<subtree>/product/specs/0001-foo.md`, never
      `docs/product/specs/0001-foo.md` (the shared root) and never
      `<subtree>/docs/...` (no such level). Same for `decisions/`,
      `architecture/` and `CLAUDE.md`. This holds for reads too, and
      for every path you hand to a subagent: it inherits none of this
      reasoning, so give it resolved absolute paths.
- [ ] **Shared material is at `<shared>`, never in the subtree:**
      `requirements-template.md`, `validation-summary-template.md`,
      `workflow/*`, `glossary.md`, the constitution layers. (The
      framework's own ADRs and specs, cited as "framework ADR NNNN", are
      never in a project or a shared root: they live in the framework
      repository's `evolution/`.) If a file genuinely isn't there, say
      so and continue without it — never recreate it in the target repo
      or the subtree.
- [ ] **Up to three constitution layers** (framework ADR 0015, framework ADR 0018), each
      adding to and never weakening the one above:
      `<shared>/constitution-baseline.md` (framework baseline, I–V),
      `<shared>/constitution.md` (organization layer), and
      `<subtree>/constitution.md` (this project's own, **often absent** —
      normal, not a setup failure). Hand every existing path to anything
      that checks the constitution.
- [ ] **Runtime values.** Wherever a command body says
      `<canonical_lang>`, `<stakeholder_lang>`, `<stakeholder_lang_code>`,
      `<build_test_cmd>` or `<main_integration_branch>` — or, in an
      un-installed copy, the matching double-brace placeholder — use this
      project's `project_config` value. For the main branch, use the
      probe's `main_integration_branch`. It comes from
      `project-config.json`, or `origin/HEAD` when unset. `<project name>`
      is the subtree's folder name. Missing or malformed config: say so
      and ask rather than guessing a language, branch or test command.
- [ ] **Framework scripts** (`census.py`, `metrics.py`,
      `register_project.py`) live in the probe's `scripts_dir`.
- [ ] **Source code stays where it is.** Only the framework's own
      artifacts rebind. The repo being worked on is still
      `CLAUDE_PROJECT_DIR`, and every code edit, build and test belongs
      there.
