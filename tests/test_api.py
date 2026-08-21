from __future__ import annotations

import asyncio
import unittest

from starlette.testclient import TestClient

from src.api import create_app
from src.errors import UpstreamError
from tests.helpers import make_settings


class FakeDriver:
    def __init__(self, answer: str = "테스트 답변") -> None:
        self.answer = answer
        self.histories = []
        self.closed = False

    async def generate(self, history):
        self.histories.append(history)
        return self.answer

    async def aclose(self) -> None:
        self.closed = True


class FailingDriver(FakeDriver):
    async def generate(self, history):
        raise UpstreamError("upstream unavailable")


class SlowDriver(FakeDriver):
    async def generate(self, history):
        await asyncio.sleep(0.1)
        return self.answer


class APITest(unittest.TestCase):
    def test_models_contract(self) -> None:
        app = create_app(driver=FakeDriver(), settings=make_settings())
        with TestClient(app) as client:
            response = client.get("/v1/models")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["object"], "list")
        self.assertEqual(
            response.json()["data"][0]["id"], "lunit-hackathon-driver"
        )

    def test_chat_contract_and_full_history_forwarding(self) -> None:
        driver = FakeDriver("문맥을 반영한 답변")
        app = create_app(driver=driver, settings=make_settings())
        payload = {
            "model": "lunit-hackathon-driver",
            "messages": [
                {"role": "user", "content": "만성 신장질환이 있어요."},
                {"role": "assistant", "content": "어떤 점이 궁금하신가요?"},
                {"role": "user", "content": "당뇨도 있으면 달라져요?"},
            ],
        }

        with TestClient(app) as client:
            response = client.post("/v1/chat/completions", json=payload)

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["object"], "chat.completion")
        self.assertEqual(body["choices"][0]["message"]["role"], "assistant")
        self.assertEqual(
            body["choices"][0]["message"]["content"], "문맥을 반영한 답변"
        )
        self.assertEqual(len(driver.histories[0]), 3)
        self.assertEqual(driver.histories[0][-1].content, "당뇨도 있으면 달라져요?")

    def test_empty_messages_is_rejected(self) -> None:
        app = create_app(driver=FakeDriver(), settings=make_settings())
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={"model": "lunit-hackathon-driver", "messages": []},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "empty_messages")

    def test_streaming_is_rejected_explicitly(self) -> None:
        app = create_app(driver=FakeDriver(), settings=make_settings())
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "lunit-hackathon-driver",
                    "messages": [{"role": "user", "content": "질문"}],
                    "stream": True,
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"], "stream_not_supported"
        )

    def test_upstream_error_does_not_crash_service(self) -> None:
        app = create_app(driver=FailingDriver(), settings=make_settings())
        with TestClient(app) as client:
            failed = client.post(
                "/v1/chat/completions",
                json={
                    "model": "lunit-hackathon-driver",
                    "messages": [{"role": "user", "content": "질문"}],
                },
            )
            healthy = client.get("/v1/models")

        self.assertEqual(failed.status_code, 502)
        self.assertEqual(healthy.status_code, 200)

    def test_request_deadline_returns_504(self) -> None:
        settings = make_settings(request_timeout_seconds=0.01)
        app = create_app(driver=SlowDriver(), settings=settings)
        with TestClient(app) as client:
            response = client.post(
                "/v1/chat/completions",
                json={
                    "model": "lunit-hackathon-driver",
                    "messages": [{"role": "user", "content": "질문"}],
                },
            )
            healthy = client.get("/v1/models")

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["error"]["code"], "request_timeout")
        self.assertEqual(healthy.status_code, 200)


if __name__ == "__main__":
    unittest.main()
