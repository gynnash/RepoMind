from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "repomind"
SKILL = PLUGIN / "skills" / "repomind"
SKILL_MD = SKILL / "SKILL.md"
OPENAI_YAML = SKILL / "agents" / "openai.yaml"


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

    def test_pre_confirmation_state_precedes_all_tool_use(self):
        gate = self.text.index("## State 1: Before research confirmation")
        preconditions = self.text.index("## Preconditions")
        self.assertLess(gate, preconditions)
        gate_text = self.text[gate:preconditions]
        for prohibition in (
            "Do not run any tool",
            "Do not initialize the database",
            "Do not read references",
            "Do not search GitHub",
        ):
            self.assertIn(prohibition, gate_text)
        self.assertIn("edit the candidates", gate_text)
        self.assertIn("provide free-form input", gate_text)
        self.assertIn("request another set", gate_text)

    def test_two_states_and_authoritative_query_routing(self):
        self.assertIn("## State 1: Before research confirmation", self.text)
        self.assertIn("## State 2: After research confirmation", self.text)
        state_two = self.text.split("## State 2: After research confirmation", 1)[1]
        self.assertIn("authoritative research question", state_two)
        self.assertIn("adaptation-only context", state_two)

    def test_four_scenario_matrix(self):
        for phrase in (
            "feature design",
            "engineering pattern",
            "design rationale",
            "syntax question",
            "single API",
            "routine debugging",
        ):
            self.assertIn(phrase, self.text)

    def test_no_query_conversation_and_query_direct_research(self):
        for phrase in (
            "conversation context",
            "design material",
            "task code",
            "lightweight repository context",
            "one recommendation",
            "2–3 alternatives",
            "research directly",
        ):
            self.assertIn(phrase, self.text)

    def test_cache_sufficiency_is_quality_based(self):
        section = self.text.split("## Cache workflow", 1)[1]
        for phrase in (
            "question coverage",
            "distinct approaches",
            "independent repositories",
            "evidence quality",
            "freshness",
        ):
            self.assertIn(phrase, section)
        self.assertIn("not card count", section)
        self.assertLess(section.index("Search local cards"), section.index("Search GitHub conditionally"))
        self.assertIn("classic repositories", section)
        self.assertIn("age warning", section)

    def test_collaboration_has_five_statuses(self):
        for status in ("proposed", "confirmed", "researching", "synthesized", "blocked"):
            self.assertRegex(self.text, rf"(?m)^- `{status}`:")

    def test_openai_metadata_is_adaptive(self):
        metadata = OPENAI_YAML.read_text(encoding="utf-8")
        self.assertIn('short_description: "Research reusable designs from public codebases"', metadata)
        self.assertIn(
            'default_prompt: "Use $repomind to research public implementations relevant to this design question."',
            metadata,
        )
        self.assertIn("allow_implicit_invocation: true", metadata)
        self.assertIn("comparative evidence", metadata)
        self.assertIn("keyword matching", metadata)

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
