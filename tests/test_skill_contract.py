from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "repomind"
SKILL = PLUGIN / "skills" / "repomind"
SKILL_MD = SKILL / "SKILL.md"


class SkillContractTests(unittest.TestCase):
    def setUp(self):
        self.text = SKILL_MD.read_text(encoding="utf-8")

    def test_standard_skill_layout(self):
        self.assertTrue(SKILL_MD.is_file())
        self.assertTrue((SKILL / "scripts" / "search.py").is_file())
        self.assertTrue((SKILL / "config" / "defaults.json").is_file())
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())
        for name in (
            "relevance-evaluation.md",
            "deep-analysis.md",
            "output-format.md",
        ):
            self.assertTrue((SKILL / "references" / name).is_file())

    def test_frontmatter_and_arguments(self):
        self.assertRegex(
            self.text,
            r"\A---\nname: repomind\ndescription: .+\nmetadata:\n",
        )
        self.assertIn("$ARGUMENTS", self.text)
        self.assertIn("argument-hint:", self.text)

    def test_scope_gate_precedes_all_tool_use(self):
        gate = self.text.index("## Mandatory scope gate")
        preconditions = self.text.index("## Preconditions")
        self.assertLess(gate, preconditions)
        gate_text = self.text[gate:preconditions]
        self.assertIn("Do not run any tool", gate_text)
        self.assertIn("STOP", gate_text)
        self.assertIn("narrow implementation", gate_text)

    def test_helper_path_resolution_is_explicit_and_fail_closed(self):
        self.assertIn('SKILL_DIR=<absolute path to this skill>', self.text)
        self.assertIn('SEARCH_SCRIPT="$SKILL_DIR/scripts/search.py"', self.text)
        self.assertIn('test -f "$SEARCH_SCRIPT"', self.text)
        self.assertIn("best-effort RepoMind-style workflow", self.text)
        self.assertIn("do not perform GitHub research without", self.text)

    def test_skill_is_concise_and_references_supporting_files(self):
        self.assertLess(len(self.text.splitlines()), 220)
        for name in (
            "references/relevance-evaluation.md",
            "references/deep-analysis.md",
            "references/output-format.md",
        ):
            self.assertIn(name, self.text)

    def test_old_runtime_paths_are_not_used(self):
        self.assertNotIn(".repomind/search.py", self.text)
        self.assertFalse((ROOT / ".claude" / "skills" / "repomind.md").exists())
        self.assertFalse((ROOT / ".repomind" / "search.py").exists())

    def test_plugin_manifests_match(self):
        claude = json.loads(
            (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        codex = json.loads(
            (PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        for field in ("name", "version", "description", "repository", "license"):
            self.assertEqual(claude[field], codex[field])
        self.assertEqual(codex["skills"], "./skills/")

    def test_marketplaces_point_to_same_plugin(self):
        claude = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        codex = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(claude["name"], "repomind")
        self.assertEqual(codex["name"], "repomind")
        self.assertEqual(
            claude["plugins"][0]["source"], "./plugins/repomind"
        )
        self.assertEqual(
            codex["plugins"][0]["source"]["path"], "./plugins/repomind"
        )

    def test_skill_contains_no_unbalanced_four_backtick_fence(self):
        self.assertEqual(self.text.count("````") % 2, 0)


if __name__ == "__main__":
    unittest.main()
