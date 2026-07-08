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
        self.assertIn("tests/fixtures/usefulness_cases.json", readme)
        self.assertIn("30%", readme)


if __name__ == "__main__":
    unittest.main()
