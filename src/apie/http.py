from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Mapping, Optional

import httpx

from .errors import ApieError


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _build_url(
    base_url: str,
    path: str,
    query: Optional[Mapping[str, Any]] = None,
) -> str:
    url = httpx.URL(f"{base_url}/").join(path.lstrip("/"))
    if query:
        url = url.copy_merge_params({k: str(v) for k, v in query.items() if v is not None})
    return str(url)


def _parse_response_body(response: httpx.Response) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    text = response.text
    return text if text else None


def parse_retry_after_ms(header_value: Optional[str]) -> Optional[int]:
    if not header_value:
        return None
    trimmed = header_value.strip()
    if not trimmed:
        return None

    try:
        as_seconds = float(trimmed)
        if as_seconds >= 0:
            return round(as_seconds * 1000)
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(trimmed)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = retry_at - now
        return max(0, round(delta.total_seconds() * 1000))
    except (TypeError, ValueError):
        return None


@dataclass(slots=True)
class ApieClientOptions:
    base_url: str
    api_key: Optional[str] = None
    timeout: Optional[int] = None
    headers: Mapping[str, str] = field(default_factory=dict)
    client: Optional[httpx.Client] = None


@dataclass(slots=True)
class AsyncApieClientOptions:
    base_url: str
    api_key: Optional[str] = None
    timeout: Optional[int] = None
    headers: Mapping[str, str] = field(default_factory=dict)
    client: Optional[httpx.AsyncClient] = None


class HttpClient:
    def __init__(self, options: ApieClientOptions) -> None:
        self._base_url = normalize_base_url(options.base_url)
        self._timeout_ms = options.timeout
        self._default_headers = {
            "Content-Type": "application/json",
            **dict(options.headers),
        }
        if options.api_key:
            self._default_headers["Authorization"] = f"Bearer {options.api_key}"
        timeout = None if options.timeout is None else options.timeout / 1000
        self._client = options.client or httpx.Client(timeout=timeout)
        self._owns_client = options.client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def request(
        self,
        *,
        method: str = "GET",
        path: str,
        query: Optional[Mapping[str, Any]] = None,
        body: Any = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        url = _build_url(self._base_url, path, query)
        merged_headers = {**self._default_headers, **(headers or {})}
        try:
            response = self._client.request(
                method.upper(),
                url,
                headers=merged_headers,
                json=body if body is not None else None,
            )
        except httpx.TimeoutException as exc:
            raise ApieError("Request timed out", status=408) from exc

        response_body = _parse_response_body(response)
        request_id = response.headers.get("x-request-id") or response.headers.get(
            "x-apie-request-id"
        )
        retry_after_ms = parse_retry_after_ms(response.headers.get("retry-after"))

        if response.is_error:
            raise ApieError(
                f"Request failed with status {response.status_code}",
                status=response.status_code,
                body=response_body,
                request_id=request_id,
                retry_after_ms=retry_after_ms,
            )
        return response_body

    def get(
        self,
        path: str,
        *,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        return self.request(method="GET", path=path, query=query, headers=headers)

    def post(
        self,
        path: str,
        body: Any = None,
        *,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        return self.request(
            method="POST",
            path=path,
            query=query,
            body=body,
            headers=headers,
        )


class AsyncHttpClient:
    def __init__(self, options: AsyncApieClientOptions) -> None:
        self._base_url = normalize_base_url(options.base_url)
        self._default_headers = {
            "Content-Type": "application/json",
            **dict(options.headers),
        }
        if options.api_key:
            self._default_headers["Authorization"] = f"Bearer {options.api_key}"
        timeout = None if options.timeout is None else options.timeout / 1000
        self._client = options.client or httpx.AsyncClient(timeout=timeout)
        self._owns_client = options.client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        *,
        method: str = "GET",
        path: str,
        query: Optional[Mapping[str, Any]] = None,
        body: Any = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        url = _build_url(self._base_url, path, query)
        merged_headers = {**self._default_headers, **(headers or {})}
        try:
            response = await self._client.request(
                method.upper(),
                url,
                headers=merged_headers,
                json=body if body is not None else None,
            )
        except httpx.TimeoutException as exc:
            raise ApieError("Request timed out", status=408) from exc

        response_body = _parse_response_body(response)
        request_id = response.headers.get("x-request-id") or response.headers.get(
            "x-apie-request-id"
        )
        retry_after_ms = parse_retry_after_ms(response.headers.get("retry-after"))

        if response.is_error:
            raise ApieError(
                f"Request failed with status {response.status_code}",
                status=response.status_code,
                body=response_body,
                request_id=request_id,
                retry_after_ms=retry_after_ms,
            )
        return response_body

    async def get(
        self,
        path: str,
        *,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        return await self.request(method="GET", path=path, query=query, headers=headers)

    async def post(
        self,
        path: str,
        body: Any = None,
        *,
        query: Optional[Mapping[str, Any]] = None,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Any:
        return await self.request(
            method="POST",
            path=path,
            query=query,
            body=body,
            headers=headers,
        )
