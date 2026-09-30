---
doc_type: adr
id: 0015
status: accepted
date: 2026-09-25
supersedes: 0013
superseded_by: null
context_budget: ~1100 tokens
---

# ADR 0015 — One unified `docs/` tree per AI-repo, and a two-layer constitution

Like ADR 0001–0014, this documents a decision about *this framework's
own* tooling.

**Amends ADR 0013's layout.** 0013's `projects/<name>/` tree is replaced
by the one below; everything else 0013 decided stands unchanged and is
restated under "What survives from 0013". It also corrects one specific
claim in ADR 0014 (see Consequences) without touching 0014's own
decision.

## Context

ADR 0013 placed shared material at `ai-repo/docs/` and per-project
content at `ai-repo/projects/<name>/docs/` — two disconnected trees.
Implementing it exposed the flaw: a target repo's `docs` link can point
at one or the other, never both. Pointing it at the project subtree, as
implemented, makes `docs/workflow/ai-first-development.md`,
`docs/constitution.md` and `docs/glossary.md` unreachable from a linked
target repo — directly contradicting 0013's own "Shared `docs/workflow/`
is genuinely shared" consequence. The implementer worked around it by
seeding a per-project *copy* of shared material, which contradicts that
same consequence from the other side: edits to the shared original stop
propagating. The gap was flagged rather than silently decided, which is
what this ADR resolves.

Separately, ADR 0007's constitution is a single `docs/constitution.md`
with one "Principle VI" placeholder slot for project-specific
principles. With one AI-repo backing several projects, that single file
has to serve two different jobs at once: cross-project non-negotiables,
and one project's own rules.

## Options considered

- **Seed shared material into each project subtree** (the implementation
  workaround). Rejected as a permanent answer: N copies that drift the
  moment one is edited, which is the exact failure 0013 exists to
  prevent for machinery.
- **Give the target repo a fourth link for shared material** (`docs` →
  project subtree, plus e.g. `shared-docs` → `ai-repo/docs`). Rejected:
  one more per-machine link to recreate, a path shape no existing hook
  or command knows, and it generalizes to nothing in mode C, which has
  no links at all.
- **Symlink each shared subfolder into every project subtree.**
  Rejected for the same reason 0013 rejected nested links: a link inside
  a linked directory, recreated per machine, with junction/symlink
  fragility on Windows.
- **One unified `docs/` tree, with each project as a subfolder of it
  (chosen).** One link, one root, shared material at the top, project
  content one level down.

## Decision

**There is no `projects/` folder.** Shared material stays at the `docs/`
root; each registered project gets `docs/<project-name>/`:

```text
ai-repo/                             (or ~/.claude for mode C)
  .claude/                           <- shared machinery, unchanged
  docs/
    constitution.md                  <- supreme, cross-project
    workflow/                        <- shared
    glossary.md                      <- shared
    product/requirements-template.md, validation-summary-template.md
    <project-name>/
      CLAUDE.md                      <- this project's own
      project-config.json            <- this project's own, unchanged shape
      constitution.md                <- this project's own extension
      product/specs/
      architecture/module-structure.md, frontend.md
      decisions/                     <- starts with only 0000-adr-template.md
```

`projects.local.json` keeps its exact shape and role — per-machine,
gitignored, keyed by the live `CLAUDE_PROJECT_DIR` — but its values now
name `docs/<name>/`, and its `projects_root` default changes from
`<ai-repo>/projects` to `<ai-repo>/docs` (mode B) or `~/.claude/docs`
(mode C, still overridable to any folder, for ADR 0014's unchanged
reasons).

**Mode B's `docs` link points at the shared root** (`ai-repo/docs`) —
that is what makes shared material relatively reachable again, and it is
the only arrangement that serves both purposes with one link. The
consequence is that a *relative* project-content path is now wrong in
mode B: `docs/product/specs/0001-x.md` lands in the shared root's
`product/`, colliding across every project on that AI-repo, instead of
in `docs/<name>/product/specs/`. So mode B joins mode C in requiring
resolved paths for project content, and only *shared-material reads*
stay relatively transparent there.

**Two constitutions in modes B and C:**

- `docs/constitution.md` — ADR 0007's existing content, now explicitly a
  **floor**: every linked project is bound by it.
- `docs/<name>/constitution.md` — that project's own additional
  principles. It may only **add**; it may never weaken or contradict a
  supreme principle. This replaces ADR 0007's single "Principle VI"
  placeholder for multi-project modes — a project can have as many of
  its own principles as it needs, not one slot.
- **Mode A is unchanged**: one `docs/constitution.md`, no layering. The
  split is a multi-project concept only.
- Enforcement posture is unchanged and deliberately not strengthened:
  `constitution_amendment_check.py` watches both files independently,
  nudging on unversioned drift exactly as it does today. "Never weakens
  the supreme one" stays a semantic judgment `reviewer`/`coder` make
  while reading both — no syntactic contradiction-detector, which is not
  a thing any hook in this codebase attempts.
- Every stage that reads the constitution per ADR 0007 (`/spec`,
  `/plan`, `coder`/`quickfix`, `reviewer`) reads **both** when both
  exist: the supreme one as non-negotiable, the project one as additive.

**What survives from 0013**, unchanged and still in force: one shared
`.claude/` holding all machinery; the split between per-machine routing
(`projects.local.json`) and committed per-project config
(`project-config.json`) by lifecycle; the two-step, fail-open lookup;
and `resolve_project_root()`'s contract.

## Rationale

The two trees were never two *kinds* of thing — they were one
documentation tree that had been cut in half by an implementation
detail. Nesting projects inside the shared root restores the property
0013 actually wanted (shared material is shared, per-project material is
separate) with strictly less machinery: one link instead of two, no
copies to drift, no nested links.

Reading `.claude/hooks/_project_paths.py` confirms the code cost is
near-zero, rather than assuming it: the module hardcodes no path segment
at all — `PROJECTS_ROOT_KEY` is a JSON key, not a folder name — and
`resolve_project_root()` returns whatever absolute path the registry
hands it. Its callers consume that opaquely. Changing where subtrees are
created therefore changes registry *values*, not the contract or any
hook that depends on it.

The constitution layering follows the same shape as the docs tree: one
shared thing at the root, one project-specific thing nested under it,
with the shared one taking precedence. Making the supreme layer a floor
that projects may only extend keeps a single, predictable answer to
"which rule wins" without inventing a precedence system.

## Consequences

- **ADR 0014's claim that only mode C needs path substitution is now
  wrong**, and this ADR corrects it: 0014's Consequences describe mode B
  as the case "where the `docs` link made those paths work
  transparently". That held only while the link pointed at the project
  subtree. Under the unified tree it is true for shared-material reads
  and false for project-content reads and writes. 0014's actual decision
  — the three modes and lazy registration — is untouched.
- **`.claude/skills/project-registration/SKILL.md` needs real rework,
  not a prefix tweak.** Its step 1 fast path currently concludes that
  `docs: reachable` means "mode A or B — stop, say nothing, use relative
  paths"; under the unified tree that silently writes project content
  into the shared root. Modes A and B must now be told apart, which is
  cheap because step 1's single bash call already reports registry
  presence: no registry entry for this `CLAUDE_PROJECT_DIR` means mode
  A (stop, relative paths, genuinely unchanged); an entry means mode B
  (rebind to the subtree). Recommend rebinding to the resolved
  **absolute** subtree path in both B and C rather than a relative
  `docs/<name>/...` — one rule instead of two, and subagents already
  require absolute paths per that skill's own step 4.
- **`constitution_amendment_check.py` needs more than a second path.**
  It matches on the final two path components being exactly
  `docs/constitution.md`, so `docs/<name>/constitution.md` never
  matches; and it derives the git repo root as the file's
  grandparent, then runs `git show HEAD:docs/constitution.md` — both
  wrong for a project constitution, whose committed path is
  `docs/<name>/constitution.md`. Its own docstring comment ("the
  constitution is *shared* framework material: it never moves into a
  project subtree") is invalidated by this ADR and must be rewritten,
  not left to mislead the next reader.
- **`.gitignore.framework-additions` patterns move** from
  `projects/*/session-handoff.md` (and the three beside it) to
  `docs/*/...`. Miss this and per-machine state starts getting committed
  — and it is now committed into the *docs* tree, where it is more
  likely to be mistaken for content.
- **Per-project state files now live inside a `docs/` tree**
  (`docs/<name>/session-handoff.md`, `pipeline-metrics.jsonl`,
  `settings.local.json`, `.plugin-gap-dismissed.json`). Accepted for
  the simplicity of "everything project-specific nests under
  `docs/<name>/`", but it does mean a `docs/` tree that is no longer
  purely documentation.
- **Project names now share a namespace with shared folder names.** A
  project called `workflow`, `product`, `architecture`, `decisions` or
  `glossary` would collide with shared material at the `docs/` root.
  Registration must reserve those names and ask for another.
- **Roughly nine files reference the `projects/` layout today** —
  `setup-framework.md`, `project-registration/SKILL.md`,
  `.gitignore.framework-additions`, `settings.multi-project.json.example`,
  `run_build_test.py`, `_project_paths.py`'s docstrings, both READMEs and
  an architecture template. Most are prose or a registry default; the
  skill and the constitution hook are the only two carrying real logic
  changes.
- **ADR 0010's technical enforcement is unaffected** — none of it reads
  the constitution file. Only `security-review`'s "map this finding to a
  named principle" framing gains a second file to consider.
- **This ADR is filed as an amendment, not a supersession**
  (`supersedes: null`), because 0013's mechanism — not just its
  reasoning — remains the live contract that `_project_paths.py` and ADR
  0014 both depend on. Marking 0013 superseded would read, in the index
  and to any future agent, as retiring that mechanism too. The accepted
  cost: 0013 stays `accepted` while containing a tree diagram this ADR
  replaces, so the amendment notice at the top of this file is the only
  thing connecting them for a reader who opens 0013 first.

## References

`docs/decisions/0013-multi-project-ai-repo.md`,
`docs/decisions/0014-setup-framework-adoption-modes.md`,
`docs/decisions/0007-constitution-document.md`,
`docs/decisions/0010-constitution-technical-enforcement.md`,
`.claude/hooks/_project_paths.py`,
`.claude/hooks/constitution_amendment_check.py`,
`.claude/skills/project-registration/SKILL.md`,
`.gitignore.framework-additions`
