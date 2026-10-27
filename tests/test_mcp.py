"""End-to-end: spawn the MCP server over stdio like Claude Desktop does, and call tools."""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


def test_mcp_server_end_to_end(tmp_path):
    async def run():
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "gatekeeper.mcp_server"], cwd=str(ROOT),
            env={**os.environ, "GATEKEEPER_AGENT": "travel-agent", "INTERPRETER": "mock",
                 "GATEKEEPER_DB": str(tmp_path / "t.db")},
        )
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            tools = {t.name for t in (await s.list_tools()).tools}
            assert tools == {"request_data", "get_free_slots", "get_events",
                             "get_preferences", "get_profile_field"}
            res = await s.call_tool("request_data", {"request": "whole calendar to plan a trip"})
            body = json.loads(res.content[0].text)
            assert body["interpreted_as"]["operation"] == "get_free_slots"
            res = await s.call_tool("get_events", {"start": "2026-11-01T00:00:00",
                                                   "end": "2026-12-01T00:00:00"})
            titles = {e["title"] for e in json.loads(res.content[0].text)["data"]}
            assert "Mortgage advisor call" not in titles and "Team standup" in titles

    asyncio.run(run())
