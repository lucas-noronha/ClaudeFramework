"""`translation.py check` (framework spec 0005 task 4, framework ADR 0023
section 5): the deterministic fidelity check. Hand-written Portuguese
fixtures; no model is ever called.
"""
import json
import os
import sys
import unittest

from helpers import SCRIPTS, TempCase

sys.path.insert(0, SCRIPTS)
import translation  # noqa: E402

SCRIPT = os.path.join(SCRIPTS, "translation.py")

EN = """---
name: spec
description: Create a feature spec.
argument-hint: <feature name>
model: sonnet
summary: Spec helper.
notFor: Planning.
---
# Spec

Run `/plan` after FR-01 and AC-02, see [the guide](docs/guide.md) and https://example.com/x.
Use {{PROJECT_NAME}} with <build_test_cmd> (framework ADR 0023). <!-- keep -->

1. First step
2. Second step

- [ ] Do it

| A | B |
|---|---|
| 1 | 2 |

## Tasks

- [task 1] FR-01: matches spec

## Reconciliation

Verdict: Approved.

```bash
echo "hello"
```

```md
# Title

Write `x` here.
```
"""

PT = """---
name: spec
description: Cria uma especificacao de funcionalidade.
argument-hint: <nome da funcionalidade>
model: sonnet
summary: Auxiliar de especificacao.
notFor: Planejamento.
---
# Especificacao

Execute `/plan` depois de FR-01 e AC-02, veja [o guia](docs/guide.md) e https://example.com/x.
Use {{PROJECT_NAME}} com <build_test_cmd> (framework ADR 0023). <!-- keep -->

1. Primeiro passo
2. Segundo passo

- [ ] Faca isso

| A | B |
|---|---|
| 1 | 2 |

## Tasks

- [task 1] FR-01: matches spec

## Reconciliation

Verdict: Approved.

```bash
echo "hello"
```

```md
# Titulo

Escreva `x` aqui.
```
"""


def rules(src, tr):
    return {r["rule"] for r in translation.check(src, tr)}


class FrontmatterCheck(unittest.TestCase):
    def test_baseline_passes(self):
        self.assertEqual(translation.check(EN, PT), [])

    def test_L08_free_text_values_may_change_keys_and_enums_may_not(self):  # FR-11, AC-10
        self.assertEqual(translation.check(EN, PT.replace("summary: Auxiliar de especificacao.", "summary: Outro texto.")), [])
        self.assertIn("frontmatter values", rules(EN, PT.replace("model: sonnet", "model: opus")))
        self.assertIn("frontmatter keys", rules(EN, PT.replace("notFor:", "naoResponde:")))
        swapped = PT.replace("name: spec\ndescription:", "description:").replace("model: sonnet", "name: spec\nmodel: sonnet")
        self.assertIn("frontmatter keys", rules(EN, swapped))

    def test_L08_aliases_are_free_text_and_unknown_key_fails_safe(self):  # FR-11, AC-10
        src = "---\nresumo: Auxiliar.\nnaoResponde: Nada.\nfoo: bar\n---\n# T\n"
        ok = "---\nresumo: Helper.\nnaoResponde: Tudo.\nfoo: bar\n---\n# T\n"
        self.assertEqual(translation.check(src, ok), [])
        self.assertIn("frontmatter values", rules(src, ok.replace("foo: bar", "foo: barra")))

    def test_L08_frontmatter_shaped_fences(self):  # FR-11
        src = "# T\n\n```yaml\ndescription: One\nstatus: draft\n```\n"
        self.assertEqual(translation.check(src, src.replace("One", "Um")), [])
        self.assertIn("frontmatter values", rules(src, src.replace("draft", "rascunho")))
        dashed = "# T\n\n```\n---\ntitle: One\nid: 3\n---\n```\n"
        self.assertEqual(translation.check(dashed, dashed.replace("One", "Um")), [])
        self.assertIn("frontmatter values", rules(dashed, dashed.replace("id: 3", "id: 4")))


class FidelityCheck(unittest.TestCase):
    def test_L09_structure(self):  # FR-08, NFR-04, AC-03
        self.assertIn("heading count and levels", rules(EN, PT.replace("# Especificacao", "## Especificacao")))
        self.assertIn("numbered-item ordinals", rules(EN, PT.replace("2. Segundo", "3. Segundo")))
        self.assertIn("checkbox count", rules(EN, PT.replace("- [ ] Faca isso", "- Faca isso")))
        self.assertIn("table shape", rules(EN, PT.replace("| 1 | 2 |", "| 1 | 2 | 3 |")))
        self.assertIn("length ratio", rules(EN, PT + "x" * 3 * len(EN)))

    def test_L09_code_blocks_and_inline_code(self):  # FR-08, NFR-04, AC-03
        self.assertIn("code blocks", rules(EN, PT.replace('echo "hello"', 'echo "ola"')))
        self.assertIn("inline code spans", rules(EN, PT.replace("`/plan`", "`/planejar`")))
        # `md` blocks are translated but checked recursively
        self.assertIn("inline code spans", rules(EN, PT.replace("`x` aqui", "`y` aqui")))
        self.assertIn("heading count and levels", rules(EN, PT.replace("# Titulo", "Titulo")))

    def test_L09_placeholders_commands_ids_links(self):  # FR-08, NFR-04, AC-03
        self.assertIn("placeholders", rules(EN, PT.replace("{{PROJECT_NAME}}", "{{NOME_DO_PROJETO}}")))
        self.assertIn("runtime tokens", rules(EN, PT.replace("<build_test_cmd>", "<comando>")))
        self.assertIn("/commands", rules(EN, PT.replace("`/plan` depois", "`/plan` depois de /spec")))
        self.assertIn("ids", rules(EN, PT.replace("FR-01 e", "FR-02 e")))
        self.assertIn("link targets and URLs", rules(EN, PT.replace("docs/guide.md", "docs/guia.md")))
        self.assertIn("link targets and URLs", rules(EN, PT.replace("https://example.com/x", "https://example.com/y")))
        self.assertIn("HTML comments", rules(EN, PT.replace("<!-- keep -->", "<!-- manter -->")))
        self.assertIn("framework ADR/spec references", rules(EN, PT.replace("framework ADR 0023", "framework ADR 0024")))

    def test_L09_english_literals(self):  # FR-08, NFR-04, AC-03
        self.assertIn("English literals", rules(EN, PT.replace("## Tasks", "## Tarefas")))
        self.assertIn("English literals", rules(EN, PT.replace("## Reconciliation", "## Reconciliacao")))
        self.assertIn("English literals", rules(EN, PT.replace(": matches spec", ": corresponde a spec")))
        self.assertIn("English literals", rules(EN, PT.replace("Approved", "Aprovado")))
        diverged = EN.replace("matches spec", "diverged")
        self.assertIn("English literals", rules(diverged, PT.replace("matches spec", "divergiu")))
        scope = EN.replace("- [task 1] FR-01: matches spec", "- [task 1] out of scope: a.py")
        self.assertIn("English literals", rules(scope, PT.replace("- [task 1] FR-01: matches spec", "- [task 1] fora do escopo: a.py")))


class SoftLineBreaks(unittest.TestCase):
    """A single line break inside a paragraph is a space in Markdown, so a
    translation that rewraps lines must not fail on spans, references or
    numbers the source happened to split across lines."""

    def test_inline_code_split_across_lines(self):
        src = ("and after the last one `metrics.py finish\n"
               "--feature <spec id>`. They let `/metrics` attribute subagents.\n")
        tr = ("e depois da ultima `metrics.py finish --feature <spec id>`.\n"
              "Eles permitem que o `/metrics` atribua subagentes.\n")
        self.assertEqual(translation.check(src, tr), [])
        self.assertIn("inline code spans", rules(src, tr.replace("--feature <spec id>", "--feature <id>")))

    def test_inline_code_never_spans_a_blank_line(self):
        src = "One `a` here and a stray ` tick.\n\nNext `b` paragraph.\n"
        self.assertEqual(translation.check(src, "Um `a` aqui e um ` solto.\n\nProximo `b` paragrafo.\n"), [])
        self.assertIn("inline code spans", rules(src, "Um `a` aqui e um ` solto.\n\nProximo `c` paragrafo.\n"))

    def test_framework_reference_split_across_lines(self):
        src = "blocks the agent (framework ADR\n0025), so the gate still blocks.\n"
        tr = "bloqueia o agente (framework ADR 0025),\nentao o gate ainda bloqueia.\n"
        self.assertEqual(translation.check(src, tr), [])
        self.assertIn("framework ADR/spec references", rules(src, tr.replace("0025", "0026")))

    def test_wrapped_number_is_not_a_list_item(self):
        src = ("9. Gate step: it exits with code 2 (framework ADR\n"
               "   0025) — so the gate still blocks.\n"
               "10. Next step.\n"
               "    1. Nested first.\n"
               "    2. Nested second.\n"
               "11. Last step.\n")
        tr = ("9. Passo do gate: sai com codigo 2 (framework ADR 0025)\n"
              "   — entao o gate ainda bloqueia.\n"
              "10. Proximo passo.\n"
              "    1. Primeiro aninhado.\n"
              "    2. Segundo aninhado.\n"
              "11. Ultimo passo.\n")
        self.assertEqual(translation.check(src, tr), [])
        self.assertIn("numbered-item ordinals", rules(src, tr.replace("11. Ultimo", "12. Ultimo")))
        self.assertIn("numbered-item ordinals", rules(src, tr.replace("    2. Segundo", "    3. Segundo")))


class CheckCli(TempCase):
    def test_L10_failing_file_stays_english_with_reasons(self):  # NFR-04
        src, bad, rec = (os.path.join(self.tmp, n) for n in ("en.md", "pt.md", "rec.json"))
        self.write(src, EN)
        self.write(bad, PT.replace("## Tasks", "## Tarefas"))
        ok = self.run_py(SCRIPT, "check", "--source", src, "--translated", src)
        self.assertTrue(json.loads(ok.stdout)["ok"])
        res = self.run_py(SCRIPT, "check", "--source", src, "--translated", bad, check=False)
        self.assertEqual(res.returncode, 1)
        report = json.loads(res.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "english")
        self.assertEqual(report["reasons"][0]["rule"], "English literals")
        # the caller records it through the existing apply, with no staged file
        root = os.path.join(self.tmp, "pristine")
        self.write(os.path.join(root, "commands", "spec.md"), EN)
        out = self.run_py(SCRIPT, "apply", "--source", root, "--record", rec, "--language-code", "pt-BR",
                          "--language", "Portuguese", "--path", "commands/spec.md",
                          "--status", report["status"], "--reason", report["reason"])
        self.assertEqual(json.loads(out.stdout)["status"], "english")
        entry = json.loads(self.read(rec))["files"]["commands/spec.md"]
        self.assertEqual(entry["status"], "english")
        self.assertIn("## Tasks", entry["reason"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "commands", "spec.md")))


if __name__ == "__main__":
    unittest.main()
