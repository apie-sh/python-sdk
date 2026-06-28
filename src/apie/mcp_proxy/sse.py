from __future__ import annotations

from dataclasses import dataclass

from ..mcp_core.config import McpServerConfig
from .stdio import require_mcp_sdk


@dataclass(slots=True)
class SseProxyOptions:
    config: McpServerConfig
    port: int = 3100
    api_key: str | None = None
    base_url: str | None = None
    run_id: str | None = None


async def start_sse_proxy(options: SseProxyOptions) -> None:
    require_mcp_sdk()
    import os

    import mcp.types as types
    import uvicorn
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from mcp.server import Server
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    from ..mcp_core.client import ApieMcpClient, ApieMcpClientOptions
    from ..types import ApieRuntimeConfig
    from .interceptor import McpInterceptor

    config = options.config
    expected_api_key = options.api_key or os.environ.get("APIE_API_KEY")

    apie_client = ApieMcpClient(
        ApieMcpClientOptions(
            api_key=options.api_key,
            base_url=options.base_url,
            agent_key=config.agent_key,
            agent_name=config.agent_name,
            release_mode=config.release_mode,
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

            sse = SseServerTransport("/message")

            async def handle_sse(request: Request) -> Response:
                if expected_api_key:
                    auth = request.headers.get("authorization", "")
                    token = auth[7:].strip() if auth.startswith("Bearer ") else None
                    if token != expected_api_key:
                        return Response("Unauthorized", status_code=401)

                async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
                    await server.run(
                        streams[0],
                        streams[1],
                        server.create_initialization_options(),
                    )
                return Response()

            app = Starlette(
                routes=[
                    Route("/sse", endpoint=handle_sse, methods=["GET"]),
                    Mount("/message", app=sse.handle_post_message),
                ]
            )

            print(f"[apie] MCP SSE proxy listening on http://localhost:{options.port}/sse")
            config_uvicorn = uvicorn.Config(
                app,
                host="127.0.0.1",
                port=options.port,
                log_level="warning",
            )
            server_uvicorn = uvicorn.Server(config_uvicorn)
            await server_uvicorn.serve()
