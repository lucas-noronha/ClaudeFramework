---
doc_type: workflow
scope: framework-evolution
status: active
resumo: Where does the framework's own development history live, and what never ships to a project?
naoResponde: How to use the framework in a project — see the root README.md.
context_budget: ~650 tokens
---

# `evolution/` — the framework's own development history

This folder holds the documents about **how this framework evolves**: its
specs and its architecture decision records. None of it is part of the
skeleton a project receives (framework ADR 0021).

```text
evolution/
  product/specs/      <- the framework's own specs (0001, 0002, ...) + index
  decisions/          <- the framework's own ADRs (0001-...) + index
  project-config.json <- lets the pipeline run on the framework itself
```

## The boundary

| Ships to projects (the skeleton) | Stays in this repository |
|---|---|
| `.claude/` — agents, commands, skills, hooks, scripts, settings templates | `evolution/` — framework specs and ADRs |
| `docs/` — constitution layers, workflow docs, templates (incl. `decisions/0000-adr-template.md`) | `tests/` — the framework's test suite |
| `CLAUDE.md.template`, `.mcp.json.example`, `.gitignore.framework-additions` | `README.md`, `CHANGELOG.md`, `.gitattributes`, `.gitignore` |

Mode A copies exactly the left column; the user-level installer (mode C)
installs only from it; a mode B AI-repo is a clone of this repository, so
it carries `evolution/` but never inside `docs/`, where projects nest.
`tests/test_skeleton_boundary.py` enforces all of this.

## Referring to these documents from shipped files

A project numbers its own ADRs and specs from 0001, so "ADR 0004" inside a
project means *that project's* ADR. Shipped files therefore always say
**"framework ADR NNNN"** / **"framework spec NNNN"**, and never give a
path into this folder (the project doesn't have it). The boundary test
rejects a bare `ADR 00NN` or an `evolution/` path in any shipped file.

## Running the pipeline on the framework itself

This folder has a project subtree's shape (ADR 0015), so the framework's
own `/spec`, `/plan`, `/tasks`, `/implement`, `/review` can work on it.
Route this repository to it once per machine:

- **Mode C install:**
  `python ~/.claude/cfw/scripts/register_project.py --repo <this repo> --subtree <this repo>/evolution --apply`
- **Running from this checkout:** put
  `{"<this repo, forward slashes>": "<this repo>/evolution"}` in
  `.claude/projects.local.json`. It's gitignored, per machine. Note that
  `/setup-framework` then reads this checkout as an AI-repo (mode B).

`project-config.json` makes the build/test gate run the framework's test
suite. The shared material (constitution, templates) resolves to this
repository's `docs/`.

## A note on history

ADRs 0001–0020 were written while they lived in `docs/decisions/`. The
accepted ones are immutable, so their bodies still cite
`docs/decisions/...` and `docs/product/specs/...` paths. Read those as
`evolution/decisions/...` and `evolution/product/specs/...`.
