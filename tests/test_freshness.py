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


if __name__ == "__main__":
    unittest.main()
