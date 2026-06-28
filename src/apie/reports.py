from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from .http import AsyncHttpClient, HttpClient
from .types import BoundaryReportCreateInput, BoundaryReportResponse


def create_report(
    http: HttpClient,
    agent_id: str,
    input: Optional[BoundaryReportCreateInput] = None,
) -> BoundaryReportResponse:
    payload = {
        "title": input.title if input else None,
        "report_type": input.report_type if input else None,
        "window": input.window if input else None,
        "time_window": input.time_window if input else None,
        "filters": (
            {"environments": input.environments}
            if input and input.environments
            else {"agent_version_id": input.agent_version_id}
            if input and input.agent_version_id
            else None
        ),
        "sections": input.sections if input else None,
    }
    body = http.post(f"/v1/agents/{agent_id}/boundary-reports", payload)
    return BoundaryReportResponse(
        report_id=str(body.get("report_id", "")),
        status=str(body.get("status", "")),
        web_url=str(body.get("web_url", "")),
    )


def get_report(http: HttpClient, report_id: str) -> dict[str, Any]:
    return http.get(f"/v1/boundary-reports/{report_id}")


def wait_until_report_ready(
    http: HttpClient,
    report_id: str,
    *,
    timeout_ms: int = 30_000,
    poll_interval_ms: int = 1_000,
) -> dict[str, Any]:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        report = get_report(http, report_id)
        if report.get("status") in {"generated", "shared"}:
            return report
        time.sleep(poll_interval_ms / 1000)
    raise TimeoutError(f"Report {report_id} was not ready within {timeout_ms}ms")


async def async_create_report(
    http: AsyncHttpClient,
    agent_id: str,
    input: Optional[BoundaryReportCreateInput] = None,
) -> BoundaryReportResponse:
    payload = {
        "title": input.title if input else None,
        "report_type": input.report_type if input else None,
        "window": input.window if input else None,
        "time_window": input.time_window if input else None,
        "filters": (
            {"environments": input.environments}
            if input and input.environments
            else {"agent_version_id": input.agent_version_id}
            if input and input.agent_version_id
            else None
        ),
        "sections": input.sections if input else None,
    }
    body = await http.post(f"/v1/agents/{agent_id}/boundary-reports", payload)
    return BoundaryReportResponse(
        report_id=str(body.get("report_id", "")),
        status=str(body.get("status", "")),
        web_url=str(body.get("web_url", "")),
    )


async def async_get_report(http: AsyncHttpClient, report_id: str) -> dict[str, Any]:
    return await http.get(f"/v1/boundary-reports/{report_id}")


async def async_wait_until_report_ready(
    http: AsyncHttpClient,
    report_id: str,
    *,
    timeout_ms: int = 30_000,
    poll_interval_ms: int = 1_000,
) -> dict[str, Any]:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        report = await async_get_report(http, report_id)
        if report.get("status") in {"generated", "shared"}:
            return report
        await asyncio.sleep(poll_interval_ms / 1000)
    raise TimeoutError(f"Report {report_id} was not ready within {timeout_ms}ms")
