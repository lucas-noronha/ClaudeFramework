---
name: skill-authoring
description: Decides whether a new piece of project knowledge belongs in a Skill, a slash command, or an agent's own body — and applies the standard Skill frontmatter/structure when it is a Skill. Use whenever you're about to add reusable project-specific knowledge to this framework.
---

Full rationale for the split this skill enforces →
framework ADR 0001.

## The one test that decides Skill vs. something else

**Does this apply at any pipeline stage, regardless of sequence?**

- **Yes** → it's a Skill. Text-similarity triggering is fine here,
  because there's no wrong stage to get routed to — the rule is either
  relevant to the current change or it isn't.
- **No, it only matters at one specific stage** → it belongs in the
  body of that stage's slash command or subagent, not in its own
  Skill. A pipeline's sequence shouldn't depend on probabilistic
  description matching.

If you're unsure, ask: "would this rule make sense to check during
`/spec`, `/plan`, `/implement`, AND `/review` alike?" If the honest
answer is "only during implementation," it's implementation-agent
guidance, not a Skill.

## Structure, once it is a Skill

```markdown
---
name: kebab-case-name
description: One sentence — what it checks/ensures, and when to use it (be specific enough that an agent can self-trigger on the right task, not so broad it fires on everything).
applies_to: [coder, reviewer]
---

Full reference: `path/to/the/longer/architecture/doc.md` (if one
exists — don't duplicate it here, point to it).

<the actual checklist/rule, as a checklist where possible>
```

Rules:
- One skill = one checkable concern. If you're listing two unrelated
  rule sets under one name, split the file.
- **Tag `applies_to` with the exact agent names from
  `.claude/agents/*.md`** (e.g. `coder`, `reviewer`, `architect`) that
  should actively check for this skill — as an inline list on one
  line, e.g. `applies_to: [coder, reviewer]`. This is how a project
  signals a new skill to the agents that need it: tag it here, once,
  at the source — never edit an agent's own file to "register" a
  skill. `.claude/hooks/skill_index.py` rebuilds
  `.claude/skills/README.md` from these tags automatically whenever a
  `SKILL.md` changes, and every pipeline agent is expected to check
  that index for its own name before starting a task. Omit the field
  entirely for a skill that isn't tied to one specific pipeline role
  (e.g. this skill itself — relevant to whoever maintains `.claude/`,
  not to one agent in the pipeline). A typo in an agent name silently
  drops the skill from that agent's view, so copy names exactly.
- Prefer a checklist (`- [ ]` items) over prose — it's what `coder` and
  `reviewer` actually scan against.
- If the skill encodes a non-negotiable invariant (something that must
  never be false, not just "usually true"), say so explicitly and
  state what happens if an item can't be confirmed (usually: the task
  isn't done).
- Document deliberate exceptions inline, with the specific reason and
  a link to the ADR that justifies it, e.g.: "table X has no isolation
  policy because it records cross-tenant platform activity, not tenant
  business data — see ADR 000N." An undocumented exception invites a
  future agent (or you) to "fix" it incorrectly.
