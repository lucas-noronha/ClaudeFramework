"""PostToolUse (Edit/Write): decide, at zero token cost, whether a spec's
stakeholder-language validation summary needs re-syncing — and only then
hand the sync to the session (ADR 0020, spec 0003 FR-03; spec 0001
D10/D11).

Before this hook, an `agent` hook started a Sonnet agent on every edit to
an approved spec, even in a project with no language split, and only
then decided to stop. Its `if: Edit(docs/product/specs/*)` filter also
never matched the absolute paths modes B/C write (D10), and its prompt
looked for a `<subtree>/docs` folder that doesn't exist (D11).

This hook makes the whole decision deterministically, from resolved
paths:

1. The edited file is a canonical spec in this project's own
   `product/specs/` (never a `.validation-*` companion, never the index).
2. The project has a language split (`canonical_lang` !=
   `stakeholder_lang` in its config); no config at all means no split
   is known, so nothing happens.
3. The spec is `approved` or `implemented`.
4. The spec's requirement sections (business context, functional,
   non-functional, out of scope) hash differently from the
   `source_hash` the companion recorded at its last sync. Appending
   Reconciliation lines or checking off tasks doesn't change the hash,
   so it never triggers a sync.

Only when all four hold does it emit `additionalContext` asking the
session to rewrite the companion, with absolute paths and the new hash
to record. A hook can't start an agent on condition, so "the agent"
here is the session itself, which may delegate. Fails open on anything
unexpected.
"""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import (  # noqa: E402
    hook_should_run,
    load_project_config,
    normalize,
    read_hook_input,
    resolve_docs_root,
    resolve_shared_docs_root,
)

SYNC_STATUSES = {"approved", "implemented"}
HASHED_SECTIONS = (
    "Business context",
    "Functional requirements",
    "Non-functional requirements",
    "Explicitly out of scope",
)


def frontmatter_field(content: str, key: str):
    fm = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not fm:
        return None
    match = re.search(rf"^{re.escape(key)}:\s*(.+)$", fm.group(1), re.MULTILINE)
    return match.group(1).strip() if match else None


def requirements_hash(content: str) -> str:
    parts = []
    for title in HASHED_SECTIONS:
        match = re.search(rf"^##\s*{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", content, re.MULTILINE | re.DOTALL)
        body = match.group(1) if match else ""
        parts.append(title + "\n" + " ".join(body.split()))
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def main() -> None:
    # Registration gate (ADR 0017): a no-op for an unregistered repo under
    # a user-level install; always open in modes A/B.
    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    if not hook_should_run(project):
        return

    data = read_hook_input()
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return

    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    specs_dir = os.path.join(resolve_docs_root(project), "product", "specs")
    base = os.path.basename(abspath)
    if normalize(os.path.dirname(abspath)) != normalize(specs_dir):
        return
    if not base.endswith(".md") or base == "README.md" or ".validation-" in base:
        return

    config = load_project_config(project)
    canonical = str(config.get("canonical_lang") or "").strip()
    stakeholder = str(config.get("stakeholder_lang") or "").strip()
    code = str(config.get("stakeholder_lang_code") or "").strip()
    if not canonical or not stakeholder or not code or canonical.lower() == stakeholder.lower():
        return

    try:
        with open(abspath, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return
    if frontmatter_field(content, "status") not in SYNC_STATUSES:
        return

    companion = abspath[: -len(".md")] + f".validation-{code}.md"
    new_hash = requirements_hash(content)
    try:
        with open(companion, encoding="utf-8") as f:
            if frontmatter_field(f.read(), "source_hash") == new_hash:
                return  # requirements unchanged since the last sync
    except OSError:
        pass  # no companion yet — it needs creating

    shared = resolve_shared_docs_root(project)
    template = normalize(os.path.join(shared, "product", "validation-summary-template.md")) if shared else "the validation-summary template"
    instruction = (
        f"Validation summary sync needed: {normalize(abspath)} is approved and its requirements changed "
        f"since the {stakeholder} companion was last synced. Rewrite {normalize(companion)} in plain "
        f"{stakeholder} for a non-technical reader, following {template}, from the canonical spec's "
        f"CURRENT business context, functional and non-functional requirements and out-of-scope list "
        f"(canonical language: {canonical}). Reference the canonical file by name. Preserve any existing "
        f"validation checkbox states; add the template's default questions only when creating the file. "
        f"Record `source_hash: {new_hash}` in the companion's frontmatter so this check stays quiet "
        f"until the requirements change again."
    )
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": instruction},
        "systemMessage": f"{base}: stakeholder validation summary is out of date — sync requested.",
    }))


if __name__ == "__main__":
    main()
