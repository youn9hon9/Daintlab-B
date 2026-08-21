import unittest

from src.conversation import ConversationService


class RecordingClient:
    def __init__(self):
        self.messages = None

    async def create_chat_completion(self, messages):
        self.messages = messages
        return {"choices": [{"message": {"role": "assistant", "content": "L2 answer"}}]}


class ConversationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_forwards_ordered_history_and_normalizes_response(self):
        history = [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "follow-up"},
        ]
        client = RecordingClient()
        result = await ConversationService(client).complete(history)
        self.assertIs(client.messages, history)
        self.assertEqual(result["model"], "daintlab-a")
        self.assertEqual(result["choices"][0]["message"]["content"], "L2 answer")


if __name__ == "__main__":
    unittest.main()
