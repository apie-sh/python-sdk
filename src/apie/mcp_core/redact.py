from __future__ import annotations

from typing import Any

DEFAULT_REDACT_KEYS = [
    "token",
    "password",
    "secret",
    "api_key",
    "apiKey",
    "authorization",
    "credential",
]


def _should_redact_key(key: str, redact_keys: list[str]) -> bool:
    lower = key.lower()
    return any(candidate.lower() in lower for candidate in redact_keys)


def redact_value(value: Any, redact_keys: list[str]) -> Any:
    if value is None:
        return value
    if isinstance(value, list):
        return [redact_value(item, redact_keys) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, nested in value.items():
            result[key] = (
                "[REDACTED]"
                if _should_redact_key(key, redact_keys)
                else redact_value(nested, redact_keys)
            )
        return result
    return value


def summarize_args(
    args: dict[str, Any] | None,
    redact_keys: list[str] | None = None,
) -> dict[str, Any]:
    keys = redact_keys if redact_keys else DEFAULT_REDACT_KEYS
    if not args:
        return {}
    redacted = redact_value(args, keys)
    return redacted if isinstance(redacted, dict) else {}
