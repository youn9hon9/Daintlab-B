from __future__ import annotations

import unittest

from src.retrieval_tools import select_retrieval_tools


def _tools(*names: str):
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": name,
                "parameters": {"type": "object", "properties": {}},
            },
        }
        for name in names
    ]


class RetrievalToolSelectionTest(unittest.TestCase):
    def test_guideline_query_gets_search_and_page_tools(self) -> None:
        tools = _tools(
            "index_get_relevant_nodes",
            "index_get_page_content",
            "index_keyword_search",
            "openapi_law_search",
            "rag_vector_query",
        )

        selected = select_retrieval_tools(
            "당뇨병 최신 가이드라인 권고를 확인해 주세요",
            tools,
            limit=3,
        )

        self.assertEqual(
            [tool["function"]["name"] for tool in selected],
            [
                "index_get_relevant_nodes",
                "index_get_page_content",
                "index_keyword_search",
            ],
        )

    def test_law_query_does_not_expose_unrelated_tools(self) -> None:
        tools = _tools(
            "openapi_law_search",
            "openapi_law_list_articles",
            "openapi_law_get_article",
            "adr_retrieve_drug_info",
        )

        selected = select_retrieval_tools(
            "한국 의료법 조문과 시행 기준",
            tools,
            limit=3,
        )

        self.assertEqual(
            [tool["function"]["name"] for tool in selected],
            [
                "openapi_law_search",
                "openapi_law_list_articles",
                "openapi_law_get_article",
            ],
        )

    def test_english_law_query_selects_law_workflow(self) -> None:
        tools = _tools(
            "openapi_law_search",
            "openapi_law_list_articles",
            "openapi_law_get_article",
            "rag_vector_query",
        )

        selected = select_retrieval_tools(
            "Find the applicable Korean medical law and article",
            tools,
            limit=3,
        )

        self.assertEqual(
            [tool["function"]["name"] for tool in selected],
            [
                "openapi_law_search",
                "openapi_law_list_articles",
                "openapi_law_get_article",
            ],
        )

    def test_medication_usage_does_not_trigger_law_tools(self) -> None:
        tools = _tools(
            "adr_retrieve_drug_info",
            "openapi_law_search",
            "openapi_law_list_articles",
        )

        selected = select_retrieval_tools(
            "메트포르민 복용법과 주요 부작용",
            tools,
            limit=3,
        )

        self.assertEqual(
            [tool["function"]["name"] for tool in selected],
            ["adr_retrieve_drug_info"],
        )

    def test_unknown_live_tools_have_bounded_fallback(self) -> None:
        tools = _tools("new_tool_one", "new_tool_two", "new_tool_three")

        selected = select_retrieval_tools(
            "특수한 외부 근거를 찾아주세요",
            tools,
            limit=2,
        )

        self.assertEqual(len(selected), 2)


if __name__ == "__main__":
    unittest.main()
