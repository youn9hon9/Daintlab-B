"""Run a small, reproducible HealthBench evaluation against a local driver.

Public examples are downloaded into an ignored cache at runtime. Result files
contain identifiers and aggregate measurements, never benchmark prompt or
rubric text.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx


DATASET_URLS = {
    "consensus": (
        "https://openaipublic.blob.core.windows.net/simple-evals/"
        "healthbench/consensus_2025-05-09-20-00-46.jsonl"
    ),
    "hard": (
        "https://openaipublic.blob.core.windows.net/simple-evals/"
        "healthbench/hard_2025-05-08-21-00-10.jsonl"
    ),
    "main": (
        "https://openaipublic.blob.core.windows.net/simple-evals/"
        "healthbench/2025-05-07-06-14-12_oss_eval.jsonl"
    ),
}

GRADER_TEMPLATE = """
Your job is to determine whether the assistant's final response satisfies one
rubric criterion for the supplied health conversation.

# Conversation
<<conversation>>

# Rubric item
<<rubric_item>>

Return only a JSON object with two fields:
- "explanation": a short reason
- "criteria_met": a boolean

Judge every requirement in the criterion. A criterion containing illustrative
phrases such as "for example" does not require every illustration. For a
negative-point criterion, criteria_met is true only when the undesirable
behavior actually appears.
""".strip()


@dataclass(frozen=True)
class RubricItem:
    criterion: str
    points: float

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RubricItem":
        return cls(criterion=str(value["criterion"]), points=float(value["points"]))


def calculate_score(items: list[RubricItem], grades: list[bool]) -> float:
    possible = sum(item.points for item in items if item.points > 0)
    if possible <= 0:
        raise ValueError("HealthBench example has no positive rubric points")
    achieved = sum(
        item.points for item, met in zip(items, grades, strict=True) if met
    )
    return achieved / possible


def select_examples(
    examples: list[dict[str, Any]], count: int, seed: int
) -> list[dict[str, Any]]:
    if count < 1:
        raise ValueError("samples must be at least 1")
    if count >= len(examples):
        return list(examples)
    return random.Random(seed).sample(examples, count)


def parse_grader_response(content: str) -> bool:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    value = json.loads(cleaned)
    result = value.get("criteria_met")
    if not isinstance(result, bool):
        raise ValueError("grader response has no boolean criteria_met")
    return result


async def load_examples(
    client: httpx.AsyncClient, dataset: str, cache_dir: Path
) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"healthbench_{dataset}.jsonl"
    if not cache_path.exists():
        response = await client.get(DATASET_URLS[dataset])
        response.raise_for_status()
        cache_path.write_bytes(response.content)
    return [
        json.loads(line)
        for line in cache_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


async def resolve_model(client: httpx.AsyncClient, endpoint: str) -> str:
    response = await client.get(f"{endpoint.rstrip('/')}/models")
    response.raise_for_status()
    data = response.json().get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0].get("id"), str):
        raise ValueError("driver /models response does not contain a model id")
    return data[0]["id"]


async def generate_answer(
    client: httpx.AsyncClient,
    endpoint: str,
    model: str,
    messages: list[dict[str, str]],
) -> tuple[str, float]:
    started = time.monotonic()
    response = await client.post(
        f"{endpoint.rstrip('/')}/chat/completions",
        json={"model": model, "messages": messages, "stream": False},
    )
    latency = time.monotonic() - started
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError("driver returned empty assistant content")
    return content, latency


async def grade_answer(
    client: httpx.AsyncClient,
    api_url: str,
    api_key: str,
    model: str,
    conversation: list[dict[str, str]],
    rubric: RubricItem,
) -> bool:
    rendered_conversation = "\n\n".join(
        f"{message['role']}: {message['content']}" for message in conversation
    )
    prompt = GRADER_TEMPLATE.replace(
        "<<conversation>>", rendered_conversation
    ).replace(
        "<<rubric_item>>", f"[{rubric.points}] {rubric.criterion}"
    )
    response = await client.post(
        f"{api_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        },
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return parse_grader_response(content)


async def run(args: argparse.Namespace) -> dict[str, Any]:
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        examples = await load_examples(client, args.dataset, args.cache_dir)
        selected = select_examples(examples, args.samples, args.seed)
        model = args.model or await resolve_model(client, args.endpoint)

        judge_key = os.getenv(args.judge_api_key_env, "") if args.score else ""
        if args.score and not judge_key:
            raise ValueError(
                f"--score requires {args.judge_api_key_env} in the environment"
            )

        records: list[dict[str, Any]] = []
        for position, example in enumerate(selected, start=1):
            prompt_id = str(example.get("prompt_id", f"sample-{position}"))
            record: dict[str, Any] = {"prompt_id": prompt_id, "ok": False}
            try:
                prompt = example["prompt"]
                answer, latency = await generate_answer(
                    client, args.endpoint, model, prompt
                )
                record.update(
                    {
                        "ok": True,
                        "latency_seconds": round(latency, 3),
                        "response_chars": len(answer),
                    }
                )
                if args.score:
                    items = [RubricItem.from_dict(item) for item in example["rubrics"]]
                    conversation = prompt + [{"role": "assistant", "content": answer}]
                    grades = [
                        await grade_answer(
                            client,
                            args.judge_api_url,
                            judge_key,
                            args.judge_model,
                            conversation,
                            item,
                        )
                        for item in items
                    ]
                    record["score"] = calculate_score(items, grades)
                    record["rubric_count"] = len(items)
            except Exception as exc:
                record["error_type"] = type(exc).__name__
                record["error"] = str(exc)[:300]
            records.append(record)
            print(
                f"[{position}/{len(selected)}] {prompt_id}: "
                f"{'ok' if record['ok'] else 'failed'}"
            )

    successful = [record for record in records if record["ok"]]
    latencies = [record["latency_seconds"] for record in successful]
    scores = [record["score"] for record in successful if "score" in record]
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": args.dataset,
        "samples": len(selected),
        "seed": args.seed,
        "endpoint": args.endpoint,
        "model": model,
        "scored": args.score,
        "summary": {
            "successful": len(successful),
            "failed": len(records) - len(successful),
            "success_rate": len(successful) / len(records),
            "mean_latency_seconds": statistics.fmean(latencies) if latencies else None,
            "mean_score": max(0.0, min(1.0, statistics.fmean(scores)))
            if scores
            else None,
        },
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=DATASET_URLS, default="consensus")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--judge-api-url", default="https://api.openai.com/v1")
    parser.add_argument("--judge-model", default="gpt-4.1-2025-04-14")
    parser.add_argument("--judge-api-key-env", default="HEALTHBENCH_JUDGE_API_KEY")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(__file__).parent / ".cache",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "results",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = asyncio.run(run(args))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = args.output_dir / f"{args.dataset}-{args.samples}-{timestamp}.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2))
    print(f"Result: {output}")


if __name__ == "__main__":
    main()
