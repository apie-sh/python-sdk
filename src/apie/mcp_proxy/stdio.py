from __future__ import annotations

from dataclasses import dataclass

from ..mcp_core.config import McpServerConfig


def require_mcp_sdk() -> None:
    try:
        import mcp  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "MCP proxy requires the optional mcp dependency. "
            "Install with: pip install apie-sdk[mcp-proxy]"
        ) from exc


@dataclass(slots=True)
class StdioProxyOptions:
    config: McpServerConfig
    api_key: str | None = None
    base_url: str | None = None
    run_id: str | None = None


async def start_stdio_proxy(options: StdioProxyOptions) -> None:
    require_mcp_sdk()
    import anyio
    import mcp.types as types
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    from ..mcp_core.client import ApieMcpClient, ApieMcpClientOptions
    from ..types import ApieRuntimeConfig
    from .interceptor import McpInterceptor

    config = options.config
    apie_client = ApieMcpClient(
        ApieMcpClientOptions(
            api_key=options.api_key,
            base_url=options.base_url,
            agent_key=config.agent_key,
            agent_name=config.agent_name,
            mode=config.mode,
            runtime=ApieRuntimeConfig(framework="mcp-proxy", language="python"),
        )
    )
    apie_client.identify()

    interceptor = McpInterceptor(
        config=config,
        apie_client=apie_client,
        run_id=options.run_id,
    )

    upstream_params = StdioServerParameters(
        command=config.upstream.command,
        args=config.upstream.args,
        env=config.upstream.env,
    )

    async with stdio_client(upstream_params) as (read, write):
        async with ClientSession(read, write) as upstream_session:
            await upstream_session.initialize()

            server = Server("apie-mcp-proxy", version="0.1.0")

            @server.list_tools()
            async def list_tools() -> list[types.Tool]:
                result = await upstream_session.list_tools()
                tool_payload = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema,
                    }
                    for tool in result.tools
                ]
                interceptor.handle_tools_list(tool_payload)
                return result.tools

            @server.call_tool(validate_input=False)
            async def call_tool(name: str, arguments: dict[str, object] | None) -> types.CallToolResult:
                args = {str(k): v for k, v in (arguments or {}).items()}
                gate = interceptor.before_tool_call(name, args)
                if not gate.allowed and gate.error:
                    return types.CallToolResult(
                        content=[
                            types.TextContent(
                                type="text",
                                text=McpInterceptor.format_blocked_result(gate.error),
                            )
                        ],
                        isError=True,
                    )

                try:
                    result = await upstream_session.call_tool(name, args)
                    interceptor.after_tool_call_success(name, args)
                    if isinstance(result, types.CallToolResult):
                        return result
                    return types.CallToolResult(content=list(result))
                except Exception as exc:
                    interceptor.after_tool_call_failure(name, args, exc)
                    raise

            async with stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )

    # Keep anyio happy if server exits
    await anyio.sleep(0)
