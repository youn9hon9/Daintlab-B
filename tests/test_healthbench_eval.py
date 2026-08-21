import unittest

from eval.run_healthbench import (
    RubricItem,
    calculate_score,
    parse_grader_response,
    select_examples,
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

    def test_grader_json_accepts_markdown_fence(self):
        content = '```json\n{"explanation":"ok","criteria_met":true}\n```'
        self.assertTrue(parse_grader_response(content))

    def test_grader_json_requires_boolean(self):
        with self.assertRaises(ValueError):
            parse_grader_response('{"criteria_met":"true"}')


if __name__ == "__main__":
    unittest.main()
