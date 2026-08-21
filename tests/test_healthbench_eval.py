import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from eval.run_healthbench import (
    RubricItem,
    calculate_score,
    bootstrap_interval,
    parse_grader_response,
    read_secret,
    select_examples,
    select_representative_examples,
    select_stratified_examples,
    tag_scores,
)


class LocalHealthBenchTests(unittest.TestCase):
    def test_selection_is_reproducible(self):
        examples = [{"prompt_id": str(index)} for index in range(20)]
        first = select_examples(examples, count=5, seed=7)
        second = select_examples(examples, count=5, seed=7)
        self.assertEqual(first, second)

    def test_score_matches_healthbench_weighting(self):
        items = [
            RubricItem("positive", 4),
            RubricItem("negative behavior", -2),
            RubricItem("another positive", 6),
        ]
        self.assertEqual(calculate_score(items, [True, False, True]), 1.0)
        self.assertEqual(calculate_score(items, [True, True, False]), 0.2)

    def test_stratified_selection_covers_themes(self):
        examples = [
            {"prompt_id": f"{theme}-{index}", "example_tags": [f"theme:{theme}"], "rubrics": [{}] * (index + 1)}
            for theme in ("a", "b", "c")
            for index in range(4)
        ]
        selected = select_stratified_examples(examples, count=3, seed=0)
        self.assertEqual({item["example_tags"][0] for item in selected}, {"theme:a", "theme:b", "theme:c"})

    def test_representative_selection_is_proportional(self):
        examples = [
            {"prompt_id": f"a-{index}", "example_tags": ["theme:a"]}
            for index in range(8)
        ] + [
            {"prompt_id": f"b-{index}", "example_tags": ["theme:b"]}
            for index in range(2)
        ]
        selected = select_representative_examples(examples, count=5, seed=0)
        self.assertEqual(sum(item["example_tags"][0] == "theme:a" for item in selected), 4)
        self.assertEqual(sum(item["example_tags"][0] == "theme:b" for item in selected), 1)

    def test_bootstrap_groups_repeats_by_prompt(self):
        records = [
            {"prompt_id": "a", "score": 0.0},
            {"prompt_id": "a", "score": 1.0},
            {"prompt_id": "b", "score": 1.0},
        ]
        interval = bootstrap_interval(records, seed=0, iterations=200)
        self.assertIsNotNone(interval)
        self.assertLessEqual(interval[0], 0.75)
        self.assertGreaterEqual(interval[1], 0.75)

    def test_axis_score_uses_tagged_rubrics(self):
        items = [RubricItem("a", 2, ("axis:accuracy",)), RubricItem("b", 2, ("axis:completeness",))]
        self.assertEqual(tag_scores(items, [True, False], "axis:"), {"axis:accuracy": 1.0, "axis:completeness": 0.0})

    def test_axis_without_positive_points_is_omitted(self):
        items = [RubricItem("penalty", -1, ("axis:accuracy",))]
        self.assertEqual(tag_scores(items, [True], "axis:"), {})

    def test_grader_json_accepts_markdown_fence(self):
        content = '```json\n{"explanation":"ok","criteria_met":true}\n```'
        self.assertTrue(parse_grader_response(content))

    def test_grader_json_requires_boolean(self):
        with self.assertRaises(ValueError):
            parse_grader_response('{"criteria_met":"true"}')

    def test_secret_can_be_loaded_from_env_file(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("JUDGE_KEY=test-value\n", encoding="utf-8")
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(read_secret("JUDGE_KEY", env_file), "test-value")

    def test_process_environment_takes_precedence(self):
        with TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text("JUDGE_KEY=file-value\n", encoding="utf-8")
            with patch.dict("os.environ", {"JUDGE_KEY": "process-value"}):
                self.assertEqual(read_secret("JUDGE_KEY", env_file), "process-value")


if __name__ == "__main__":
    unittest.main()
