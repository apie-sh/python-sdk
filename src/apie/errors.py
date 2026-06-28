from __future__ import annotations

from typing import Any, Optional


class ApieError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status: int,
        body: Any = None,
        request_id: Optional[str] = None,
        retry_after_ms: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.body = body
        self.request_id = request_id
        self.retry_after_ms = retry_after_ms
