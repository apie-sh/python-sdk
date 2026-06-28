#!/usr/bin/env bash
# Example: point your MCP host at the Apie Python MCP proxy (stdio).
#
# Prerequisites:
#   pip install apie-sdk[mcp-proxy]
#   export APIE_API_KEY=apie_sk_...
#
# Then configure your MCP host to run:
#   apie mcp proxy --config examples/apie.mcp.json

set -euo pipefail

apie mcp proxy --config "$(dirname "$0")/apie.mcp.json"
