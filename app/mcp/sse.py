"""MCP SSE transport — mountable as FastAPI route."""

from __future__ import annotations

import json
import asyncio
from typing import AsyncGenerator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.mcp.server import mcp_server
from app.core.logging import get_logger

logger = get_logger("mcp.sse")

router = APIRouter(prefix="/mcp")


@router.get("/tools")
async def list_tools() -> dict:
    """List available MCP tools."""
    return {"tools": mcp_server.get_tool_list()}


@router.post("/call")
async def call_tool(request: Request) -> dict:
    """Call an MCP tool by name with arguments."""
    body = await request.json()
    tool_name = body.get("name")
    arguments = body.get("arguments", {})

    if not tool_name:
        return {"error": "Missing 'name' field"}

    result = await mcp_server.handle_call(tool_name, arguments)
    return result


@router.get("/sse")
async def sse_stream(request: Request) -> EventSourceResponse:
    """SSE endpoint for MCP tool streaming.

    Clients POST tool calls to /mcp/call and listen here for results.
    """
    async def event_generator() -> AsyncGenerator[dict, None]:
        # Keepalive stream — real tool results come via /mcp/call
        while True:
            if await request.is_disconnected():
                break
            yield {"event": "keepalive", "data": "{}"}
            await asyncio.sleep(30)

    return EventSourceResponse(event_generator())
