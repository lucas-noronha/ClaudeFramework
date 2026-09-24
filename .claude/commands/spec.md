---
description: Creates a feature spec from the requirements template, producing a canonical file plus a stakeholder-language validation summary (if that split applies to this project).
argument-hint: short description of the feature
---

Use `docs/product/requirements-template.md` as the fixed structure.
From the description in $ARGUMENTS:

1. If `superpowers` is enabled this session, invoke its `brainstorming`
   skill first to explore intent, requirements, and design questions
   from the description — its output feeds the steps below, it doesn't
   replace them. If `superpowers` isn't enabled, apply the same
   discipline directly (absorbed fallback, see `plugin-awareness`):
   don't jump straight to filling the template without first surfacing
   what's actually unclear. Never mention the plugin to the user either
   way — just produce the spec.
2. **Problem vs. solution check, as part of that same step**: state in
   one sentence what business problem this actually solves, separate
   from the solution described in $ARGUMENTS. If the described solution
   doesn't obviously follow from that problem — it looks like it solves
   a symptom, a narrower or broader case exists, or a simpler fix would
   address the same problem — say so explicitly as one of the "unclear,
   ask" items below, don't silently formalize the requested solution
   as-is. This isn't second-guessing the user for its own sake: it's the
   cheapest point in the whole pipeline to catch "wrong feature,
   confidently described" before it becomes a validated spec everything
   downstream trusts.
3. Fill in the business context and functional/non-functional
   requirements that are already clear from the description, **in
   {{CANONICAL_LANG}}** — this is the canonical file agents will
   reload repeatedly. Also check `docs/constitution.md`, if present —
   if the requirement as described would need to violate a principle
   there, flag that explicitly as one of the "unclear, ask" items
   below rather than formalizing it silently.
4. **Area and lineage, automatically — never ask the human to tag
   this** (see `docs/decisions/0008-spec-area-lineage.md`): read
   `docs/product/specs/README.md`, already grouped by area. If this
   spec clearly extends the same functional domain/capability as
   specs already tagged with one, reuse that exact `area` value;
   otherwise propose a new short kebab-case tag. For every existing
   spec sharing that area, decide the relationship to this new one
   (e.g. "extends", "modifies FR-03", "no direct overlap, same area
   only") and list it under `relates_to` (ids, in the frontmatter) and
   "## Related specs" (body, one line each). Nothing sharing the area
   yet means both stay empty — this is that area's first spec. Never
   invent an overlap that isn't really there just to populate the
   field.
5. For anything unclear (including a problem/solution mismatch flagged
   in step 2, or a constitution conflict flagged in step 3), list it as
   explicit questions at the end of your reply — don't invent a
   requirement.
6. Save the canonical file at `docs/product/specs/NNNN-short-name.md`
   (next available sequential number), starting with its own
   frontmatter (`doc_type: spec`, `id: NNNN`, `status: draft`, the
   `area`/`relates_to` from step 4, a `context_budget` estimate) — see
   the fenced example in `requirements-template.md`, right after its
   own divider, for the exact shape. Include an empty "## Reconciliation"
   section per the template; `reviewer` populates it during
   `/implement` — never fill it in here.
7. If the project has a `{{STAKEHOLDER_LANG}}` split configured (see
   `CLAUDE.md`'s language convention), generate a second, short file at
   `docs/product/specs/NNNN-short-name.validation-{{STAKEHOLDER_LANG_CODE}}.md`
   — a plain restatement of the functional/non-functional requirements
   in `{{STAKEHOLDER_LANG}}`, written for a non-technical reader. This
   is the only artifact the stakeholder needs to read; it references
   the canonical file, it doesn't duplicate its full structure. Skip
   this step entirely if canonical and stakeholder language are the
   same.
8. Do not implement anything at this stage. Do not invoke `coder`.

End by reminding the user that the next step is validating the
`.validation-{{STAKEHOLDER_LANG_CODE}}.md` file (or the canonical file
directly, if no split applies) with the stakeholder outside the chat,
updating `status` to `approved` in the **canonical** file once
approved, and only then running `/plan`. If the feature gets dropped
instead — before or during implementation — `status` becomes
`abandoned` (set by hand, at any point); see the frontmatter note in
`docs/product/requirements-template.md` for the full status set.
