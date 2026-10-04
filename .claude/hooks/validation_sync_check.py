"""LEGACY SHIM, unwired from every settings template (framework ADR 0023 item 6,
framework spec 0005 FR-03/NFR-05). The canonical/stakeholder split is
retired; this file stays only so a settings file that still wires it never
hits a missing-script error, and so a project that still has split keys
and no setup language keeps its old behaviour. In every other case it is
a silent no-op. It never deletes any `.validation-*.md` file.

Original purpose: PostToolUse (Edit/Write): decide, at zero token cost, whether a spec's
stakeholder-language validation summary needs re-syncing — and only then
hand the sync to the session (framework ADR 0020, framework spec 0003 FR-03; framework spec 0001
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
    framework_config,
    framework_home,
    has_actual_split,
    hook_should_run,
    load_project_config,
    normalize,
    read_hook_input,
    resolve_docs_root,
    read_project_config,
)

SYNC_STATUSES = {"approved", "implemented"}
HASHED_SECTIONS = (
    "Business context",
    "Functional requirements",
    "Non-functional requirements",
    "Explicitly out of scope",
)


def setup_has_language() -> bool:
    """True when the setup itself names a language (framework.json, or
    the setup's own project-config.json): the split is retired there."""
    if str(framework_config().get("language") or "").strip():
        return True
    own = read_project_config(framework_home())
    return bool(str(own.get("language") or "").strip())


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
    # Registration gate (framework ADR 0017): a no-op for an unregistered repo under
    # a user-level install; always open in modes A/B.
    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    if not hook_should_run(project):
        return

    data = read_hook_input()
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return

    if setup_has_language():
        return  # the setup has a language: the split is retired

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
    if not has_actual_split(config) or not code:
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

    instruction = (
        f"Validation summary sync needed: {normalize(abspath)} is approved and its requirements changed "
        f"since the {stakeholder} companion was last synced. Rewrite {normalize(companion)} in plain "
        f"{stakeholder} for a non-technical reader, from the canonical spec's "
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
