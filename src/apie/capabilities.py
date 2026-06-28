from __future__ import annotations

from .http import AsyncHttpClient, HttpClient
from .types import DeclaredCapabilityInput, ToolDefinitionInput


def declare_capabilities(
    http: HttpClient,
    agent_id: str,
    capabilities: list[DeclaredCapabilityInput],
) -> dict:
    return http.post(
        f"/v1/agents/{agent_id}/capabilities/declare",
        {
            "capabilities": [
                {
                    "tool": {"name": cap.tool.name, "provider": cap.tool.provider},
                    "actions": cap.actions,
                    "resources": cap.resources,
                    "environments": cap.environments,
                    "riskLevel": cap.risk_level,
                }
                for cap in capabilities
            ]
        },
    )


def define_tool(http: HttpClient, agent_id: str, tool: ToolDefinitionInput) -> dict:
    return http.post(
        f"/v1/agents/{agent_id}/tools/define",
        {
            "name": tool.name,
            "provider": tool.provider,
            "description": tool.description,
            "inputSchema": tool.input_schema,
            "actionTypes": tool.action_types,
            "resourceTypes": tool.resource_types,
            "riskLevel": tool.risk_level,
        },
    )


async def async_declare_capabilities(
    http: AsyncHttpClient,
    agent_id: str,
    capabilities: list[DeclaredCapabilityInput],
) -> dict:
    return await http.post(
        f"/v1/agents/{agent_id}/capabilities/declare",
        {
            "capabilities": [
                {
                    "tool": {"name": cap.tool.name, "provider": cap.tool.provider},
                    "actions": cap.actions,
                    "resources": cap.resources,
                    "environments": cap.environments,
                    "riskLevel": cap.risk_level,
                }
                for cap in capabilities
            ]
        },
    )


async def async_define_tool(
    http: AsyncHttpClient,
    agent_id: str,
    tool: ToolDefinitionInput,
) -> dict:
    return await http.post(
        f"/v1/agents/{agent_id}/tools/define",
        {
            "name": tool.name,
            "provider": tool.provider,
            "description": tool.description,
            "inputSchema": tool.input_schema,
            "actionTypes": tool.action_types,
            "resourceTypes": tool.resource_types,
            "riskLevel": tool.risk_level,
        },
    )
