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
            "Do not run the RepoMind helper",
            "Do not initialize the database",
            "Do not search GitHub",
            "Do not generate cards",
        ):
            self.assertIn(prohibition, gate_text)
        self.assertNotIn("Do not run any tool", gate_text)
        self.assertIn("bounded read-only local inspection", gate_text)
        self.assertIn("README", gate_text)
        self.assertIn("task code", gate_text)
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

    def test_trigger_contract_accepts_research_and_rejects_narrow_help(self):
        description = self.text.split("---", 2)[1].lower()
        state_one = self.text.split("## State 1: Before research confirmation", 1)[1].split(
            "## State 2: After research confirmation", 1
        )[0].lower()

        valid_contract_relationships = {
            "Research plugin lifecycle and isolation designs in public codebases": (
                (description, "feature design"),
                (state_one, "explicit query"),
                (state_one, "research directly"),
            ),
            "Compare scheduler retry patterns across repositories": (
                (description, "engineering patterns"),
                (description, "comparative evidence"),
                (state_one, "research directly"),
            ),
            "Find reusable Agent Skill workflow designs and rationale": (
                (description, "design rationale"),
                (description, "public codebases"),
                (state_one, "research directly"),
            ),
        }
        invalid_contract_relationships = {
            "How do I implement React useState?": (
                (state_one, "syntax question"),
                (state_one, "ordinary coding help"),
            ),
            "What arguments does this API accept?": (
                (state_one, "single api question"),
                (state_one, "documentation"),
            ),
            "Debug this failing unit test": (
                (state_one, "routine debugging"),
                (state_one, "normal debugging"),
            ),
        }

        for request, relationships in {
            **valid_contract_relationships,
            **invalid_contract_relationships,
        }.items():
            with self.subTest(request=request):
                for contract_text, normative_clause in relationships:
                    self.assertIn(normative_clause, contract_text)

        metadata = OPENAI_YAML.read_text(encoding="utf-8").lower()
        self.assertIn("allow_implicit_invocation: true", metadata)
        self.assertIn("genuine comparative evidence", metadata)
        self.assertIn("not from keyword matching alone", metadata)

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

    def test_cache_workflow_orchestrates_adaptive_validation_commands(self):
        section = self.text.split("## Cache workflow", 1)[1]
        commands = ("repos-for-cards", "record-repo-check", "affected-cards", "refresh-cards")
        for command in commands:
            self.assertIn(command, section)
            self.assertIn(command, self.text.split("## Helper interface", 1)[1])
        self.assertLess(section.index("repos-for-cards"), section.index("Search GitHub conditionally"))
        for phrase in ("not due", "HEAD", "structural", "localized", "full refresh",
                       "unverified", "remote validation fails", "legacy"):
            self.assertIn(phrase, section)

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

    def test_relevance_scoring_is_question_centered(self):
        text = (SKILL / "references" / "relevance-evaluation.md").read_text(
            encoding="utf-8"
        )
        for dimension in (
            "question_match",
            "transferability",
            "constraint_fit",
            "evidence_depth",
            "independence",
        ):
            self.assertIn(dimension, text)
        self.assertIn("research object", text)
        self.assertIn("Stars break ties only", text)

    def test_analysis_cards_are_dynamic_and_evidence_backed(self):
        text = (SKILL / "references" / "deep-analysis.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("Always create `architecture`", text)
        self.assertIn("question-relevant dimensions", text)
        for field in (
            "research_object",
            "mechanism",
            "limitations",
            "transferability",
            "sha",
            "evidence_paths",
            "keywords",
        ):
            self.assertIn(field, text)
        self.assertIn("documented rationale", text)
        self.assertIn("inference", text)

    def test_no_mandatory_architecture_dimension_bundle_survives(self):
        combined = "\n".join(path.read_text(encoding="utf-8") for path in (
            SKILL_MD, SKILL / "references" / "deep-analysis.md",
            SKILL / "references" / "output-format.md",
            SKILL / "references" / "relevance-evaluation.md",
        )).lower()
        for phrase in ("mandatory dimensions", "always create `architecture`",
                       "must create architecture", "architecture, design_patterns, data_flow"):
            self.assertNotIn(phrase, combined)

    def test_result_envelope_and_evidence_provenance(self):
        text = (SKILL / "references" / "output-format.md").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '<repomind-result status="complete|partial|needs_clarification|out_of_scope|unavailable">',
            text,
        )
        for heading in (
            "## Research conclusion",
            "## Approaches and trade-offs",
            "## Public implementation evidence",
            "## Implications for the current project",
            "## Evidence freshness",
            "## Follow-up directions",
        ):
            self.assertIn(heading, text)
        for field in ("URL", "SHA", "files", "card ID"):
            self.assertIn(field, text)
        for freshness in ("new", "validated_cache", "unverified_cache"):
            self.assertIn(freshness, text)
        self.assertIn("next action", text)


if __name__ == "__main__":
    unittest.main()
