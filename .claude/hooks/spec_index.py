"""PostToolUse: rebuild docs/product/specs/README.md — a one-line-per-spec
index (id, title, area, status, related specs) — whenever a spec is
written or edited. Lets an agent see what specs exist, their status,
and their lineage (see framework ADR 0008)
without opening or globbing every file. Writes the filesystem directly
(not through the Write/Edit tool), so it never re-triggers itself.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _project_paths import hook_should_run, normalize, read_hook_input, resolve_docs_root, resolve_shared_docs_root  # noqa: E402


def title_from_filename(basename: str) -> str:
    stem = re.sub(r"^\d{4}-", "", basename)
    stem = re.sub(r"\.md$", "", stem)
    words = stem.replace("-", " ").replace("_", " ")
    return words[:1].upper() + words[1:] if words else "(untitled)"


def parse_spec(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return None

    # Only look inside the YAML frontmatter block — a spec's body can
    # otherwise contain lines that look like frontmatter fields and get
    # matched by mistake.
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    frontmatter = fm_match.group(1) if fm_match else ""

    id_match = re.search(r"^id:\s*(\d{4})", frontmatter, re.MULTILINE)
    status_match = re.search(r"^status:\s*(.+)$", frontmatter, re.MULTILINE)
    area_match = re.search(r"^area:\s*(.+)$", frontmatter, re.MULTILINE)
    relates_match = re.search(r"^relates_to:\s*(.+)$", frontmatter, re.MULTILINE)
    heading_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)

    basename = os.path.basename(path)
    spec_id = id_match.group(1) if id_match else basename[:4]

    heading = heading_match.group(1).strip() if heading_match else ""
    title = heading if heading and heading.lower() != "feature name" else title_from_filename(basename)

    area = area_match.group(1).strip() if area_match else ""
    related_ids = re.findall(r"\d{4}", relates_match.group(1)) if relates_match else []

    return {
        "id": spec_id,
        "status": status_match.group(1).strip() if status_match else "unknown",
        "area": area if area else "(unassigned)",
        "related": related_ids,
        "title": title,
        "file": basename,
    }


def shared_doc_ref(project: str, from_dir: str, shared_relpath: str, label: str) -> str:
    """A reference to shared framework material, relative to where the
    index actually sits (framework spec 0001 D4). The index lives in a project
    subtree in modes B/C, and the shared root sits elsewhere, so a fixed
    `../../decisions/...` only resolves in mode A. Falls back to a plain
    label when the target isn't on disk, never a dead path.
    """
    shared = resolve_shared_docs_root(project)
    if shared:
        target = os.path.join(shared, *shared_relpath.split("/"))
        if os.path.isfile(target):
            try:
                rel = normalize(os.path.relpath(target, from_dir))
            except ValueError:  # different drive on Windows
                rel = normalize(target)
            return f"`{rel}`"
    return label


def main() -> None:
    # Registration gate (framework ADR 0017): a no-op for an unregistered repo under
    # a user-level install; always open in modes A/B.
    if not hook_should_run(os.environ.get("CLAUDE_PROJECT_DIR", ".")):
        return

    data = read_hook_input()
    path = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    if not path:
        return

    project = os.environ.get("CLAUDE_PROJECT_DIR", ".")
    abspath = path if os.path.isabs(path) else os.path.join(project, path)
    specs_dir = os.path.join(resolve_docs_root(project), "product", "specs")

    # Self-gating: this hook fires on every Write/Edit in the multi-project
    # settings variant, so it decides relevance itself rather than trusting
    # a literal-prefix `if` condition — it compares the tool-reported
    # path's own directory against the resolved specs_dir directly instead,
    # which works regardless of which of the two path shapes a tool call
    # reports (see resolve_docs_root in _project_paths.py).
    if normalize(os.path.dirname(abspath)) != normalize(specs_dir):
        return
    if os.path.basename(abspath) == "README.md":
        return

    entries = []
    for candidate in sorted(glob.glob(os.path.join(specs_dir, "[0-9][0-9][0-9][0-9]-*.md"))):
        if ".validation-" in os.path.basename(candidate):
            continue
        entry = parse_spec(candidate)
        if entry:
            entries.append(entry)
    entries.sort(key=lambda e: (e["area"], e["id"]))

    # Framework ADRs live in the framework repository (evolution/), never in
    # a project: name it, don't link it — a project's own decisions/0008-*
    # is an unrelated document with a colliding number.
    lineage_adr = "framework ADR 0008"
    template = shared_doc_ref(project, specs_dir, "product/requirements-template.md", "the requirements template")
    lines = [
        "<!-- Auto-generated by spec_index.py — do not edit by hand. -->",
        "",
        "# Product specs — index",
        "",
        f"One line per spec, grouped by area (see {lineage_adr}). Open the",
        "file only if the summary here doesn't already answer your question —",
        f"see {template} for the format. `/spec` reads this table to infer a",
        "new spec's own `area`/`relates_to` automatically.",
        "",
        "| ID | Title | Area | Status | Related to |",
        "|---|---|---|---|---|",
    ]
    for e in entries:
        related = ", ".join(e["related"]) if e["related"] else "—"
        lines.append(f"| {e['id']} | [{e['title']}]({e['file']}) | {e['area']} | {e['status']} | {related} |")

    with open(os.path.join(specs_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    areas = len({e["area"] for e in entries})
    print(json.dumps({"systemMessage": f"docs/product/specs/README.md index refreshed ({len(entries)} specs, {areas} area(s))."}))


if __name__ == "__main__":
    main()
