"""L22 (framework spec 0005, FR-08, AC-07): on a Portuguese project the
real hooks behave exactly as on an English one. Free text is Portuguese;
frontmatter keys, enumerated values, `## Tasks`/`## Reconciliation`, the
reconciliation phrases and the reviewer verdict stay English.
"""
import json
import os
import unittest

from helpers import HOOKS, TempCase

SPEC = """---
doc_type: spec
id: 0001
status: approved
area: vendas
summary: Como o cliente repõe o estoque de um pedido recorrente.
notFor: Detalhes de cobrança, que ficam em outra especificação.
context_budget: ~500 tokens
---

# Reposição de pedido recorrente

## Requisitos funcionais

- FR-01: O cliente repete um pedido anterior com um clique.

## Reconciliation

- [task 1] FR-01: matches spec
- [task 2] FR-01: matches spec (ajuste de texto)
- [task 3] FR-01: diverged (o botão fica na tela de resumo)
- [task 4] out of scope (cobrança)

## Tasks

- [x] 1. **Tela** — camada de interface. — Depende de: nenhuma
- [x] 2. **Serviço** — regra de reposição. — Depende de: 1
- [ ] 3. **Testes** — cobertura. — Depende de: 2
"""

ADR = """---
doc_type: adr
id: 0001
status: accepted
supersedes: null
superseded_by: null
---

# ADR 0001 — Usar fila para reposições

## Contexto

Reposições chegam em rajadas.
"""


class TestPortugueseProject(TempCase):
    def setUp(self):
        super().setUp()
        self.repo = os.path.join(self.tmp, "loja")
        os.makedirs(self.repo)
        self.git(self.repo, "init", "-q")
        os.makedirs(os.path.join(self.repo, ".claude"))  # the metrics log never creates its folder
        self.spec = os.path.join(self.repo, "docs", "product", "specs", "0001-reposicao.md")
        self.write(self.spec, SPEC)

    def edit(self, name, path):
        return self.hook(HOOKS, name, {"tool_name": "Edit", "tool_input": {"file_path": path}}, self.repo)

    def events(self):
        log = os.path.join(self.repo, ".claude", "pipeline-metrics.jsonl")
        with open(log, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_l22_spec_status_sync_flips_when_all_boxes_checked(self):
        self.edit("spec_status_sync.py", self.spec)
        self.assertIn("status: approved", self.read(self.spec))  # one box still open
        self.write(self.spec, SPEC.replace("- [ ] 3.", "- [x] 3."))
        self.edit("spec_status_sync.py", self.spec)
        text = self.read(self.spec)
        self.assertIn("status: implemented", text)
        self.assertIn("summary: Como o cliente repõe o estoque", text)

    def test_l22_spec_index_lists_portuguese_title(self):
        self.edit("spec_index.py", self.spec)
        index = self.read(os.path.join(self.repo, "docs", "product", "specs", "README.md"))
        self.assertIn("Reposição de pedido recorrente", index)
        self.assertIn("vendas", index)
        self.assertIn("approved", index)

    def test_l22_decision_index_lists_portuguese_title(self):
        adr = os.path.join(self.repo, "docs", "decisions", "0001-fila.md")
        self.write(adr, ADR)
        self.edit("decision_index.py", adr)
        index = self.read(os.path.join(self.repo, "docs", "decisions", "README.md"))
        self.assertIn("Usar fila para reposições", index)
        self.assertIn("accepted", index)

    def test_l22_reconciliation_phrases_parse_as_in_english(self):
        self.hook(HOOKS, "pipeline_metrics.py", {"tool_name": "Edit", "tool_input": {"file_path": self.spec}}, self.repo)
        snap = [e for e in self.events() if e["event"] == "reconciliation_snapshot"][-1]
        self.assertEqual((snap["spec_id"], snap["matches"], snap["diverged"], snap["out_of_scope"]), ("0001", 2, 1, 1))

    def test_l22_reviewer_verdict_parses_with_portuguese_body(self):
        for reply, verdict in (("Approved\n\nTudo conforme a especificação.", "Approved"),
                               ("**Returned**\n\nFalta o teste da tarefa 3.", "Returned")):
            payload = {"tool_name": "Agent",
                       "tool_input": {"subagent_type": "reviewer", "prompt": "Revise docs/product/specs/0001-reposicao.md"},
                       "tool_response": {"content": reply}}
            self.hook(HOOKS, "pipeline_metrics.py", payload, self.repo)
            last = [e for e in self.events() if e["event"] == "reviewer_verdict"][-1]
            self.assertEqual((last["verdict"], last["spec_id"]), (verdict, "0001"))

    def test_l22_frontmatter_check_accepts_portuguese_routing_values(self):
        result = self.edit("frontmatter_check.py", self.spec)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((result.stdout + result.stderr).strip(), "")


if __name__ == "__main__":
    unittest.main()
