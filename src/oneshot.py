from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from src.context import build_oneshot_input
from src.errors import UpstreamProtocolError
from src.prompts import ONESHOT_SYSTEM_PROMPT
from src.schemas import InputMessage


logger = logging.getLogger(__name__)


async def generate_oneshot(
    settings: Any,
    model_client: Any,
    history: list[InputMessage],
) -> str:
    latest_question, context = build_oneshot_input(history)
    user_payload = json.dumps(
        {"current_question": latest_question, "relevant_context": context},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    messages = [
        {"role": "system", "content": ONESHOT_SYSTEM_PROMPT},
        {"role": "user", "content": user_payload},
    ]

    loop = asyncio.get_running_loop()
    started = loop.time()
    assistant = await model_client.chat(
        messages,
        phase="initial",
        max_tokens=settings.initial_max_tokens,
        max_retries=0,
    )
    elapsed_ms = round((loop.time() - started) * 1_000)
    content = assistant.get("content")
    reasoning = assistant.get("reasoning_content")
    finish_reason = assistant.get("_finish_reason")
    output_chars = len(content) if isinstance(content, str) else 0
    reasoning_chars = len(reasoning) if isinstance(reasoning, str) else 0
    logger.info(
        "oneshot_complete input_chars=%s context_chars=%s output_chars=%s "
        "reasoning_chars=%s finish_reason=%s l2_latency_ms=%s",
        len(user_payload),
        len(context),
        output_chars,
        reasoning_chars,
        finish_reason or "unknown",
        elapsed_ms,
    )
    if not isinstance(content, str) or not content.strip():
        logger.warning(
            "oneshot_empty_content finish_reason=%s reasoning_chars=%s",
            finish_reason or "unknown",
            reasoning_chars,
        )
        raise UpstreamProtocolError("Lunit FM returned empty message.content")
    return content.strip()
