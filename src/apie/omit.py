from __future__ import annotations

from typing import Any


def omit_none(value: dict[str, Any]) -> dict[str, Any]:
    return {key: entry for key, entry in value.items() if entry is not None}
