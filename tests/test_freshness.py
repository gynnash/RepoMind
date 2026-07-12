import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/repomind/skills/repomind/scripts/freshness.py"


def load_freshness():
    spec = importlib.util.spec_from_file_location("repomind_freshness", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FreshnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.freshness = load_freshness()

    def test_median_commit_interval_sorts_timestamps(self):
        self.assertEqual(
            self.freshness.median_commit_interval_days(
                [
                    "2026-01-11T00:00:00Z",
                    "2026-01-01T00:00:00Z",
                    "2026-01-03T00:00:00Z",
                ]
            ),
            5.0,
        )

    def test_median_commit_interval_requires_two_timestamps(self):
        self.assertIsNone(self.freshness.median_commit_interval_days([]))
        self.assertIsNone(
            self.freshness.median_commit_interval_days(["2026-01-01T00:00:00Z"])
        )

    def test_stable_checks_grow_from_commit_cadence(self):
        self.assertEqual(
            self.freshness.calculate_check_interval(10, 2, False, False, 1, 30, 1.5, 0.5),
            22.5,
        )

    def test_relevant_global_change_decays_interval_after_growth(self):
        self.assertEqual(
            self.freshness.calculate_check_interval(10, 4, True, True, 1, 30, 1.5, 0.5),
            5.0,
        )

    def test_interval_is_clamped_and_rounded(self):
        self.assertEqual(
            self.freshness.calculate_check_interval(0.1, 0, False, False, 1, 30, 1.5, 0.5),
            1.0,
        )
        self.assertEqual(
            self.freshness.calculate_check_interval(10 / 3, 1, False, False, 1, 30, 1.1, 0.5),
            3.667,
        )

    def test_missing_or_equal_next_check_is_due(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(self.freshness.is_check_due(None, now))
        self.assertTrue(self.freshness.is_check_due(now, now))
        self.assertFalse(self.freshness.is_check_due(now + timedelta(seconds=1), now))

    def test_check_due_compares_offset_timestamps_as_instants(self):
        self.assertTrue(
            self.freshness.is_check_due(
                "2026-07-12T09:00:00+08:00", "2026-07-12T08:00:00Z"
            )
        )

    def test_check_due_treats_naive_timestamps_as_utc(self):
        self.assertTrue(
            self.freshness.is_check_due(
                "2026-07-12T08:00:00", "2026-07-12T08:00:00Z"
            )
        )

    def test_unchanged_head_is_unchanged(self):
        result = self.freshness.classify_repository_change({
            "previous_head_sha": "abc", "head_sha": "abc",
            "changed_paths": ["src/changed.py"],
        })
        self.assertEqual(result["kind"], "unchanged")
        self.assertEqual(result["affected_paths"], [])

    def test_deleted_evidence_is_localized(self):
        result = self.freshness.classify_repository_change({
            "previous_head_sha": "abc", "head_sha": "def",
            "changed_paths": ["src/core/engine.py"],
            "deleted_paths": ["src/core/engine.py"],
            "evidence_paths": ["src/core/engine.py"],
        })
        self.assertEqual(result["kind"], "localized")
        self.assertEqual(result["affected_paths"], ["src/core/engine.py"])

    def test_deleted_only_evidence_is_localized(self):
        result = self.freshness.classify_repository_change({
            "previous_head_sha": "abc", "head_sha": "def",
            "changed_paths": [],
            "deleted_paths": ["src/core/engine.py"],
            "evidence_paths": ["src/core/engine.py"],
        })
        self.assertEqual(result["kind"], "localized")
        self.assertEqual(result["affected_paths"], ["src/core/engine.py"])

    def test_canonical_equivalent_paths_match(self):
        result = self.freshness.classify_repository_change({
            "previous_head_sha": "abc", "head_sha": "def",
            "changed_paths": ["./src//core/../core/engine.py"],
            "evidence_paths": ["src/core/engine.py"],
        })
        self.assertEqual(result["kind"], "localized")
        self.assertEqual(result["affected_paths"], ["src/core/engine.py"])

    def test_architecture_and_structure_change_is_global(self):
        result = self.freshness.classify_repository_change({
            "previous_head_sha": "abc", "head_sha": "def",
            "changed_paths": ["README.md"],
            "architecture_changed": True, "structure_changed": True,
        })
        self.assertEqual(result["kind"], "global")

    def test_key_directory_ratio_at_half_is_global(self):
        result = self.freshness.classify_repository_change({
            "previous_head_sha": "abc", "head_sha": "def",
            "changed_paths": ["src/a.py", "docs/note.md"],
            "key_directories": ["src"],
        })
        self.assertEqual(result["kind"], "global")

    def test_commit_count_does_not_make_unrelated_change_relevant(self):
        result = self.freshness.classify_repository_change({
            "previous_head_sha": "abc", "head_sha": "def",
            "commit_count": 500, "changed_paths": ["CHANGELOG.md"],
            "evidence_paths": ["src/engine.py"],
            "module_paths": ["src"],
        })
        self.assertEqual(result["kind"], "unrelated")


if __name__ == "__main__":
    unittest.main()
