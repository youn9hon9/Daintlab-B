import unittest

from src.api_contract import (
    DRIVER_MODEL_ID,
    ContractError,
    model_catalog,
    normalize_completion,
    validate_request,
)


class ApiContractTests(unittest.TestCase):
    def test_model_catalog(self):
        self.assertEqual(model_catalog()["data"][0]["id"], DRIVER_MODEL_ID)

    def test_validation_returns_a_defensive_copy(self):
        source = {
            "model": DRIVER_MODEL_ID,
            "messages": [{"role": "user", "content": "hi"}],
        }
        messages = validate_request(source)
        messages[0]["content"] = "changed"
        self.assertEqual(source["messages"][0]["content"], "hi")

    def test_invalid_model_has_400_contract_error(self):
        with self.assertRaises(ContractError) as caught:
            validate_request(
                {
                    "model": "wrong",
                    "messages": [{"role": "user", "content": "hi"}],
                }
            )
        self.assertEqual(caught.exception.status_code, 400)

    def test_completion_normalization_preserves_usage(self):
        upstream = {
            "choices": [{"message": {"role": "assistant", "content": "answer"}}],
            "usage": {"total_tokens": 4},
        }
        result = normalize_completion(upstream)
        self.assertEqual(result["model"], DRIVER_MODEL_ID)
        self.assertEqual(result["usage"], upstream["usage"])


if __name__ == "__main__":
    unittest.main()
