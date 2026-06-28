from __future__ import annotations

from typing import Any, Awaitable, Callable, TypeVar

from ..apie import Apie, AsyncApie

T = TypeVar("T")


def with_vercel_ai_generation(apie: Apie, input: dict[str, Any], fn: Callable[[], T]) -> T:
    payload_summary = {
        "provider": input.get("provider", "vercel-ai"),
        "model": input["model"],
        "prompt_hash": input.get("promptHash"),
        **(input.get("metadata") or {}),
    }
    return apie.with_llm_call(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepName": "vercel-ai.generateText",
            "payloadSummary": payload_summary,
        },
        fn,
    )


async def with_vercel_ai_generation_async(
    apie: AsyncApie,
    input: dict[str, Any],
    fn: Callable[[], Awaitable[T]],
) -> T:
    payload_summary = {
        "provider": input.get("provider", "vercel-ai"),
        "model": input["model"],
        "prompt_hash": input.get("promptHash"),
        **(input.get("metadata") or {}),
    }
    return await apie.with_llm_call(
        {
            "runId": input["runId"],
            "sessionId": input.get("sessionId"),
            "stepName": "vercel-ai.generateText",
            "payloadSummary": payload_summary,
        },
        fn,
    )
