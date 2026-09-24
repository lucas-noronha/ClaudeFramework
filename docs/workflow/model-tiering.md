---
doc_type: workflow
scope: model-tiering
status: active
last_updated: {{DATE}}
context_budget: ~500 tokens
related: [../decisions/0001-tooling-agents-commands-skills.md, ../decisions/0004-plan-tasks-implement-rebalance.md]
context: This doc was added while generalizing this framework — the
  tiering itself was real and deliberate in the source project, but
  only lived implicitly in each agent's frontmatter there. Written
  down here so the convention travels with the framework, not just
  with one project's memory of why it was set up this way.
---

# Model tiering across subagents

Each subagent's frontmatter pins a `model:` deliberately, not by
default. The rule: **match the model to how reversible a mistake at
that stage is, and how much judgment the task genuinely requires** —
not just its raw difficulty.

| Subagent | Tier | Why this tier |
|---|---|---|
| `triage` | cheapest (e.g. haiku) | A 1-sentence classification. Getting it wrong just routes to the wrong next stage, which the next stage's own read of the task will usually catch — low cost of error, and the task itself needs no real judgment. |
| `quickfix` | cheapest (e.g. haiku) | Scoped, by construction, to single-file/no-new-rule changes. If a task needs more judgment than that, the agent's own instructions tell it to stop and say so rather than improvise at a model tier too cheap for the job. |
| `coder` | mid (e.g. sonnet) | Writing real implementation + tests against documented architecture rules — needs enough judgment to apply a pattern correctly, not enough novelty to need the top tier. |
| `researcher` | mid (e.g. sonnet) | Synthesizing an external answer to a pointed question — needs judgment about source quality, not architectural judgment about the project itself. |
| `reviewer` | mid (e.g. sonnet) | Checking a diff against an explicit checklist — bounded judgment, not open-ended design. |
| `architect` | highest (e.g. opus) | The one role that can introduce a new structural decision the whole project has to live with, and the one place `permission-mode: plan` matters — mistakes here are the least reversible and cost the most to unwind later. |

## Tiering applies to the review step too

`/implement`'s orchestration mode (see
`../decisions/0004-plan-tasks-implement-rebalance.md`) auto-reviews a
finished task with `reviewer` only when `coder` (mid tier) did the
work — not when `quickfix` (cheapest tier) did. Spending a mid-tier
review pass on a task scoped, by construction, to a single file with no
new business rule doesn't buy back its own cost; the same reasoning
that keeps `quickfix` at the cheapest tier keeps it out of the
automatic review loop too. `reviewer`'s two other scopes — the
whole-feature pass (`/review`) and the on-demand sweep against an
already-`implemented` spec (`/reconcile`, ADR 0012) — stay at the same
mid tier: both are still bounded-checklist judgment, not open-ended
design.

## How to reconsider this per project

- If a project's `coder` tasks are unusually novel/ambiguous (not just
  "apply the documented pattern"), consider moving it up a tier.
- If `architect` almost never actually proposes an ADR in your
  project's real usage, it's still worth keeping at the top tier — the
  cost of getting a rare structural call wrong outweighs the token
  savings of downgrading a role that runs infrequently.
- Re-evaluate this table whenever the available model lineup changes
  meaningfully — the point is the *reasoning* (match tier to
  reversibility + judgment required), not these exact model names.
