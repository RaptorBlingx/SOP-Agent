"""Integration tests for MCP tools."""

import pytest


def test_mcp_tool_list():
    from app.mcp.server import mcp_server

    tools = mcp_server.get_tool_list()
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"ingest_sop", "run_sop", "approve_step", "get_report"}


def test_mcp_tool_schemas():
    from app.mcp.server import mcp_server

    for tool in mcp_server.get_tool_list():
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"
        assert "properties" in tool["inputSchema"]


@pytest.mark.asyncio
async def test_mcp_unknown_tool():
    from app.mcp.server import mcp_server

    result = await mcp_server.handle_call("nonexistent_tool", {})
    assert "error" in result
