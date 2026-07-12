import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "usefulness_cases.json"


RUBRIC_DIMENSIONS = (
    "relevance",
    "specificity",
    "implementation_guidance",
    "applicability_explanation",
    "anti_hallucination",
)

REPOSITORY_URL = re.compile(
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
)
FILE_REFERENCE = re.compile(
    r"[A-Za-z0-9_./-]+\.(?:py|js|ts|tsx|go|rs|java|md)"
)


def each_repository_has_file_evidence(output):
    """Associate evidence with the repository whose URL begins each segment."""
    repositories = list(REPOSITORY_URL.finditer(output))
    if not repositories:
        return False
    return all(
        FILE_REFERENCE.search(
            output[repository.end():next_start]
        )
        for repository, next_start in zip(
            repositories,
            [match.start() for match in repositories[1:]] + [len(output)],
        )
    )


class UsefulnessEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def score_output(self, case, output):
        lower = output.lower()
        file_refs = FILE_REFERENCE.findall(output)
        github_refs = re.findall(r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", output)
        prompt_terms = {
            term.lower()
            for term in case["research_terms"]
        }
        matched_terms = {term for term in prompt_terms if term in lower}

        relevance = min(5, 1 + len(matched_terms))
        specificity = min(5, len(set(github_refs)) * 2 + min(3, len(set(file_refs))))
        implementation_guidance = min(
            5,
            sum(
                1
                for term in (
                    "implementation guidance",
                    "model",
                    "persist",
                    "separate",
                    "version",
                    "commit",
                    "idempotent",
                    "boundary",
                    "retry",
                )
                if term in lower
            ),
        )
        applicability_explanation = min(
            5,
            (2 if "why useful" in lower else 0)
            + sum(
                1
                for term in (
                    "maps to",
                    "demonstrates",
                    "separates",
                    "directly",
                    "useful",
                )
                if term in lower
            ),
        )
        anti_hallucination = min(
            5,
            len(set(github_refs))
            + min(2, len(set(file_refs)))
            + (1 if '<repomind-result status="complete">' in lower else 0)
            + (1 if "freshness:" in lower else 0),
        )

        return {
            "relevance": relevance,
            "specificity": specificity,
            "implementation_guidance": implementation_guidance,
            "applicability_explanation": applicability_explanation,
            "anti_hallucination": anti_hallucination,
        }

    def test_fixture_defines_written_rubric_and_five_cases(self):
        rubric = self.fixture["rubric"]
        self.assertEqual(tuple(rubric["dimensions"]), RUBRIC_DIMENSIONS)
        self.assertEqual(rubric["scale"], "0-5")
        self.assertEqual(rubric["minimum_total_improvement_percent"], 30)
        self.assertEqual(len(self.fixture["cases"]), 5)

    def test_each_case_compares_baseline_to_repomind_assisted_output(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertIn("prompt", case)
                self.assertEqual(case["baseline"]["mode"], "without_repomind")
                self.assertEqual(case["repomind"]["mode"], "with_repomind")
                self.assertIn("output", case["baseline"])
                self.assertIn("output", case["repomind"])
                self.assertIn("research_terms", case)
                self.assertNotIn("architecture_terms", case)

    def test_repomind_output_scores_at_least_30_percent_higher(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                baseline_scores = self.score_output(case, case["baseline"]["output"])
                repomind_scores = self.score_output(case, case["repomind"]["output"])
                baseline_total = sum(baseline_scores.values())
                repomind_total = sum(repomind_scores.values())
                improvement = ((repomind_total - baseline_total) / baseline_total) * 100
                self.assertGreaterEqual(
                    improvement,
                    self.fixture["rubric"]["minimum_total_improvement_percent"],
                )

    def test_derived_scores_cover_exact_rubric_dimensions_and_scale(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                for output in (case["baseline"]["output"], case["repomind"]["output"]):
                    scores = self.score_output(case, output)
                    self.assertEqual(set(scores), set(RUBRIC_DIMENSIONS))
                    for score in scores.values():
                        self.assertIsInstance(score, int)
                        self.assertGreaterEqual(score, 0)
                        self.assertLessEqual(score, 5)

    def test_repomind_never_regresses_on_relevance_or_specificity(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                baseline_scores = self.score_output(case, case["baseline"]["output"])
                repomind_scores = self.score_output(case, case["repomind"]["output"])
                for dimension in ("relevance", "specificity"):
                    self.assertGreaterEqual(
                        repomind_scores[dimension],
                        baseline_scores[dimension],
                    )

    def test_repomind_outputs_contain_concrete_code_location_evidence(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                output = case["repomind"]["output"]
                self.assertIn("https://github.com/", output)
                self.assertRegex(output, FILE_REFERENCE)
                self.assertIn("why useful", output.lower())
                self.assertIn("implementation", output.lower())

    def test_repomind_outputs_are_comparative_result_envelopes(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                output = case["repomind"]["output"]
                repositories = set(
                    re.findall(
                        r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
                        output,
                    )
                )
                self.assertGreaterEqual(len(repositories), 2)
                self.assertTrue(each_repository_has_file_evidence(output))
                self.assertIn("<repomind-result status=\"complete\">", output)
                self.assertIn("trade-off", output.lower())
                self.assertIn("freshness:", output.lower())
                self.assertIn("applicability:", output.lower())

    def test_comparative_evidence_rejects_a_repository_without_a_file(self):
        output = (
            "https://github.com/example/with-file uses src/worker.py; "
            "https://github.com/example/without-file provides another approach."
        )
        self.assertFalse(each_repository_has_file_evidence(output))

    def test_baseline_outputs_are_intentionally_generic(self):
        for case in self.fixture["cases"]:
            with self.subTest(case=case["id"]):
                output = case["baseline"]["output"].lower()
                self.assertNotIn("https://github.com/", output)
                self.assertIn("consider", output)


if __name__ == "__main__":
    unittest.main()
