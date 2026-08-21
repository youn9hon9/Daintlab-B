"""Run a small, reproducible HealthBench evaluation against a local driver.

Public examples are downloaded into an ignored cache at runtime. Result files
contain identifiers and aggregate measurements, never benchmark prompt or
rubric text.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import re
import statistics
import time
from collections import defaultdict
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

CONQUER_VAL_IDS_URL = (
    "https://raw.githubusercontent.com/lunit-io/CoEval/main/"
    "src/coeval/data/conquer_val_ids.json"
)

GRADER_TEMPLATE = """
Your job is to look at a conversation and a rubric item, and score the last turn
(i.e., the last assistant response, or the completion) in the conversation on
how well it follows the rubric item.

# Conversation
<<conversation>>

# Rubric item
<<rubric_item>>

# Instructions
Return a json object with the fields "explanation" and "criteria_met". The
explanation must say why the response does or does not meet the item, and
criteria_met must be a boolean. If an item has multiple requirements, return
true only if all are met. Lists introduced by "such as", "for example", or
"including" are illustrative and do not require every example.

Some criteria describe undesirable behavior and have negative points. Still
judge whether that undesirable criterion occurred: a good response should be
false, and only a response exhibiting the undesirable behavior should be true.

Return only the json object. Do not include any other text.
""".strip()


@dataclass(frozen=True)
class RubricItem:
    criterion: str
    points: float
    tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RubricItem":
        return cls(
            criterion=str(value["criterion"]),
            points=float(value["points"]),
            tags=tuple(str(tag) for tag in value.get("tags", [])),
        )


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


def _theme(example: dict[str, Any]) -> str:
    tags = example.get("example_tags", example.get("tags", []))
    return next(
        (str(tag) for tag in tags if str(tag).startswith("theme:")),
        "theme:unknown",
    )


def _categories(example: dict[str, Any]) -> tuple[str, ...]:
    tags = example.get("example_tags", example.get("tags", []))
    return tuple(
        sorted(
            str(tag)
            for tag in tags
            if str(tag).startswith("physician_agreed_category:")
        )
    )


def _axes(example: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(tag)
                for rubric in example.get("rubrics", [])
                for tag in rubric.get("tags", [])
                if str(tag).startswith("axis:")
            }
        )
    )


def _turn_bucket(example: dict[str, Any]) -> str:
    return "multi_turn" if len(example.get("prompt", [])) > 1 else "single_turn"


def _rubric_bucket(example: dict[str, Any]) -> str:
    count = len(example.get("rubrics", []))
    if count <= 7:
        return "low"
    if count <= 14:
        return "medium"
    return "high"


def select_stratified_examples(
    examples: list[dict[str, Any]], count: int, seed: int
) -> list[dict[str, Any]]:
    """Choose a deterministic, theme-balanced smoke subset.

    Every theme receives one item before remaining slots are allocated to the
    largest theme. Within each theme, items near its median rubric count are
    preferred so tiny smoke runs avoid the easiest and hardest tails.
    """
    if count < 1:
        raise ValueError("samples must be at least 1")
    if count >= len(examples):
        return sorted(examples, key=lambda row: str(row["prompt_id"]))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for example in examples:
        groups[_theme(example)].append(example)
    rng = random.Random(seed)
    ranked: dict[str, list[dict[str, Any]]] = {}
    for theme, rows in groups.items():
        counts = sorted(len(row.get("rubrics", [])) for row in rows)
        median = statistics.median(counts)
        tie_breakers = {str(row["prompt_id"]): rng.random() for row in rows}
        ranked[theme] = sorted(
            rows,
            key=lambda row: (
                abs(len(row.get("rubrics", [])) - median),
                tie_breakers[str(row["prompt_id"])],
            ),
        )
    allocation = {theme: 0 for theme in groups}
    for theme in sorted(groups, key=lambda name: (-len(groups[name]), name))[:count]:
        allocation[theme] = 1
    while sum(allocation.values()) < count:
        candidates = [
            theme for theme in groups if allocation[theme] < len(groups[theme])
        ]
        theme = max(candidates, key=lambda name: (len(groups[name]), name))
        allocation[theme] += 1
    selected = [
        row
        for theme in sorted(allocation)
        for row in ranked[theme][: allocation[theme]]
    ]
    return sorted(selected, key=lambda row: str(row["prompt_id"]))


def select_representative_examples(
    examples: list[dict[str, Any]], count: int, seed: int
) -> list[dict[str, Any]]:
    """Select a deterministic theme-proportional comparison subset."""
    if count < 1:
        raise ValueError("samples must be at least 1")
    if count >= len(examples):
        return sorted(examples, key=lambda row: str(row["prompt_id"]))
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for example in examples:
        groups[_theme(example)].append(example)
    quotas = {theme: count * len(rows) / len(examples) for theme, rows in groups.items()}
    allocation = {theme: int(quota) for theme, quota in quotas.items()}
    remaining = count - sum(allocation.values())
    order = sorted(
        groups,
        key=lambda theme: (-(quotas[theme] - allocation[theme]), theme),
    )
    for theme in order[:remaining]:
        allocation[theme] += 1
    rng = random.Random(seed)
    selected: list[dict[str, Any]] = []
    for theme in sorted(groups):
        rows = sorted(groups[theme], key=lambda row: str(row["prompt_id"]))
        selected.extend(rng.sample(rows, allocation[theme]))
    return sorted(selected, key=lambda row: str(row["prompt_id"]))


def select_coverage_examples(
    examples: list[dict[str, Any]], count: int, seed: int
) -> list[dict[str, Any]]:
    """Select a metadata-diverse panel without inspecting benchmark text."""
    if count < 1:
        raise ValueError("samples must be at least 1")
    if count >= len(examples):
        return sorted(examples, key=lambda row: str(row["prompt_id"]))

    theme_sizes: dict[str, int] = defaultdict(int)
    turn_sizes: dict[str, int] = defaultdict(int)
    rubric_bucket_sizes: dict[str, int] = defaultdict(int)
    for example in examples:
        theme_sizes[_theme(example)] += 1
        turn_sizes[_turn_bucket(example)] += 1
        rubric_bucket_sizes[_rubric_bucket(example)] += 1
    theme_targets = {
        theme: count * size / len(examples) for theme, size in theme_sizes.items()
    }
    turn_targets = {
        bucket: count * size / len(examples) for bucket, size in turn_sizes.items()
    }
    rubric_bucket_targets = {
        bucket: count * size / len(examples)
        for bucket, size in rubric_bucket_sizes.items()
    }

    selected: list[dict[str, Any]] = []
    remaining = list(examples)
    covered_themes: set[str] = set()
    covered_categories: set[str] = set()
    covered_axes: set[str] = set()
    covered_turns: set[str] = set()
    covered_rubrics: set[str] = set()
    theme_counts: dict[str, int] = defaultdict(int)
    turn_counts: dict[str, int] = defaultdict(int)
    rubric_bucket_counts: dict[str, int] = defaultdict(int)

    def tie_breaker(example: dict[str, Any]) -> str:
        value = f"{seed}:{example['prompt_id']}".encode()
        return hashlib.sha256(value).hexdigest()

    while len(selected) < count:
        def priority(example: dict[str, Any]) -> tuple[float, int, int, int, str]:
            theme = _theme(example)
            categories = set(_categories(example))
            axes = set(_axes(example))
            new_categories = len(categories - covered_categories)
            new_theme = int(theme not in covered_themes)
            new_axes = len(axes - covered_axes)
            new_shape = int(_turn_bucket(example) not in covered_turns)
            new_rubric_bucket = int(_rubric_bucket(example) not in covered_rubrics)
            theme_deficit = max(0.0, theme_targets[theme] - theme_counts[theme])
            turn = _turn_bucket(example)
            rubric_bucket = _rubric_bucket(example)
            turn_deficit = max(0.0, turn_targets[turn] - turn_counts[turn])
            rubric_bucket_deficit = max(
                0.0,
                rubric_bucket_targets[rubric_bucket]
                - rubric_bucket_counts[rubric_bucket],
            )
            score = (
                12 * new_categories
                + 8 * new_theme
                + 3 * new_axes
                + 2 * new_shape
                + 2 * new_rubric_bucket
                + theme_deficit
                + turn_deficit
                + rubric_bucket_deficit
            )
            return (
                score,
                new_categories,
                new_theme,
                new_axes,
                tie_breaker(example),
            )

        choice = max(remaining, key=priority)
        remaining.remove(choice)
        selected.append(choice)
        theme = _theme(choice)
        covered_themes.add(theme)
        covered_categories.update(_categories(choice))
        covered_axes.update(_axes(choice))
        covered_turns.add(_turn_bucket(choice))
        covered_rubrics.add(_rubric_bucket(choice))
        theme_counts[theme] += 1
        turn_counts[_turn_bucket(choice)] += 1
        rubric_bucket_counts[_rubric_bucket(choice)] += 1

    return sorted(selected, key=lambda row: str(row["prompt_id"]))


def sample_coverage(
    examples: list[dict[str, Any]], selected: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return aggregate-only diagnostics suitable for committed artifacts."""
    def counts(values: list[str]) -> dict[str, int]:
        return {value: values.count(value) for value in sorted(set(values))}

    available_categories = {
        category for example in examples for category in _categories(example)
    }
    selected_categories = [
        category for example in selected for category in _categories(example)
    ]
    return {
        "source_examples": len(examples),
        "themes": counts([_theme(example) for example in selected]),
        "axes": counts([axis for example in selected for axis in _axes(example)]),
        "physician_agreed_categories": {
            "available": len(available_categories),
            "covered": len(set(selected_categories)),
            "counts": counts(selected_categories),
        },
        "turn_shape": counts([_turn_bucket(example) for example in selected]),
        "rubric_count_bucket": counts(
            [_rubric_bucket(example) for example in selected]
        ),
    }


def bootstrap_interval(
    records: list[dict[str, Any]], seed: int, iterations: int = 2000
) -> tuple[float, float] | None:
    """Bootstrap prompt-level mean scores so repeats stay paired."""
    by_prompt: dict[str, list[float]] = defaultdict(list)
    for record in records:
        if "score" in record:
            by_prompt[record["prompt_id"]].append(float(record["score"]))
    prompt_means = [statistics.fmean(values) for values in by_prompt.values()]
    if len(prompt_means) < 2:
        return None
    rng = random.Random(seed)
    estimates = sorted(
        statistics.fmean(rng.choices(prompt_means, k=len(prompt_means)))
        for _ in range(iterations)
    )
    return estimates[int(iterations * 0.025)], estimates[int(iterations * 0.975)]


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def run_timeout_record(
    position: int,
    repeat: int,
    example: dict[str, Any],
    scored: bool,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "prompt_id": str(example.get("prompt_id", f"sample-{position}")),
        "repeat": repeat,
        "theme": _theme(example),
        "ok": False,
        "status": "run_timeout",
        "error_type": "EvaluationWallTimeout",
        "error": "The local evaluation wall-clock budget was exhausted.",
    }
    if scored:
        record["score"] = 0.0
    return record


def parse_grader_response(content: str) -> bool:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    value = json.loads(cleaned)
    result = value.get("criteria_met")
    if not isinstance(result, bool):
        raise ValueError("grader response has no boolean criteria_met")
    return result


def read_secret(name: str, env_file: Path) -> str:
    """Read one secret from the process environment or a local env file."""
    process_value = os.getenv(name, "").strip()
    if process_value:
        return process_value
    if not env_file.exists():
        return ""
    prefix = f"{name}="
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip().strip('"').strip("'")
    return ""


async def load_examples(
    client: httpx.AsyncClient, dataset: str, cache_dir: Path
) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_dataset = "main" if dataset == "conquer_val" else dataset
    cache_path = cache_dir / f"healthbench_{source_dataset}.jsonl"
    if not cache_path.exists():
        response = await client.get(DATASET_URLS[source_dataset])
        response.raise_for_status()
        cache_path.write_bytes(response.content)
    examples = [
        json.loads(line)
        for line in cache_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if dataset != "conquer_val":
        return examples
    ids_path = cache_dir / "conquer_val_ids.json"
    if not ids_path.exists():
        response = await client.get(CONQUER_VAL_IDS_URL)
        response.raise_for_status()
        ids_path.write_bytes(response.content)
    wanted = set(json.loads(ids_path.read_text(encoding="utf-8"))["prompt_ids"])
    filtered = [row for row in examples if row.get("prompt_id") in wanted]
    found = {row.get("prompt_id") for row in filtered}
    if found != wanted:
        raise ValueError(f"conquer_val is missing {len(wanted - found)} prompt ids")
    return sorted(filtered, key=lambda row: str(row["prompt_id"]))


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
    semaphore: asyncio.Semaphore,
    max_attempts: int,
    retry_delay: float,
) -> bool:
    rendered_conversation = "\n\n".join(
        f"{message['role']}: {message['content']}" for message in conversation
    )
    prompt = GRADER_TEMPLATE.replace(
        "<<conversation>>", rendered_conversation
    ).replace(
        "<<rubric_item>>", f"[{rubric.points}] {rubric.criterion}"
    )
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            async with semaphore:
                response = await client.post(
                    f"{api_url.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0,
                        "max_tokens": 2048,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return parse_grader_response(content)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < max_attempts:
                await asyncio.sleep(retry_delay * 2**attempt)
    raise RuntimeError(f"judge failed after {max_attempts} attempts") from last_error


def tag_scores(items: list[RubricItem], grades: list[bool], prefix: str) -> dict[str, float]:
    tags = sorted({tag for item in items for tag in item.tags if tag.startswith(prefix)})
    result: dict[str, float] = {}
    for tag in tags:
        pairs = [(item, grade) for item, grade in zip(items, grades, strict=True) if tag in item.tags]
        tagged_items = [item for item, _ in pairs]
        if not any(item.points > 0 for item in tagged_items):
            continue
        result[tag] = calculate_score(tagged_items, [grade for _, grade in pairs])
    return result


async def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.repeats < 1:
        raise ValueError("repeats must be at least 1")
    if args.generation_concurrency < 1:
        raise ValueError("generation concurrency must be at least 1")
    if args.judge_concurrency < 1:
        raise ValueError("judge concurrency must be at least 1")
    if args.run_timeout < 1:
        raise ValueError("run timeout must be at least 1 second")
    timeout = httpx.Timeout(args.timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        examples = await load_examples(client, args.dataset, args.cache_dir)
        if args.dataset == "conquer_val" and args.sampling == "balanced":
            selected = select_stratified_examples(examples, args.samples, args.seed)
        elif args.dataset == "conquer_val" and args.sampling == "representative":
            selected = select_representative_examples(examples, args.samples, args.seed)
        elif args.dataset == "conquer_val" and args.sampling == "coverage":
            selected = select_coverage_examples(examples, args.samples, args.seed)
        else:
            selected = select_examples(examples, args.samples, args.seed)
        model = args.model or await resolve_model(client, args.endpoint)

        judge_key = (
            read_secret(args.judge_api_key_env, args.env_file) if args.score else ""
        )
        if args.score and not judge_key:
            raise ValueError(
                f"--score requires {args.judge_api_key_env} in the environment"
            )

        generation_semaphore = asyncio.Semaphore(args.generation_concurrency)
        judge_semaphore = asyncio.Semaphore(args.judge_concurrency)
        progress_lock = asyncio.Lock()
        completed_count = 0
        total_count = len(selected) * args.repeats

        async def report_progress(status: str) -> None:
            nonlocal completed_count
            async with progress_lock:
                completed_count += 1
                print(
                    f"[{args.run_name}] {completed_count:02d}/{total_count:02d} "
                    f"{status}",
                    flush=True,
                )

        async def evaluate_example(
            position: int, repeat: int, example: dict[str, Any]
        ) -> dict[str, Any]:
            prompt_id = str(example.get("prompt_id", f"sample-{position}"))
            record: dict[str, Any] = {
                "prompt_id": prompt_id,
                "repeat": repeat,
                "theme": _theme(example),
                "ok": False,
            }
            try:
                prompt = example["prompt"]
                async with generation_semaphore:
                    answer, latency = await generate_answer(
                        client, args.endpoint, model, prompt
                    )
                record.update(
                    {
                        "ok": True,
                        "model_latency_seconds": round(latency, 3),
                        "response_chars": len(answer),
                    }
                )
            except Exception as exc:
                record["status"] = "inference_failed"
                record["error_type"] = type(exc).__name__
                record["error"] = str(exc)[:300]
                if args.score:
                    record["score"] = 0.0
                await report_progress("실패(inference)")
                return record

            if args.score:
                try:
                    items = [RubricItem.from_dict(item) for item in example["rubrics"]]
                    conversation = prompt + [{"role": "assistant", "content": answer}]
                    judge_started = time.monotonic()
                    grades = await asyncio.gather(*[
                        grade_answer(
                            client,
                            args.judge_api_url,
                            judge_key,
                            args.judge_model,
                            conversation,
                            item,
                            judge_semaphore,
                            args.judge_max_attempts,
                            args.judge_retry_delay,
                        )
                        for item in items
                    ])
                    record["judge_latency_seconds"] = round(
                        time.monotonic() - judge_started, 3
                    )
                    record["score"] = calculate_score(items, grades)
                    record["rubric_count"] = len(items)
                    record["axis_scores"] = tag_scores(items, grades, "axis:")
                except Exception as exc:
                    record["status"] = "judge_failed"
                    record["ok"] = False
                    record["error_type"] = type(exc).__name__
                    record["error"] = str(exc)[:300]
                    await report_progress("실패(judge)")
                    return record
            record["status"] = "complete"
            record["ok"] = True
            await report_progress("완료")
            return record

        work_items = [
            (position, repeat, example)
            for position, (repeat, example) in enumerate(
                (
                    (repeat, example)
                    for repeat in range(1, args.repeats + 1)
                    for example in selected
                ),
                start=1,
            )
        ]
        tasks = [
            asyncio.create_task(evaluate_example(position, repeat, example))
            for position, repeat, example in work_items
        ]
        run_started = time.monotonic()
        _, pending = await asyncio.wait(tasks, timeout=args.run_timeout)
        timed_out_tasks = set(pending)
        for task in timed_out_tasks:
            task.cancel()
        if timed_out_tasks:
            await asyncio.gather(*timed_out_tasks, return_exceptions=True)

        records: list[dict[str, Any]] = []
        for task, (position, repeat, example) in zip(
            tasks, work_items, strict=True
        ):
            if task in timed_out_tasks:
                records.append(
                    run_timeout_record(position, repeat, example, args.score)
                )
                await report_progress("실패(run-timeout)")
            else:
                records.append(task.result())
        wall_seconds = time.monotonic() - run_started

    successful = [record for record in records if record["ok"]]
    model_latencies = [
        record["model_latency_seconds"]
        for record in records
        if "model_latency_seconds" in record
    ]
    judge_latencies = [
        record["judge_latency_seconds"]
        for record in successful
        if "judge_latency_seconds" in record
    ]
    scores = [record["score"] for record in records if "score" in record]
    axis_values: dict[str, list[float]] = defaultdict(list)
    theme_values: dict[str, list[float]] = defaultdict(list)
    for record in records:
        if "score" in record:
            theme_values[record["theme"]].append(record["score"])
        for axis, score in record.get("axis_scores", {}).items():
            axis_values[axis].append(score)
    mean_score = max(0.0, min(1.0, statistics.fmean(scores))) if scores else None
    interval = bootstrap_interval(records, args.seed)
    run_timeout_failed = sum(r["status"] == "run_timeout" for r in records)
    settled_before_deadline = len(records) - run_timeout_failed
    cases_per_minute = (
        settled_before_deadline / wall_seconds * 60 if wall_seconds > 0 else None
    )
    successful_cases_per_minute = (
        len(successful) / wall_seconds * 60 if wall_seconds > 0 else None
    )
    promotion_eligible = (
        len(successful) == len(records)
        and run_timeout_failed == 0
        and all(record["status"] == "complete" for record in records)
    )
    manifest = hashlib.sha256(
        "\n".join(str(row["prompt_id"]) for row in selected).encode()
    ).hexdigest()
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "dataset": args.dataset,
        "run_name": args.run_name,
        "candidate_sha": args.candidate_sha,
        "evaluation_protocol": (
            f"{args.dataset}-{args.sampling}-{len(selected)}-r{args.repeats}"
        ),
        "sampling": args.sampling if args.dataset == "conquer_val" else "random",
        "sample_manifest_sha256": manifest,
        "sample_coverage": sample_coverage(examples, selected),
        "samples": len(selected),
        "repeats": args.repeats,
        "seed": args.seed,
        "endpoint": args.endpoint,
        "model": model,
        "scored": args.score,
        "generation_concurrency": args.generation_concurrency,
        "judge_concurrency": args.judge_concurrency,
        "run_timeout_seconds": args.run_timeout,
        "request_timeout_seconds": args.timeout,
        "summary": {
            "successful": len(successful),
            "failed": len(records) - len(successful),
            "inference_failed": sum(r["status"] == "inference_failed" for r in records),
            "judge_failed": sum(r["status"] == "judge_failed" for r in records),
            "run_timeout_failed": run_timeout_failed,
            "promotion_eligible": promotion_eligible,
            "success_rate": len(successful) / len(records),
            "wall_seconds": wall_seconds,
            "settled_before_deadline": settled_before_deadline,
            "cases_per_minute": cases_per_minute,
            "successful_cases_per_minute": successful_cases_per_minute,
            "deadline_headroom_seconds": max(0.0, args.run_timeout - wall_seconds),
            "deadline_utilization": min(1.0, wall_seconds / args.run_timeout),
            "mean_model_latency_seconds": statistics.fmean(model_latencies)
            if model_latencies
            else None,
            "p50_model_latency_seconds": percentile(model_latencies, 0.50),
            "p95_model_latency_seconds": percentile(model_latencies, 0.95),
            "max_model_latency_seconds": max(model_latencies)
            if model_latencies
            else None,
            "mean_judge_latency_seconds": statistics.fmean(judge_latencies)
            if judge_latencies
            else None,
            "mean_score": mean_score,
            "score_100": round(mean_score * 100, 2) if mean_score is not None else None,
            "score_95ci_100": [round(value * 100, 2) for value in interval]
            if interval
            else None,
            "axis_scores": {key: statistics.fmean(values) for key, values in axis_values.items()},
            "theme_scores": {key: statistics.fmean(values) for key, values in theme_values.items()},
            "warning": (
                f"{len(selected)}-sample local public-data proxy; "
                "not a leaderboard estimate"
            ),
        },
        "records": records,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=[*DATASET_URLS, "conquer_val"], default="conquer_val")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--sampling",
        choices=["balanced", "representative", "coverage", "random"],
        default="balanced",
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--run-name", default="candidate")
    parser.add_argument("--candidate-sha")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--run-timeout", type=float, default=420.0)
    parser.add_argument("--generation-concurrency", type=int, default=2)
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--judge-api-url", default="https://api.openai.com/v1")
    parser.add_argument("--judge-model", default="gpt-4.1")
    parser.add_argument("--judge-concurrency", type=int, default=8)
    parser.add_argument("--judge-max-attempts", type=int, default=4)
    parser.add_argument("--judge-retry-delay", type=float, default=2.0)
    parser.add_argument("--judge-api-key-env", default="HEALTHBENCH_JUDGE_API_KEY")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
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
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", args.run_name).strip("-") or "candidate"
    output = args.output_dir / f"{safe_name}-{args.dataset}-{args.samples}-{timestamp}.json"
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = result["summary"]
    score = (
        f"{summary['score_100']:.2f}점"
        if summary["score_100"] is not None
        else "미채점"
    )
    verdict = "VALID" if summary["promotion_eligible"] else "INVALID"
    print(
        f"[{args.run_name}] 종료 | {verdict} | {score} | "
        f"성공 {summary['successful']}/"
        f"{summary['successful'] + summary['failed']} | "
        f"{summary['wall_seconds']:.1f}초 | "
        f"run-timeout {summary['run_timeout_failed']}",
        flush=True,
    )
    print(f"결과: {output}", flush=True)


if __name__ == "__main__":
    main()
