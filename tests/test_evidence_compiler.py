from __future__ import annotations

import unittest

from src.evidence_compiler import compile_evidence
from tests.helpers import FakeGatewayFactory, make_settings


class CompileEvidenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_direct_route_returns_none_without_calling_gateway(self) -> None:
        gateways = FakeGatewayFactory()

        result = await compile_evidence(
            "direct", "query", make_settings(), gateway_factory=gateways
        )

        self.assertIsNone(result)
        self.assertEqual(gateways.instances, [])

    async def test_empty_query_returns_none(self) -> None:
        gateways = FakeGatewayFactory()

        result = await compile_evidence(
            "drug_dose", "   ", make_settings(), gateway_factory=gateways
        )

        self.assertIsNone(result)
        self.assertEqual(gateways.instances, [])

    async def test_drug_dose_route_calls_the_mfds_tool(self) -> None:
        gateways = FakeGatewayFactory()

        result = await compile_evidence(
            "drug_dose", "메트포르민 용량", make_settings(), gateway_factory=gateways
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status, "sufficient")
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].citation, "[1]")
        self.assertEqual(
            gateways.instances[0].calls[0][0],
            "openapi_mfds_get_drug_indication",
        )
        self.assertEqual(
            gateways.instances[0].calls[0][1],
            {"product_name": "메트포르민 용량"},
        )

    async def test_medical_evidence_route_calls_guideline_tool_with_corpus_tag(
        self,
    ) -> None:
        gateways = FakeGatewayFactory()

        result = await compile_evidence(
            "medical_evidence",
            "고혈압 진료지침",
            make_settings(),
            gateway_factory=gateways,
        )

        self.assertIsNotNone(result)
        called_name, called_args = gateways.instances[0].calls[0]
        self.assertEqual(called_name, "index_get_relevant_nodes")
        self.assertEqual(called_args["query"], "고혈압 진료지침")
        self.assertEqual(called_args["corpus_tag"], "guideline")

    async def test_policy_legal_route_chains_search_then_get_article(self) -> None:
        gateways = FakeGatewayFactory()

        result = await compile_evidence(
            "policy_legal", "의료법 조문", make_settings(), gateway_factory=gateways
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(len(result.items), 1)
        called_names = [call[0] for call in gateways.instances[0].calls]
        self.assertEqual(
            called_names, ["openapi_law_search", "openapi_law_get_article"]
        )
        self.assertEqual(
            gateways.instances[0].calls[1][1], {"mst": "mst-test-1"}
        )

    async def test_gateway_exception_returns_none(self) -> None:
        class FailingGatewayFactory:
            def __call__(self, settings):
                raise ConnectionError("unreachable")

        result = await compile_evidence(
            "drug_dose",
            "메트포르민 용량",
            make_settings(),
            gateway_factory=FailingGatewayFactory(),
        )

        self.assertIsNone(result)

    async def test_missing_tool_returns_none(self) -> None:
        class EmptyGateway:
            def __init__(self, settings) -> None:
                self.settings = settings

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback) -> None:
                return None

            async def list_openai_tools(self):
                return []

            async def call_tool(self, name, arguments):
                raise AssertionError("should not be called")

        result = await compile_evidence(
            "drug_dose", "메트포르민 용량", make_settings(), gateway_factory=EmptyGateway
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
