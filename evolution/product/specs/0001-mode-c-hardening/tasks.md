---
doc_type: spec-tasks
spec: 0001
summary: The ordered task list, one checkbox per task.
context_budget: ~300 tokens
---

## Tasks

- [x] 1. Registration gate, `framework.json` as the single config source, shared-root resolution, `describe` probe — Tests: FR-03, FR-09, AC-02
- [x] 2. User-level installer: prefix, reference rewriting, runtime tokens, absolute hook paths, generated permission, collision and hand-edit refusal — Tests: FR-01, FR-04, FR-06, FR-07, FR-08, NFR-01, NFR-03, AC-01, AC-04
- [x] 3. Manifest, uninstaller with byte-exact settings restore, retire/restore — Tests: FR-02, AC-03
- [x] 4. Index hooks scoped to the namespace/subtree, links computed from the index location — Tests: FR-05
- [x] 5. Constitution baseline layer and upgrade policies — Tests: FR-10, AC-06
- [x] 6. `register_project.py`, single and bulk — Tests: FR-11
- [x] 7. `migrate_context.py` — Tests: FR-12, AC-07
- [x] 8. Verify-before-reporting rule for security claims in `coder`/`reviewer` — Tests: NFR-02
- [x] 9. Validation-summary pre-check firing in a mode C subtree (shared with framework spec 0003) — Tests: AC-05
