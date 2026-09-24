---
doc_type: template
scope: stakeholder-validation-summary
status: active
last_updated: {{DATE}}
context_budget: ~150 tokens
language_note: >
  This file is the only spec artifact the non-technical stakeholder
  needs to read. /spec generates it alongside the canonical
  {{CANONICAL_LANG}} file, purely for the validation checkpoint — it
  isn't reloaded repeatedly by agents, so writing it in
  {{STAKEHOLDER_LANG}} costs little and is paid once per spec. Delete
  this whole template (and the corresponding /spec step) if your
  project has no canonical/stakeholder language split.
---

# Validation summary — {feature name}

> Full technical reference: `NNNN-short-name.md` ({{CANONICAL_LANG}},
> no need to read it).

## What this feature does

<!-- 2-3 sentences, plain business language, no technical terms. -->

## What the system will allow (in practice)

- ...
- ...

## What's left out, for now

- ...

## Question for you to validate

- [ ] Does this correctly reflect how the process actually works
      today?
- [ ] Is there a real-world case this is missing?
- [ ] Should any of this be left out of scope for now?

---
Once validated, let us know so we can update the technical spec's
status.

---

Translate every heading and line above into `{{STAKEHOLDER_LANG}}`
before using this template for real — this file's own prose stays in
{{CANONICAL_LANG}} (it's instructions for whoever fills it in), but
the actual generated `.validation-*.md` companion should read
naturally to the stakeholder, not be a literal copy of this scaffold.
