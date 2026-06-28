from __future__ import annotations

from typing import Any, Awaitable, Protocol

from ..context import resolve_run_id
from .mcp import with_mcp_tool_call, with_mcp_tool_call_async


class McpClientLike(Protocol):
    def call_tool(self, name: str, args: dict[str, Any] | None = None) -> Any: ...

    def list_tools(self) -> Any: ...


class AsyncMcpClientLike(Protocol):
    async def call_tool(
        self, name: str, args: dict[str, Any] | None = None
    ) -> Any: ...

    async def list_tools(self) -> Any: ...


def create_instrumented_mcp_client(
    apie: Any,
    client: McpClientLike,
    *,
    server: str,
    environment: str | None = None,
    risk_level: str | None = None,
) -> McpClientLike:
    class InstrumentedMcpClient:
        def call_tool(self, name: str, args: dict[str, Any] | None = None) -> Any:
            run_id = resolve_run_id()
            if not run_id:
                raise RuntimeError(
                    "create_instrumented_mcp_client requires an active run context"
                )
            return with_mcp_tool_call(
                apie,
                {
                    "runId": run_id,
                    "server": server,
                    "tool": name,
                    "environment": environment,
                    "riskLevel": risk_level,
                    "payloadSummary": {"arguments": args or {}},
                },
                lambda: client.call_tool(name, args),
            )

        def list_tools(self) -> Any:
            result = client.list_tools()
            run_id = resolve_run_id()
            if run_id and hasattr(result, "get"):
                tools = result.get("tools", [])
                for tool in tools:
                    try:
                        apie.define_tool(
                            {
                                "name": f"{server}.{tool.get('name')}",
                                "provider": "mcp",
                                "description": tool.get("description"),
                                "inputSchema": tool.get("inputSchema"),
                                "riskLevel": risk_level or "medium",
                            }
                        )
                    except Exception:
                        pass
            return result

    return InstrumentedMcpClient()


def create_instrumented_mcp_client_async(
    apie: Any,
    client: AsyncMcpClientLike,
    *,
    server: str,
    environment: str | None = None,
    risk_level: str | None = None,
) -> AsyncMcpClientLike:
    class InstrumentedAsyncMcpClient:
        async def call_tool(
            self, name: str, args: dict[str, Any] | None = None
        ) -> Any:
            run_id = resolve_run_id()
            if not run_id:
                raise RuntimeError(
                    "create_instrumented_mcp_client_async requires an active run context"
                )
            return await with_mcp_tool_call_async(
                apie,
                {
                    "runId": run_id,
                    "server": server,
                    "tool": name,
                    "environment": environment,
                    "riskLevel": risk_level,
                    "payloadSummary": {"arguments": args or {}},
                },
                lambda: client.call_tool(name, args),
            )

        async def list_tools(self) -> Any:
            result = await client.list_tools()
            run_id = resolve_run_id()
            if run_id and hasattr(result, "get"):
                tools = result.get("tools", [])
                for tool in tools:
                    try:
                        await apie.define_tool(
                            {
                                "name": f"{server}.{tool.get('name')}",
                                "provider": "mcp",
                                "description": tool.get("description"),
                                "inputSchema": tool.get("inputSchema"),
                                "riskLevel": risk_level or "medium",
                            }
                        )
                    except Exception:
                        pass
            return result

    return InstrumentedAsyncMcpClient()
