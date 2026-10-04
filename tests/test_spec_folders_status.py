"""Framework spec 0006 task 2: the status flip and the index across spec
layouts (ADR 0024 sections 2 and 3). Real hook invocations in temp dirs.
"""
import json
import os
import unittest

from helpers import HOOKS, TempCase

SPEC = """---
doc_type: spec
id: {id}
status: {status}
area: {area}
{extra}---

# {title}

## Functional requirements

- FR-01: something.
"""

TASKS_TAIL = """
## Tasks

- [x] 1. **One** — first. — Depends on: none
  - plain note under the task
  - another plain note
- [{box}] 2. **Two** — second. — Depends on: 1
"""


class TestSpecFoldersStatus(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "proj")
        os.makedirs(os.path.join(self.repo, ".claude"))
        self.git(self.repo, "init", "-q")
        self.specs = os.path.join(self.repo, "docs", "product", "specs")

    def spec_text(self, id="0001", status="approved", area="core", title="Folder spec", extra="", tail=""):
        return SPEC.format(id=id, status=status, area=area, title=title, extra=extra) + tail

    def put_bytes(self, path, text, crlf=False):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = text.replace("\n", "\r\n") if crlf else text
        with open(path, "wb") as f:
            f.write(data.encode("utf-8"))

    def get_bytes(self, path):
        with open(path, "rb") as f:
            return f.read()

    def edit(self, name, path):
        return self.hook(HOOKS, name, {"tool_name": "Edit", "tool_input": {"file_path": path}}, self.repo)

    def index(self):
        path = os.path.join(self.specs, "README.md")
        return self.read(path) if os.path.isfile(path) else None

    def events(self):
        log = os.path.join(self.repo, ".claude", "pipeline-metrics.jsonl")
        if not os.path.isfile(log):
            return []
        with open(log, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    # S03 — FR-10, AC-05
    def test_s03_last_box_in_tasks_md_flips_only_status_line_crlf_preserved(self):
        folder = os.path.join(self.specs, "0001-folder")
        spec_md = os.path.join(folder, "spec.md")
        tasks_md = os.path.join(folder, "tasks.md")
        original = self.spec_text()
        self.put_bytes(spec_md, original, crlf=True)
        self.put_bytes(tasks_md, TASKS_TAIL.format(box=" "), crlf=True)

        self.edit("spec_status_sync.py", tasks_md)
        self.assertEqual(self.get_bytes(spec_md), original.replace("\n", "\r\n").encode())  # one box open

        self.put_bytes(tasks_md, TASKS_TAIL.format(box="x"), crlf=True)
        tasks_before = self.get_bytes(tasks_md)
        self.edit("spec_status_sync.py", tasks_md)

        expected = original.replace("status: approved", "status: implemented").replace("\n", "\r\n").encode()
        self.assertEqual(self.get_bytes(spec_md), expected)
        self.assertEqual(self.get_bytes(tasks_md), tasks_before)
        self.assertEqual([e["event"] for e in self.events()].count("spec_implemented"), 1)
        self.assertIn("implemented", self.index())

    # S04 — FR-15, AC-08, AC-17
    def test_s04_lite_and_legacy_single_files_flip_as_before(self):
        body = TASKS_TAIL.format(box="x")
        legacy = os.path.join(self.specs, "0002-legacy.md")
        lite = os.path.join(self.specs, "0003-quick-fix", "spec.md")
        draft = os.path.join(self.specs, "0004-draft.md")
        self.put_bytes(legacy, self.spec_text(id="0002", tail=body))
        self.put_bytes(lite, self.spec_text(id="0003", extra="lite: true\n", tail=body))
        self.put_bytes(draft, self.spec_text(id="0004", status="draft", tail=body))

        for path in (legacy, lite, draft):
            self.edit("spec_status_sync.py", path)

        self.assertIn(b"status: implemented", self.get_bytes(legacy))
        self.assertIn(b"status: implemented", self.get_bytes(lite))
        self.assertEqual(self.get_bytes(draft), self.spec_text(id="0004", status="draft", tail=body).encode())
        self.assertEqual(self.get_bytes(legacy),
                         self.spec_text(id="0002", tail=body).replace("approved", "implemented").encode())

    # S05 — FR-07, AC-03
    def test_s05_indented_plain_sub_bullets_never_count_as_boxes(self):
        legacy = os.path.join(self.specs, "0005-subs.md")
        tail = (
            "\n## Tasks\n\n- [x] 1. **One** — done.\n"
            "  - [link-like note] not a box\n  - plain note\n    - deeper plain note\n"
        )
        self.put_bytes(legacy, self.spec_text(id="0005", tail=tail))
        result = self.edit("spec_status_sync.py", legacy)
        self.assertIn("all 1 tasks", result.stdout)
        self.assertIn(b"status: implemented", self.get_bytes(legacy))

        # Only sub-bullets and no box: nothing to flip.
        bare = os.path.join(self.specs, "0006-bare.md")
        self.put_bytes(bare, self.spec_text(id="0006", tail="\n## Tasks\n\n  - plain note\n"))
        self.edit("spec_status_sync.py", bare)
        self.assertIn(b"status: approved", self.get_bytes(bare))

    # S07 — FR-12, AC-07
    def test_s07_index_one_row_per_spec_across_layouts_and_silent_on_due_flip(self):
        self.put_bytes(os.path.join(self.specs, "0001-folder", "spec.md"),
                       self.spec_text(id="0001", title="Folder spec title"), crlf=True)
        self.put_bytes(os.path.join(self.specs, "0001-folder", "tasks.md"), TASKS_TAIL.format(box=" "))
        self.put_bytes(os.path.join(self.specs, "0002-quick-lite", "spec.md"),
                       self.spec_text(id="0002", title="Lite spec title", extra="lite: true\n"))
        self.put_bytes(os.path.join(self.specs, "0003-legacy.md"), self.spec_text(id="0003", title="Legacy title"))
        self.put_bytes(os.path.join(self.specs, "0004-nospec", "plan.md"), "# just a plan\n")

        self.edit("spec_index.py", os.path.join(self.specs, "0001-folder", "tasks.md"))
        index = self.index()
        rows = [line for line in index.splitlines() if line.startswith("| 000")]
        self.assertEqual(len(rows), 4)
        self.assertIn("[Folder spec title](0001-folder/spec.md)", index)
        self.assertIn("[Lite spec title](0002-quick-lite/spec.md)", index)
        self.assertIn("[Legacy title](0003-legacy.md)", index)
        self.assertIn("unknown", [r for r in rows if r.startswith("| 0004")][0])

        # A due flip: the index hook writes nothing; the flip rebuilds.
        os.remove(os.path.join(self.specs, "README.md"))
        self.put_bytes(os.path.join(self.specs, "0001-folder", "tasks.md"), TASKS_TAIL.format(box="x"))
        result = self.edit("spec_index.py", os.path.join(self.specs, "0001-folder", "tasks.md"))
        self.assertEqual(result.stdout.strip(), "")
        self.assertIsNone(self.index())

        self.edit("spec_status_sync.py", os.path.join(self.specs, "0001-folder", "tasks.md"))
        self.assertRegex(self.index(), r"\| 0001 \| \[Folder spec title\]\(0001-folder/spec.md\) \| core \| implemented \|")


if __name__ == "__main__":
    unittest.main()
