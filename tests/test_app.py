import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import app as submission_app


MOCK_COMPLETION = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "created": 1,
    "model": "Lunit/L2-preview",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "mocked L2 answer"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
}


class SubmissionAppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(submission_app.app)

    def tearDown(self):
        submission_app.app.dependency_overrides.clear()

    def test_models_shape(self):
        response = self.client.get("/v1/models")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["object"], "list")
        self.assertEqual(body["data"][0]["id"], "daintlab-a")
        self.assertEqual(body["data"][0]["object"], "model")

    def test_messages_are_validated(self):
        response = self.client.post(
            "/v1/chat/completions",
            json={"model": "daintlab-a", "messages": []},
        )
        self.assertEqual(response.status_code, 422)

    def test_multi_turn_history_is_forwarded_in_order_and_output_is_from_l2(self):
        messages = [
            {"role": "system", "content": "Be concise."},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Follow-up question"},
        ]
        mock_client = AsyncMock()
        mock_client.create_chat_completion.return_value = MOCK_COMPLETION
        with patch.object(submission_app, "get_l2_client", return_value=mock_client):
            response = self.client.post(
                "/v1/chat/completions",
                json={"model": "daintlab-a", "messages": messages},
            )
        self.assertEqual(response.status_code, 200)
        mock_client.create_chat_completion.assert_awaited_once_with(messages)
        body = response.json()
        self.assertEqual(body["choices"][0]["message"]["content"], "mocked L2 answer")
        self.assertEqual(body["model"], "daintlab-a")
        self.assertEqual(body["usage"], MOCK_COMPLETION["usage"])

    def test_unsupported_features_fail_explicitly(self):
        response = self.client.post(
            "/v1/chat/completions",
            json={
                "model": "daintlab-a",
                "messages": [{"role": "user", "content": "hi"}],
                "stream": True,
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_missing_key_is_clear(self):
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post(
                "/v1/chat/completions",
                json={
                    "model": "daintlab-a",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "LUNIT_FM_API_KEY is required")


if __name__ == "__main__":
    unittest.main()
