---
name: project-registration
description: Resolves where this session's project docs actually live before a pipeline command reads or writes anything, rebinding project-content paths to a registered project's own subtree (ADR 0015 modes B and C), and registers an unregistered project on the spot when the framework runs user-level (ADR 0014 mode C). Invoked explicitly as the first step of /spec, /plan, /tasks, /implement, /review, /adr and /reconcile — never left to self-trigger.
---

Full rationale → `docs/decisions/0014-setup-framework-adoption-modes.md`
(three adoption modes, lazy registration),
`docs/decisions/0013-multi-project-ai-repo.md` (the routing/config split
this reuses) and `docs/decisions/0015-unified-docs-tree-and-layered-constitution.md`
(one unified `docs/` tree — **read this one if anything below surprises
you**). Hooks do the equivalent lookup in code via
`.claude/hooks/_project_paths.py`; this skill is the same rule for the
paths a *command* reads and writes itself.

**Non-negotiable invariant:** a pipeline command must never create
project content (a spec, an ADR, an edit to `CLAUDE.md` or
`architecture/*`) inside a target repo that this framework is not
supposed to touch, and must never create it in the **shared** `docs/`
root, where it would collide with every other project on the same
AI-repo. If you can't confirm where this session's project docs live,
stop and ask — do not write and hope.

## The layout you are resolving against (ADR 0015)

```text
<ai-repo>/  (or ~/.claude in mode C)
  .claude/                     <- the machinery, and projects.local.json
  docs/                        <- THE SHARED ROOT: constitution.md, workflow/,
                                  glossary.md, product/*-template.md
    <project-name>/            <- ONE PROJECT'S SUBTREE = what the registry points at
      CLAUDE.md
      project-config.json
      constitution.md          <- optional, project-owned, may not exist
      product/specs/
      architecture/module-structure.md, frontend.md
      decisions/
```

Two things follow, and they are the whole reason this skill exists:

- **There is no second `docs/` level inside a subtree.** A spec is
  `<subtree>/product/specs/0001-x.md`, not
  `<subtree>/docs/product/specs/0001-x.md`.
- **In mode B the target repo's `docs` link points at the shared root**,
  not at the subtree. So `docs/workflow/...` and `docs/constitution.md`
  resolve correctly there, while a relative `docs/product/specs/0001-x.md`
  lands in the *shared* `product/` and collides across every project.
  Relative paths are safe for shared *reads* in mode B, and wrong for
  project content in both B and C.

## Step 1 — Probe: is `docs/` reachable, and is there a registry? (cheap, always first)

One call, and in the common case it is the only call this skill costs:

```bash
P="${CLAUDE_PROJECT_DIR:-.}"
echo "project: $P"
[ -d "$P/docs" ] && echo "docs: reachable" || echo "docs: UNREACHABLE"
[ -f "$P/.claude/projects.local.json" ] && echo "registry: $P/.claude/projects.local.json"
[ -f "$HOME/.claude/projects.local.json" ] && echo "registry: $HOME/.claude/projects.local.json"
exit 0
```

(`-d` is false for a broken link too, which is the right answer: a mode
B repo whose links didn't survive a fresh clone is not reachable either.)

**Decide from both lines together — `docs: reachable` on its own no
longer means mode A.** Since ADR 0015 a mode B target repo also reports
`docs: reachable` (the link points at the shared root), so treating
that as "stop, relative paths" would write this project's specs into
the shared root. What tells A and B apart is **a registry entry for
this `CLAUDE_PROJECT_DIR`**, not the link:

- **No `registry:` line at all** — nothing to route with:
  - `docs: reachable` → **mode A** (skeleton copied into the repo).
    **Stop here. Say nothing.** Every path the command already uses
    (`docs/product/specs/...`, `CLAUDE.md`, ...) resolves correctly
    as-is; continue with the command exactly as written, relative paths
    and all. This is the common case and must stay this cheap.
  - `docs: UNREACHABLE` → **stop the command** and report it (see step
    2's "No registry at all").
- **A `registry:` line is printed** → go to step 2 and do the lookup,
  whichever way the `docs:` line came out. One small JSON read; the
  answer decides everything after it.

## Step 2 — Find the registry and this project's entry

Use the registry paths already printed in step 1, in this order —
project root first, then `~/.claude` (the same two places Claude Code
itself looks for `.claude/`, so this is correct however the session got
here):

1. `<CLAUDE_PROJECT_DIR>/.claude/projects.local.json`
2. `~/.claude/projects.local.json` — equivalently, beside the `.claude/`
   directory this skill file itself was loaded from, which is the same
   folder unless the developer relocated their user config.

First one that exists wins — the same order and the same fallbacks
`.claude/hooks/_project_paths.py` uses, so a command and a hook never
disagree about which project this session is. It is flat JSON:

```json
{
  "projects_root": "<absolute path where new project subtrees are created>",
  "<absolute CLAUDE_PROJECT_DIR of a registered repo>": "<absolute path to that project's subtree>"
}
```

Match this session's `CLAUDE_PROJECT_DIR` against the keys **tolerantly,
not by raw string equality**: ignore a trailing separator, treat `\` and
`/` as equivalent, and compare case-insensitively on Windows.

- **Entry found** → this is mode B or C. From here on the two are
  identical; go to step 4. If the subtree it names doesn't exist on
  disk, stop and say so (a stale entry — the subtree was moved or
  deleted); don't silently recreate it and don't fall back to relative
  paths.
- **No entry for this `CLAUDE_PROJECT_DIR`, and `docs: reachable`** →
  this is **mode A**, or a session running inside the AI-repo's own
  root. Stop here, say nothing, continue with relative paths exactly as
  in step 1's mode A case. **Never register a project whose own `docs/`
  is already reachable** — registering it would rebind writes away from
  a tree that is already correct.
- **No entry for this `CLAUDE_PROJECT_DIR`, and `docs: UNREACHABLE`** →
  go to step 3. This is an unregistered mode C project. Do **not**
  create `docs/` in the target repo to "fix" the unreachable path: a
  real `docs/` inside the target repo is exactly the footprint mode C
  exists to avoid.
- **No registry at all** (reached only with `docs: UNREACHABLE`) →
  **stop the command here** and tell the user plainly: this session
  can't reach `docs/` and no `projects.local.json` exists in either
  location, so mode C was never set up on this machine (or, if this repo
  was set up in mode B, its `.claude`/`docs`/`CLAUDE.md` links are
  missing or broken). Point them at `/setup-framework` — Domain 6 for
  mode C setup, which is what chooses and records `projects_root`.
  Never invent a `projects_root` yourself, and never fall back to
  writing into the target repo. Same stop if the registry exists but
  has no `projects_root` key.

## Step 3 — Register this project, then continue

Pause the command here, before doing any of what it was actually asked
to do. Registration is a prerequisite, not a side quest — but it is also
not the user's request, so keep it to one question batch and one report
line.

**Ask once** (a single `AskUserQuestion` call, four questions):

- [ ] **Project name** — default: the target repo's own folder name
      (`basename "$CLAUDE_PROJECT_DIR"`). This becomes
      `<projects_root>/<name>/`.
      - **Reserved names, reject and ask again:** `workflow`,
        `product`, `architecture`, `decisions`, `glossary`. Each is a
        folder the shared `docs/` root already owns, and a project of
        that name collides with it (ADR 0015). Say which shared folder
        it collides with; never silently rename it yourself.
      - If a subtree with that name already exists under
        `projects_root`, never overwrite it: ask whether it's the same
        project (then create nothing — write only the routing entry) or
        a different one that needs another name.
- [ ] **Build/test command** — detect first, offer the detected value as
      the default, same detection Domain 1 uses: `.sln`/`.csproj` →
      `dotnet test`; a `package.json` `test` script → `npm test`; both →
      the two chained; neither → ask outright.
- [ ] **Canonical language** — default English.
- [ ] **Stakeholder language** — offer **"same as canonical — skip the
      split"** as an explicit option. If chosen, set `stakeholder_lang`
      and `stakeholder_lang_code` to the canonical values; the
      split's own steps already no-op when they are equal.

**First locate the shared `docs/` root**, since every template below is
copied out of it. It is `docs/` in the directory that holds the
registry's `.claude` (mode B: `<ai-repo>/docs`), or `docs/` inside that
`.claude` directory itself (mode C: `~/.claude/docs`) — whichever
exists. Call it `<shared>`; step 4 uses the same value, so resolve it
once here and keep it.

**Then create, under `<projects_root>/<name>/`** — note there is no
`docs/` level inside the subtree, the subtree is itself the project's
docs (ADR 0015):

- [ ] `product/specs/` — empty. `spec_index.py` generates its
      `README.md` when the first spec lands; don't hand-write one.
- [ ] `architecture/` — `<shared>/architecture/module-structure.md.template`
      and `frontend.md.template`, copied **as templates, unfilled**,
      exactly as a fresh Domain 1 skeleton leaves them. Describing a
      project's real dependency rules is a standing judgment call and is
      not this skill's job.
- [ ] `decisions/0000-adr-template.md` — copied from
      `<shared>/decisions/0000-adr-template.md`, that file only, verbatim
      with its own `{{DATE}}` left literal. This project's ADRs start at
      0001 (ADR 0013: numbering is per-project); never copy the
      framework's own `0001-*.md` onward into a project.
- [ ] `CLAUDE.md` — resolved from the framework's own
      `CLAUDE.md.template`. Look for it in order: inside the directory
      that holds the registry's `.claude` (the AI-repo root in mode B),
      then inside that `.claude` directory itself (mode C: Domain 6
      copies it there, because the template has no other home once the
      machinery lives under `~/.claude`), then beside `projects_root`.
      Resolve **every**
      `{{PLACEHOLDER}}` in it (`grep -o "{{[A-Z_]*}}"` the template —
      don't work from memory of which ones exist): the four answered
      above fill the language and build/test ones; detect the rest from
      the target repo the way Domain 1 does (`{{PROJECT_NAME}}` from the
      folder/`package.json`, `{{MAIN_INTEGRATION_BRANCH}}` from `git
      symbolic-ref refs/remotes/origin/HEAD`, stack/database/auth from
      root manifests). Only ask about something detection genuinely
      can't answer, and fold it into the same question batch above.
      Delete the language-split paragraph if canonical and stakeholder
      language are equal — the template says to. If no template is
      findable at all, say so and ask the user for its path rather than
      writing a bare stub: a placeholder-riddled `CLAUDE.md` is worse
      than none, because it looks resolved at a glance.
- [ ] `project-config.json` — flat, exactly these keys:
      `{"build_test_cmd": "...", "canonical_lang": "...",
      "stakeholder_lang": "...", "stakeholder_lang_code": "..."}`.
- [ ] **No `constitution.md`.** The shared root's `constitution.md`
      already binds this project; a project's own
      `<subtree>/constitution.md` is purely additive and project-owned
      (ADR 0015), so it is created only when that project actually
      writes its own principles. **Don't pre-create an empty stub** — a
      stub reads as "this project has its own constitution" to every
      stage that checks for one.

**Then write the routing entry** into the registry found in step 2: one
new key, this session's `CLAUDE_PROJECT_DIR` as an absolute path with no
trailing separator, valued at the absolute
`<projects_root>/<name>` path. Preserve every existing key, including
`projects_root` — read, add, write back; never rewrite the file from
scratch.

Report it in one line ("registered `<name>` → `<subtree>`"), then
continue with step 4 and, after it, with whatever the command was
actually asked to do.

## Step 4 — Rebind this command's paths, for the rest of this command

This is the point of the whole skill, and it applies to **mode B and
mode C alike** (ADR 0015: mode B's `docs` link points at the shared
root, so it does not redirect project content for you). There is no
link and no filesystem trick doing this for you: **the only thing that
makes a write land in the right place is that your own Read/Write/Edit
calls name the resolved absolute path.**

First resolve the two roots you need, and hold both:

- **`<subtree>`** — the absolute path the registry entry gave you. This
  project's own content, and nothing else, lives here.
- **`<shared>`** — the shared `docs/` root: `docs/` in the directory
  that holds the registry's `.claude` (mode B: `<ai-repo>/docs`), or
  `docs/` inside that `.claude` directory itself (mode C:
  `~/.claude/docs`). Whichever of the two exists. In mode B this is
  also what the target repo's own `docs` link points at, so relative
  `docs/...` reads of shared material work there — but use the absolute
  form anyway, so one rule covers both modes.

Then read `<subtree>/project-config.json` and state the binding in one
short line of your reply, e.g.:

> For this session: this project's docs are `<subtree>/`, shared
> framework material is `<shared>/`, `CLAUDE.md` means
> `<subtree>/CLAUDE.md`.

For every remaining step of this command:

- [ ] **Use the absolute path, not the relative one — in mode B too.**
      A spec is written to `<subtree>/product/specs/0001-foo.md` —
      never `docs/product/specs/0001-foo.md` (which lands in the shared
      root) and never `<subtree>/docs/product/specs/...` (there is no
      such level). Same for `<subtree>/decisions/`,
      `<subtree>/architecture/`, `<subtree>/CLAUDE.md`. This holds for
      reads too, and for every path you hand to a subagent (`coder`,
      `reviewer`, `architect`, `triage`): a subagent inherits none of
      this reasoning, so give it resolved absolute paths or it will
      write into the target repo or the shared root.
- [ ] **Shared framework material is at `<shared>`, never in the
      subtree.** `<shared>/product/requirements-template.md`,
      `<shared>/product/validation-summary-template.md`,
      `<shared>/workflow/*`, `<shared>/constitution.md`,
      `<shared>/glossary.md`. Mode C has no `docs` link at all, so
      those relative paths resolve to nothing there — a command needs
      to be told both roots, which is why step 4 states both. If a file
      genuinely isn't at `<shared>`, say so and continue without it —
      **never** recreate it inside the target repo or inside the
      project subtree.
- [ ] **Two constitutions, when the project has its own.**
      `<shared>/constitution.md` is the supreme one and always applies;
      `<subtree>/constitution.md` is this project's additive extension
      and **often does not exist** — that is normal, not a setup
      failure. Hand both paths to anything that checks the constitution,
      and say plainly when the project-level one is absent rather than
      inventing or creating it.
- [ ] **Wherever the command body says `{{CANONICAL_LANG}}`,
      `{{STAKEHOLDER_LANG}}`, `{{STAKEHOLDER_LANG_CODE}}` or
      `{{BUILD_TEST_CMD}}`, use this project's `project-config.json`
      value** — a shared command file can't have had those resolved into
      it, since one copy serves every registered project (ADR 0013).
      Missing or malformed config: say so and ask rather than guessing a
      language or a test command.
- [ ] **Source code stays where it is.** Only the framework's own
      artifacts rebind. The actual repo being worked on is still
      `CLAUDE_PROJECT_DIR`, and `coder`'s edits, builds and tests all
      belong there.
