from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTests(unittest.TestCase):
    def test_public_release_files_exist(self):
        self.assertTrue((ROOT / "LICENSE").is_file())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for command in (
            "claude plugin marketplace add gynnash/RepoMind",
            "claude plugin install repomind@repomind",
            "codex plugin marketplace add gynnash/RepoMind --ref main",
            "codex plugin add repomind@repomind",
            "plugins/repomind/skills/repomind",
        ):
            self.assertIn(command, readme)

    def test_runtime_artifacts_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (
            ".repomind/repomind.db",
            ".repomind/repomind.db-wal",
            ".repomind/repomind.db-shm",
            "__pycache__/",
            "*.pyc",
        ):
            self.assertIn(pattern, ignore)

    def test_readme_documents_usefulness_evaluation(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("comparative usefulness evaluation", readme.lower())
        fixture = "tests/fixtures/usefulness_cases.json"
        self.assertIn(fixture, readme)
        self.assertTrue((ROOT / fixture).is_file())
        self.assertIn("30%", readme)

    def test_readme_documents_generalized_public_behavior(self):
        readme = " ".join(
            (ROOT / "README.md").read_text(encoding="utf-8").lower().split()
        )
        for phrase in (
            "research implementation mechanisms, engineering patterns, workflows",
            "replace all candidates",
            "explicit query is authoritative",
            "1–30 days",
            "synthesized research report",
            "complete|partial|needs_clarification|out_of_scope|unavailable",
            "cross-plugin collaboration",
        ):
            self.assertIn(phrase, readme)
        self.assertNotIn("ask an architecture research question", readme)

    def test_readme_has_four_scenario_matrix(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for row in (
            "| New | No |",
            "| New | Yes |",
            "| Existing | No |",
            "| Existing | Yes |",
        ):
            self.assertIn(row, readme)

    def test_tutorial_covers_discovery_cache_refresh_and_partial_results(self):
        tutorial = (ROOT / "docs" / "tutorial.md").read_text(encoding="utf-8").lower()
        for phrase in (
            "no-query discovery",
            "new project with an explicit query",
            "existing project with a non-architecture query",
            "not due",
            "unchanged sha",
            "localized change",
            "global or unmappable change",
            'status="partial"',
        ):
            self.assertIn(phrase, tutorial)

    def test_tutorial_does_not_restore_architecture_only_positioning(self):
        tutorial = " ".join(
            (ROOT / "docs" / "tutorial.md")
            .read_text(encoding="utf-8")
            .lower()
            .split()
        )
        for legacy_phrase in (
            "a good repomind request names an architectural concern",
            "/repomind:repomind <architecture question>",
            "clearly asks for architecture research",
            "parse the architecture intent",
            "architectural relevance",
            "rewrite the request around a system-level decision",
        ):
            self.assertNotIn(legacy_phrase, tutorial)

    def test_tutorial_states_generalized_research_scope(self):
        tutorial = " ".join(
            (ROOT / "docs" / "tutorial.md")
            .read_text(encoding="utf-8")
            .lower()
            .split()
        )
        for phrase in (
            "reusable implementation mechanism, engineering or design pattern, workflow, interface, or design rationale",
            "narrow syntax questions, single-framework api usage, and routine debugging remain out of scope",
            "score the remaining repositories for relevance to the research question",
        ):
            self.assertIn(phrase, tutorial)


if __name__ == "__main__":
    unittest.main()
