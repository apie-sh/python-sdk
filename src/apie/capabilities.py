from __future__ import annotations

from .http import AsyncHttpClient, HttpClient
from .omit import omit_none
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
                omit_none(
                    {
                        "tool": omit_none(
                            {"name": cap.tool.name, "provider": cap.tool.provider}
                        ),
                        "actions": cap.actions or None,
                        "resources": cap.resources or None,
                        "environments": cap.environments or None,
                        "riskLevel": cap.risk_level,
                    }
                )
                for cap in capabilities
            ]
        },
    )


def define_tool(http: HttpClient, agent_id: str, tool: ToolDefinitionInput) -> dict:
    return http.post(
        f"/v1/agents/{agent_id}/tools/define",
        omit_none(
            {
                "name": tool.name,
                "provider": tool.provider,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "actionTypes": tool.action_types or None,
                "resourceTypes": tool.resource_types or None,
                "riskLevel": tool.risk_level,
            }
        ),
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
                omit_none(
                    {
                        "tool": omit_none(
                            {"name": cap.tool.name, "provider": cap.tool.provider}
                        ),
                        "actions": cap.actions or None,
                        "resources": cap.resources or None,
                        "environments": cap.environments or None,
                        "riskLevel": cap.risk_level,
                    }
                )
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
        omit_none(
            {
                "name": tool.name,
                "provider": tool.provider,
                "description": tool.description,
                "inputSchema": tool.input_schema,
                "actionTypes": tool.action_types or None,
                "resourceTypes": tool.resource_types or None,
                "riskLevel": tool.risk_level,
            }
        ),
    )
