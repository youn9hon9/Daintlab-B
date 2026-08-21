from __future__ import annotations

import unittest

from src.tool_filter import select_retrieval_tools


def tool(name: str) -> dict:
    return {"type": "function", "function": {"name": name, "parameters": {}}}


class ToolFilterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tools = [
            tool("openapi_law_search"),
            tool("openapi_law_get_article"),
            tool("rag_vector_query"),
        ]

    def test_high_confidence_law_query_filters_tools(self) -> None:
        selected, family = select_retrieval_tools("의료법 조문을 찾아줘", self.tools)
        self.assertEqual(family, "law")
        self.assertEqual(len(selected), 2)

    def test_ambiguous_query_keeps_all_tools(self) -> None:
        selected, family = select_retrieval_tools("고혈압 근거를 찾아줘", self.tools)
        self.assertEqual(family, "all")
        self.assertEqual(selected, self.tools)

    def test_missing_family_tools_falls_back_to_all(self) -> None:
        tools = [tool("rag_vector_query")]
        selected, family = select_retrieval_tools("약사법을 찾아줘", tools)
        self.assertEqual(family, "all")
        self.assertEqual(selected, tools)


if __name__ == "__main__":
    unittest.main()
