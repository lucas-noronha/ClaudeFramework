"""Translation record, plan and apply (framework spec 0005 FR-05/FR-06/NFR-06,
framework ADR 0023 section 2). Stdlib only; never calls a model — the
`translator` agent does that between `plan` and `apply`.

    python translation.py plan  --source DIR --record FILE --language-code pt-BR [--keep REL ...]
    python translation.py apply --source DIR --record FILE --language-code pt-BR --language Portuguese
                                --path REL --staged FILE [--dest FILE] [--policy replace|keep]
                                [--status translated|english] [--reason TEXT]
                                [--terms FILE.json] [--placeholders FILE.json]
    python translation.py check --source FILE --translated FILE
    python translation.py sync-index --claude-md FILE --root DIR [--summary-key KEY ... | --project DIR]
    python translation.py recover-placeholders --source DIR --resolved DIR --record FILE
    python translation.py upgrade-plan --mode a --source DIR --record FILE [--language-code CODE]
    python translation.py upgrade-plan --mode b --repo DIR --record FILE
    python translation.py take-upstream --repo DIR --path REL [--path REL ...]

The record (JSON) lives where the caller says: modes A/B
`.claude/translation-record.json`, mode C `<namespace>/translations/record.json`.
Nothing here hard-codes a mode: passing `--dest` (modes A/B) also records
`dest` and `output_sha256`; without it (mode C) the translated text goes to
the cache, beside the record, at `<record dir>/<path>`.

    {"language": ..., "language_code": ..., "terms": {...}, "placeholders": {...},
     "files": {REL: {"source_sha256", "status", "policy", ["dest", "output_sha256"]}}}

- Translatable: shipped `.md` and `.md.template`. Never JSON, Python,
  `.example` or generated indexes (`skills/README.md`).
- `source_sha256` is over UTF-8 text with CRLF -> LF and no BOM, so a
  working-tree EOL is never mistaken for a change. An unchanged hash is
  never re-translated.
- `keep` files are translated only when created: `plan` never lists a
  recorded one again, and `apply` leaves an existing destination alone.
- English (`en`, `en-*`): `plan` reports nothing to do, `apply` is a no-op,
  no record is written.

`check` (NFR-04, FR-08, FR-11; ADR 0023 section 5) is deterministic and
prints {"ok", "status", "reasons": [{"rule", "detail"}], "reason"}; exit 1
when it fails. A failing file stays English: the caller records it with
`apply --status english --reason "<the report's reason>"`, no `--staged`.

`sync-index` (FR-11; ADR 0023 section 5) is the cross-file step, a dedicated subcommand run
AFTER `apply` has translated every doc and `CLAUDE.md.template` itself (last): it copies each
indexed doc's translated `summary` (alias `resumo`) into its index row's first cell. The doc
wins, as in `claude_md_index_check.py`; rows whose doc has no summary are left alone. Indexed docs
that do not exist under `--root` are listed in `missing`. Without `--summary-key`, `--project DIR`
reads the routing keys from that project's config (`_project_paths.routing_keys`).

`recover-placeholders` (FR-06; ADR 0023 section 3) rebuilds the resolved-placeholder map of an
AI-repo bootstrapped before the record existed, by matching each pristine source (every
`{{NAME}}` a capture group) against the current resolved file. Disagreements (one NAME,
two values) and non-matches are reported, exit 1; the unambiguous names are stored in the record.

`upgrade-plan` (FR-06, FR-10; ADR 0023 sections 3, 4) only reports, as JSON; the caller's prompt asks
and translates. Mode A (`--source` = the newer framework checkout): `retranslate` (changed source,
output still equal to the recorded `output_sha256`, or no output to protect), `edited` (changed source,
output edited locally: ask), `new`, `keep` (never touched), `deleted_upstream` (reported, never
deleted). Mode B (`--repo` = the adopter's repo inside `git merge --no-commit`): `changed` lists every
recorded path whose source hash at MERGE_HEAD differs from the record, `conflicted` or not; `new` and
`deleted_upstream` likewise. `take-upstream` runs `git checkout MERGE_HEAD -- <path>` for each path
(adopter's repo, during an upgrade only); the caller then translates, checks, applies, and on a failed
translation records `apply --status english` so upstream English stays. Unchanged paths keep the local version.

Prints a JSON report; exit 1 on an error.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter

TRANSLATABLE_SUFFIXES = (".md", ".md.template")
GENERATED = ("skills/README.md",)  # generated indexes are never translated
SKIP_DIRS = {".git", ".translation-staging", "__pycache__", "node_modules"}
CHARS_PER_TOKEN = 4  # documented heuristic: ~4 characters per token, rounded up
POLICIES = ("replace", "keep")


def is_english(language_code) -> bool:
    code = (language_code or "").strip().lower().replace("_", "-")
    return code in ("", "en") or code.startswith("en-")


def is_translatable(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return rel.endswith(TRANSLATABLE_SUFFIXES) and not any(rel == g or rel.endswith("/" + g) for g in GENERATED)


def normalized_text(data: bytes) -> str:
    text = data.decode("utf-8-sig")
    return text.replace("\r\n", "\n")


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha256(path: str) -> str:
    with open(path, "rb") as f:
        return text_sha256(normalized_text(f.read()))


def estimate_tokens(text: str) -> int:
    return -(-len(text) // CHARS_PER_TOKEN)


def list_sources(root: str):
    """Relative posix paths of every translatable file under `root`, sorted."""
    found = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            rel = os.path.relpath(os.path.join(base, name), root).replace("\\", "/")
            if is_translatable(rel):
                found.append(rel)
    return sorted(found)


def load_record(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, ValueError):
        record = {}
    if not isinstance(record.get("files"), dict):
        record["files"] = {}
    return record


def save_record(path: str, record: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(record, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def plan(source: str, record_path: str, language_code: str, keep=()) -> dict:
    """New and changed translatable sources against the record, with a token estimate."""
    if is_english(language_code):
        return {"noop": True, "reason": "english", "new": [], "changed": [], "estimated_tokens": 0}
    record = load_record(record_path)
    files = record["files"]
    language_changed = bool(record.get("language_code")) and record["language_code"] != language_code
    keep = {k.replace("\\", "/") for k in keep}
    new, changed, skipped_keep, total = [], [], [], 0
    for rel in list_sources(source):
        with open(os.path.join(source, rel), "rb") as f:
            text = normalized_text(f.read())
        entry = files.get(rel)
        policy = entry.get("policy", "replace") if entry else ("keep" if rel in keep else "replace")
        item = {"path": rel, "policy": policy, "estimated_tokens": estimate_tokens(text)}
        if entry is None:
            new.append(item)
        elif policy == "keep":
            skipped_keep.append(rel)  # translated only on create
            continue
        elif language_changed or entry.get("source_sha256") != text_sha256(text):
            changed.append(item)
        else:
            continue
        total += item["estimated_tokens"]
    return {"noop": not (new or changed), "new": new, "changed": changed, "skipped_keep": skipped_keep,
            "estimated_tokens": total, "token_heuristic": f"chars/{CHARS_PER_TOKEN}"}


def apply(source: str, record_path: str, language: str, language_code: str, rel: str, staged: str,
          dest=None, policy="replace", status="translated", reason=None, terms=None, placeholders=None) -> dict:
    """Write one staged translation to its destination and update the record."""
    if is_english(language_code):
        return {"noop": True, "reason": "english"}
    rel = rel.replace("\\", "/")
    if not is_translatable(rel):
        return {"error": f"{rel} is not a translatable source"}
    if policy not in POLICIES:
        return {"error": f"policy must be one of {POLICIES}"}
    source_file = os.path.join(source, rel)
    if not os.path.isfile(source_file):
        return {"error": f"source {rel} not found under {source}"}
    out_path = dest or os.path.join(os.path.dirname(os.path.abspath(record_path)), rel)
    record = load_record(record_path)
    entry = {"source_sha256": file_sha256(source_file), "status": status, "policy": policy}
    if reason:
        entry["reason"] = reason
    result = {"path": rel, "status": status, "policy": policy}
    if status == "translated":
        if policy == "keep" and os.path.exists(out_path):
            entry["status"] = result["status"] = "existing"  # keep: never overwrite what is there
        else:
            if not os.path.isfile(staged):
                return {"error": f"staged file {staged} not found"}
            with open(staged, "rb") as f:
                data = f.read()
            os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(data)
            result["written"] = out_path.replace("\\", "/")
            if dest:
                entry["dest"] = dest.replace("\\", "/")
                entry["output_sha256"] = text_sha256(normalized_text(data))
    record["language"], record["language_code"] = language, language_code
    if terms is not None:
        record["terms"] = terms
    if placeholders is not None:
        record["placeholders"] = placeholders  # modes A/B only
    record["files"][rel] = entry
    save_record(record_path, record)
    return result


# ---- fidelity check ---------------------------------------------------------
FREE_TEXT_KEYS = {"description", "argument-hint", "title", "summary", "notFor", "resumo", "naoResponde"}
RECURSIVE_TAGS = {"markdown", "md", "text"}  # prose templates: translated, checked recursively
FRONTMATTER_TAGS = {"yaml"}
LENGTH_RATIO = (0.6, 2.0)  # translated/source length; Portuguese runs ~1.1-1.3x. Skipped under MIN_LENGTH
MIN_LENGTH = 200
# Hard-coded (not imported): the installer is absent from a mode C namespace. A test asserts
# this equals install_user_level.RUNTIME_TOKENS' values plus `<language>`.
RUNTIME_TOKEN_LIST = (
    "<backend dir>", "<build_test_cmd>", "<frontend dir>", "<language>",
    "<main_integration_branch>", "<project name>",
)
# English literals, verbatim and in equal counts. The outcome phrases are the ones
# `pipeline_metrics.py` parses from "## Reconciliation" lines, in their line context.
LITERALS = {
    "## Tasks": re.compile(r"## Tasks"),
    "## Reconciliation": re.compile(r"## Reconciliation"),
    "matches spec": re.compile(r":\s*matches spec"),
    "diverged": re.compile(r":\s*diverged"),
    "out of scope": re.compile(r"\]\s*out of scope"),
    "Reconciliation:": re.compile(r"(?<![#\w])Reconciliation:"),
    "Approved": re.compile(r"\bApproved\b"),
    "Returned": re.compile(r"\bReturned\b"),
    # Spec-folder file names (spec 0006 FR-09): fixed English words, never translated.
    "spec.md": re.compile(r"(?<![\w.])spec\.md(?!\w)"),
    "plan.md": re.compile(r"(?<![\w.])plan\.md(?!\w)"),
    "tasks.md": re.compile(r"(?<![\w.])tasks\.md(?!\w)"),
    "reconciliation.md": re.compile(r"(?<![\w.])reconciliation\.md(?!\w)"),
}
FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*(.*?)\s*$")
KEY = re.compile(r"^([A-Za-z_][\w-]*)\s*:(.*)$")
# A code span may continue over a single line break (Markdown reads it as a
# space) but never over a blank line; a translation rewraps lines freely.
CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)((?:(?!\n[ \t]*\n).)+?)(?<!`)\1(?!`)", re.DOTALL)
SCANS = {
    "placeholders": re.compile(r"\{\{[^{}\n]+\}\}"),
    "/commands": re.compile(r"(?<![\w/.:~<>-])/[a-z][\w-]*"),
    "ids": re.compile(r"\b(?:NFR|FR|AC)-\d+\b|\bT-?\d+\b"),
    "link targets and URLs": re.compile(r"\]\(\s*<?([^)\s>]+)|(https?://[^\s)>\]`]+)"),
    "HTML comments": re.compile(r"<!--.*?-->", re.DOTALL),
    "framework ADR/spec references": re.compile(r"framework\s+(?:ADR|spec)\s+\d+"),
}
# Scans whose hits may be split by a line break in prose: compared with
# whitespace collapsed, so rewrapping is not a change.
SOFT_WRAP_SCANS = {"framework ADR/spec references"}


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _runtime_tokens():
    return list(RUNTIME_TOKEN_LIST)


def _tag(info: str) -> str:
    return info.split()[0].lower() if info else ""


def parse_doc(text: str) -> dict:
    """Split into frontmatter lines (or None), prose lines outside fences and fenced blocks."""
    lines = text.split("\n")
    front = None
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                front, lines = lines[1:i], lines[i + 1:]
                break
    prose, blocks, i = [], [], 0
    while i < len(lines):
        m = FENCE.match(lines[i])
        if not m:
            prose.append(lines[i])
            i += 1
            continue
        mark, info = m.group(1), m.group(2)
        body, i = [], i + 1
        while i < len(lines):
            c = FENCE.match(lines[i])
            if c and c.group(1)[0] == mark[0] and len(c.group(1)) >= len(mark) and not c.group(2):
                break
            body.append(lines[i])
            i += 1
        i += 1
        blocks.append({"info": info, "body": "\n".join(body)})
    return {"front": front, "prose": prose, "blocks": blocks}


def frontmatter_pairs(lines):
    """[(key, value)] in order; continuation lines belong to the preceding key."""
    pairs = []
    for line in lines:
        m = KEY.match(line)
        if m:
            pairs.append([m.group(1), m.group(2).strip()])
        elif pairs:
            pairs[-1][1] += "\n" + line.rstrip()
        else:
            pairs.append([None, line.rstrip()])
    return [(k, v.strip()) for k, v in pairs]


def _compare_frontmatter(src, tr, where, reasons):
    s, t = frontmatter_pairs(src), frontmatter_pairs(tr)
    if [k for k, _ in s] != [k for k, _ in t]:
        reasons.append({"rule": "frontmatter keys", "detail": f"{where}keys or their order changed: "
                        f"{[k for k, _ in s]} -> {[k for k, _ in t]}"})
        return
    for (key, a), (_, b) in zip(s, t):
        if key not in FREE_TEXT_KEYS and a != b:
            reasons.append({"rule": "frontmatter values", "detail": f"{where}value of `{key}` changed "
                            "(only free-text keys may be translated)"})


def _fence_frontmatter(block):
    """Lines of a frontmatter-shaped fenced block, or None."""
    lines = block["body"].split("\n")
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), len(lines))
        return lines[1:end]
    return lines if _tag(block["info"]) in FRONTMATTER_TAGS else None


def _diff(rule, a, b, where, reasons):
    a, b = Counter(a), Counter(b)
    if a != b:
        reasons.append({"rule": rule, "detail": f"{where}{rule} differ: missing {sorted((a - b).elements())}, "
                        f"extra {sorted((b - a).elements())}"})


def _ordinals(prose):
    """Ordinals of the numbered list items, CommonMark-style: a numbered line
    that continues a paragraph (e.g. a wrapped `(framework ADR` + `0025) ...`)
    is an item only when it starts at 1 or is a sibling of an open item."""
    found, open_indents, in_paragraph = [], [], False
    for line in prose:
        if not line.strip():
            in_paragraph = False
            continue
        if re.match(r"^ {0,3}#{1,6}\s", line):
            open_indents, in_paragraph = [], False
            continue
        m = re.match(r"^(\s*)(\d+)[.)]\s", line)
        indent = len(m.group(1)) if m else len(line) - len(line.lstrip())
        if m and (not in_paragraph or int(m.group(2)) == 1 or indent in open_indents):
            found.append(m.group(2))
            open_indents = [i for i in open_indents if i < indent] + [indent]
        elif not in_paragraph and indent == 0:
            open_indents = []  # an unindented paragraph after a blank line ends the list
        in_paragraph = True
    return found


def _shape(doc):
    prose = doc["prose"]
    return {
        "headings": [len(m.group(1)) for m in (re.match(r"^ {0,3}(#{1,6})\s", l) for l in prose) if m],
        "ordinals": _ordinals(prose),
        "checkboxes": sum(1 for l in prose if re.match(r"^\s*[-*]\s+\[[ xX]\]", l)),
        "tables": [len(re.split(r"(?<!\\)\|", l.strip().strip("|"))) for l in prose if l.strip().startswith("|")],
    }


def _hits(rx, text):
    return [next(g for g in m.groups() if g) if any(m.groups()) else m.group(0) for m in rx.finditer(text)]


def _check_text(src: str, tr: str, where: str, reasons: list, top: bool) -> None:
    s, t = parse_doc(src), parse_doc(tr)
    if (s["front"] is None) != (t["front"] is None):
        reasons.append({"rule": "frontmatter keys", "detail": f"{where}frontmatter added or removed"})
    elif s["front"] is not None:
        _compare_frontmatter(s["front"], t["front"], where, reasons)
    ss, ts = _shape(s), _shape(t)
    for name, rule in (("headings", "heading count and levels"), ("ordinals", "numbered-item ordinals"),
                       ("checkboxes", "checkbox count"), ("tables", "table shape")):
        if ss[name] != ts[name]:
            reasons.append({"rule": rule, "detail": f"{where}{rule} changed: {ss[name]} -> {ts[name]}"})
    if top and len(src) >= MIN_LENGTH:
        ratio = len(tr) / len(src)
        if not LENGTH_RATIO[0] <= ratio <= LENGTH_RATIO[1]:
            reasons.append({"rule": "length ratio", "detail": f"{ratio:.2f} outside {LENGTH_RATIO}"})
    a, b = ("\n".join((d["front"] or []) + d["prose"]) for d in (s, t))
    _diff("inline code spans", [_squash(m.group(2)) for m in CODE_SPAN.finditer(a)],
          [_squash(m.group(2)) for m in CODE_SPAN.finditer(b)], where, reasons)
    tokens = _runtime_tokens()
    _diff("runtime tokens", [x for x in tokens for _ in range(a.count(x))],
          [x for x in tokens for _ in range(b.count(x))], where, reasons)
    for rule, rx in SCANS.items():
        norm = _squash if rule in SOFT_WRAP_SCANS else (lambda x: x)
        _diff(rule, [norm(h) for h in _hits(rx, a)], [norm(h) for h in _hits(rx, b)], where, reasons)
    for lit, rx in LITERALS.items():
        na, nb = len(rx.findall(src)), len(rx.findall(tr))
        if na != nb:
            reasons.append({"rule": "English literals", "detail": f"{where}`{lit}` count changed: {na} -> {nb}"})
    if len(s["blocks"]) != len(t["blocks"]):
        reasons.append({"rule": "code blocks",
                        "detail": f"{where}fenced block count {len(s['blocks'])} -> {len(t['blocks'])}"})
        return
    for n, (x, y) in enumerate(zip(s["blocks"], t["blocks"]), 1):
        label = f"{where}block {n} ({x['info'] or 'untagged'}): "
        if x["info"] != y["info"]:
            reasons.append({"rule": "code blocks", "detail": f"{label}tag changed to `{y['info']}`"})
        elif _tag(x["info"]) in RECURSIVE_TAGS:
            _check_text(x["body"], y["body"], label, reasons, False)
        elif _fence_frontmatter(x) is not None:
            _compare_frontmatter(_fence_frontmatter(x), _fence_frontmatter(y) or [], label, reasons)
        elif x["body"] != y["body"]:
            reasons.append({"rule": "code blocks", "detail": f"{label}content is not byte-identical"})


def check(source_text: str, translated_text: str) -> list:
    """Reasons a translation is rejected; an empty list means it passes."""
    reasons = []
    _check_text(source_text.replace("\r\n", "\n"), translated_text.replace("\r\n", "\n"), "", reasons, True)
    return reasons


def check_files(source: str, translated: str) -> dict:
    for path in (source, translated):
        if not os.path.isfile(path):
            return {"error": f"{path} not found"}
    with open(source, "rb") as f, open(translated, "rb") as g:
        reasons = check(normalized_text(f.read()), normalized_text(g.read()))
    return {"ok": not reasons, "status": "translated" if not reasons else "english", "reasons": reasons,
            "reason": "; ".join(f"{r['rule']}: {r['detail']}" for r in reasons)}


# ---- cross-file step and placeholder recovery --------------------------------
NAMED_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
SUMMARY_KEYS = ("summary", "resumo")  # primary first, then the alias
INDEX_ROW = re.compile(r"^(\|\s*)([^|]*?)(\s*\|.*`([^`]+\.md)`.*\|\s*~[^|]+?\s*\|\s*)$")


def doc_summary(text: str, keys=SUMMARY_KEYS):
    """The routing summary from a doc's frontmatter (first key present wins), or None."""
    m = re.match(r"^---\n(.*?)\n---", text.replace("\r\n", "\n"), re.DOTALL)
    if not m:
        return None
    for key in keys:
        found = re.search(rf"^{re.escape(key)}:\s*(.+)$", m.group(1), re.MULTILINE)
        if found:
            return found.group(1).strip().strip("\"'")
    return None


def project_summary_keys(project: str):
    """Summary routing keys (primary first, then aliases) from a project's config, or the defaults."""
    hooks = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "hooks")
    if hooks not in sys.path:
        sys.path.append(hooks)
    try:
        import _project_paths
        role = _project_paths.routing_keys(project)["summary"]
        return tuple([role["key"], *role["aliases"]])
    except Exception:
        return SUMMARY_KEYS


def sync_index(claude_md: str, root: str, keys=SUMMARY_KEYS) -> dict:
    """Copy each indexed doc's summary (found under `root`) into its CLAUDE.md index row's first cell."""
    if not os.path.isfile(claude_md):
        return {"error": f"{claude_md} not found"}
    with open(claude_md, "rb") as f:
        text = f.read().decode("utf-8")
    updated, unchanged, skipped, missing, out = [], [], [], [], []
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        eol = line[len(body):]
        m = INDEX_ROW.match(body)
        doc = os.path.join(root, m.group(4)) if m else None
        if not m:
            out.append(line)
            continue
        if not os.path.isfile(doc):
            missing.append(m.group(4))
            out.append(line)
            continue
        with open(doc, "rb") as f:
            summary = doc_summary(f.read().decode("utf-8-sig"), keys)
        if not summary or "|" in summary:  # none, or it would break the table row
            skipped.append(m.group(4))
        elif summary == m.group(2):
            unchanged.append(m.group(4))
        else:
            updated.append(m.group(4))
            body = m.group(1) + summary + m.group(3)
        out.append(body + eol)
    with open(claude_md, "wb") as f:
        f.write("".join(out).encode("utf-8"))
    return {"updated": updated, "unchanged": unchanged, "skipped": skipped, "missing": missing}


def _source_regex(text: str):
    """(compiled full-match regex, [NAME per capture group]) for a pristine source."""
    names, parts, pos = [], [], 0
    for m in NAMED_PLACEHOLDER.finditer(text):
        parts.append(re.escape(text[pos:m.start()]))
        parts.append("(.+?)")
        names.append(m.group(1))
        pos = m.end()
    parts.append(re.escape(text[pos:]))
    return re.compile("".join(parts)), names


def recover_placeholders(source: str, resolved: str, record_path: str) -> dict:
    """Rebuild the resolved-placeholder map from the current files and store it in the record."""
    values, non_matches = {}, []  # NAME -> {value: [rel, ...]}
    for rel in list_sources(source):
        with open(os.path.join(source, rel), "rb") as f:
            pristine = normalized_text(f.read())
        if not NAMED_PLACEHOLDER.search(pristine):
            continue
        candidates = [rel] + ([rel[:-len(".template")]] if rel.endswith(".template") else [])
        current = next((os.path.join(resolved, c) for c in candidates if os.path.isfile(os.path.join(resolved, c))), None)
        if current is None:
            non_matches.append({"path": rel, "reason": "resolved file not found"})
            continue
        with open(current, "rb") as f:
            text = normalized_text(f.read())
        rx, names = _source_regex(pristine)
        m = rx.fullmatch(text)
        if not m:
            non_matches.append({"path": rel, "reason": "does not match the pristine source"})
            continue
        for name, value in zip(names, m.groups()):
            if value != "{{" + name + "}}":  # still literal: a permanent placeholder, not a resolution
                values.setdefault(name, {}).setdefault(value, []).append(rel)
    disagreements = {n: v for n, v in values.items() if len(v) > 1}
    placeholders = {n: next(iter(v)) for n, v in sorted(values.items()) if n not in disagreements}
    record = load_record(record_path)
    record["placeholders"] = placeholders
    save_record(record_path, record)
    return {"placeholders": placeholders, "disagreements": disagreements, "non_matches": non_matches,
            "ok": not (disagreements or non_matches)}


# ---- upgrade support ---------------------------------------------------------
def _git(repo: str, *args, check=True):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=check)


def upgrade_plan_a(source: str, record_path: str, language_code=None, keep=()) -> dict:
    """Mode A: classify each recorded or new source of a newer checkout. Reports only."""
    if language_code is not None and is_english(language_code):
        return {"noop": True, "reason": "english"}
    files = load_record(record_path)["files"]
    out = {"retranslate": [], "edited": [], "new": [], "keep": [], "unchanged": [], "deleted_upstream": []}
    sources = list_sources(source)
    for rel in sources:
        entry = files.get(rel)
        if entry is None:
            out["new"].append(rel)
        elif entry.get("policy") == "keep":
            out["keep"].append(rel)
        elif entry.get("source_sha256") == file_sha256(os.path.join(source, rel)):
            out["unchanged"].append(rel)
        else:
            dest, recorded = entry.get("dest"), entry.get("output_sha256")
            if not (dest and recorded and os.path.isfile(dest)) or file_sha256(dest) == recorded:
                out["retranslate"].append(rel)
            else:
                out["edited"].append(rel)
    present = set(sources)
    out["deleted_upstream"] = sorted(r for r in files if r not in present)
    return out


def _merge_head(repo: str):
    proc = _git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD", check=False)
    return proc.stdout.decode().strip() if proc.returncode == 0 else None


def _git_names(repo: str, *args):
    return {p for p in _git(repo, *args, "-z").stdout.decode("utf-8").split("\0") if p}


def upgrade_plan_b(repo: str, record_path: str) -> dict:
    """Mode B: inside `git merge --no-commit`, recorded paths whose English changed upstream."""
    if not _merge_head(repo):
        return {"error": "no merge in progress (MERGE_HEAD missing): run `git merge --no-commit` first"}
    files = load_record(record_path)["files"]
    unmerged = _git_names(repo, "diff", "--name-only", "--diff-filter=U")
    tree = _git_names(repo, "ls-tree", "-r", "--name-only", "MERGE_HEAD")
    out = {"changed": [], "unchanged": [], "keep": [], "new": [], "deleted_upstream": []}
    for rel, entry in sorted(files.items()):
        if rel not in tree:
            out["deleted_upstream"].append(rel)
        elif entry.get("policy") == "keep":
            out["keep"].append(rel)
        elif text_sha256(normalized_text(_git(repo, "show", f"MERGE_HEAD:{rel}").stdout)) == entry.get("source_sha256"):
            out["unchanged"].append(rel)
        else:
            out["changed"].append({"path": rel, "conflicted": rel in unmerged})
    out["new"] = sorted(r for r in tree if is_translatable(r) and r not in files)
    return out


def take_upstream(repo: str, paths) -> dict:
    """Replace each path in the adopter's working tree with upstream's English (MERGE_HEAD)."""
    if not _merge_head(repo):
        return {"error": "no merge in progress (MERGE_HEAD missing)"}
    taken = []
    for rel in paths:
        rel = rel.replace("\\", "/")
        proc = _git(repo, "checkout", "MERGE_HEAD", "--", rel, check=False)
        if proc.returncode:
            return {"error": f"cannot take {rel}: {proc.stderr.decode('utf-8', 'replace').strip()}", "taken": taken}
        taken.append(rel)
    return {"taken": taken}


def _json_arg(path):
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Translation record, plan and apply.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "apply"):
        p = sub.add_parser(name)
        p.add_argument("--source", required=True, help="root of the pristine English sources")
        p.add_argument("--record", required=True, help="path of the translation record")
        p.add_argument("--language-code", required=True, help="BCP 47; en / en-* means English")
    sub.choices["plan"].add_argument("--keep", action="append", default=[], help="source path with `keep` policy")
    a = sub.choices["apply"]
    a.add_argument("--language", required=True)
    a.add_argument("--path", required=True, help="source path relative to --source")
    a.add_argument("--staged", help="the translated file")
    a.add_argument("--dest", help="modes A/B: where the file lands; omit in mode C (cache beside the record)")
    a.add_argument("--policy", choices=POLICIES, default="replace")
    a.add_argument("--status", choices=("translated", "english"), default="translated")
    a.add_argument("--reason")
    a.add_argument("--terms", help="JSON file: term map")
    a.add_argument("--placeholders", help="JSON file: resolved-placeholder map (modes A/B)")
    c = sub.add_parser("check")
    c.add_argument("--source", required=True, help="the pristine English file")
    c.add_argument("--translated", required=True, help="the translated file")
    x = sub.add_parser("sync-index")
    x.add_argument("--claude-md", required=True, help="the translated CLAUDE.md (or CLAUDE.md.template)")
    x.add_argument("--root", required=True, help="root the index's doc paths resolve under (translated docs)")
    x.add_argument("--summary-key", action="append", default=[], help="routing key, primary first (default summary, resumo)")
    r = sub.add_parser("recover-placeholders")
    r.add_argument("--source", required=True, help="root of the pristine English sources")
    r.add_argument("--resolved", required=True, help="root of the current, placeholder-resolved files")
    r.add_argument("--record", required=True, help="path of the translation record")
    x.add_argument("--project", help="project dir whose config supplies the routing keys when --summary-key is absent")
    u = sub.add_parser("upgrade-plan")
    u.add_argument("--mode", required=True, choices=("a", "b"))
    u.add_argument("--record", required=True)
    u.add_argument("--source", help="mode A: the newer framework checkout")
    u.add_argument("--repo", help="mode B: the adopter's repo, inside `git merge --no-commit`")
    u.add_argument("--language-code")
    t = sub.add_parser("take-upstream")
    t.add_argument("--repo", required=True)
    t.add_argument("--path", action="append", required=True)
    args = parser.parse_args(argv)

    if args.command == "check":
        report = check_files(args.source, args.translated)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report.get("ok") else 1
    if args.command == "sync-index":
        keys = tuple(args.summary_key) or (project_summary_keys(args.project) if args.project else SUMMARY_KEYS)
        report = sync_index(args.claude_md, args.root, keys)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if report.get("error") else 0
    if args.command == "recover-placeholders":
        report = recover_placeholders(args.source, args.resolved, args.record)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["ok"] else 1
    if args.command == "take-upstream":
        report = take_upstream(args.repo, args.path)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if report.get("error") else 0
    if args.command == "upgrade-plan":
        if args.mode == "a":
            report = upgrade_plan_a(args.source, args.record, args.language_code) if args.source \
                else {"error": "--source is required for mode a"}
        else:
            report = upgrade_plan_b(args.repo, args.record) if args.repo else {"error": "--repo is required for mode b"}
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if report.get("error") else 0
    if args.command == "plan":
        report = plan(args.source, args.record, args.language_code, args.keep)
    else:
        report = apply(args.source, args.record, args.language, args.language_code, args.path, args.staged,
                       args.dest, args.policy, args.status, args.reason, _json_arg(args.terms),
                       _json_arg(args.placeholders))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
