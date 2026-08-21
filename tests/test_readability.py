from __future__ import annotations

import unittest

from src.readability import assess_readability


class ReadabilityTest(unittest.TestCase):
    def test_empty_content_reports_no_sentences(self) -> None:
        result = assess_readability("")

        self.assertEqual(result.sentence_count, 0)
        self.assertEqual(result.long_sentence_count, 0)
        self.assertEqual(result.max_sentence_chars, 0)

    def test_short_sentences_are_not_flagged(self) -> None:
        result = assess_readability("두통이 있으시군요. 물을 충분히 드세요.")

        self.assertEqual(result.sentence_count, 2)
        self.assertEqual(result.long_sentence_count, 0)

    def test_long_sentence_is_flagged(self) -> None:
        long_sentence = "이것은 " + "매우 " * 40 + "긴 문장입니다."

        result = assess_readability(long_sentence)

        self.assertEqual(result.sentence_count, 1)
        self.assertEqual(result.long_sentence_count, 1)
        self.assertGreater(result.max_sentence_chars, 120)

    def test_mixed_sentences_count_only_the_long_ones(self) -> None:
        short = "짧은 문장입니다."
        long_sentence = "이것은 " + "매우 " * 40 + "긴 문장입니다."
        content = f"{short} {long_sentence}"

        result = assess_readability(content)

        self.assertEqual(result.sentence_count, 2)
        self.assertEqual(result.long_sentence_count, 1)


if __name__ == "__main__":
    unittest.main()
