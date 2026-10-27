"""MCP server exposing the gatekeeper to Claude Desktop (stdio).

Each Claude Desktop config entry sets GATEKEEPER_AGENT, so one process == one agent identity.
stdout is reserved for the MCP protocol: never print() here.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

from mcp.server.mcpserver import MCPServer  # noqa: E402  (mcp 2.x)

from .core import Gatekeeper  # noqa: E402
from .interpreter import Interpreter  # noqa: E402
from .store import Store  # noqa: E402

AGENT = os.getenv("GATEKEEPER_AGENT", "claude-desktop")
DB_PATH = os.getenv("GATEKEEPER_DB", str(ROOT / "gatekeeper.db"))

gk = Gatekeeper(Store(DB_PATH))
if gk.store.get_grant(AGENT) is None and os.getenv("GATEKEEPER_AUTO_CONNECT", "1") == "1":
    gk.connect_agent(AGENT, hours=24)  # demo convenience; revocations are kept
_interpreter: Interpreter | None = None


def _interp() -> Interpreter:
    global _interpreter
    if _interpreter is None:
        _interpreter = Interpreter()
    return _interpreter


mcp = MCPServer(
    "privacy-gatekeeper",
    instructions=(
        "All access to the user's personal data (calendar, profile, preferences, finances) goes "
        "through this gatekeeper. Ask only for what your task needs. Results may be filtered by "
        "the user's privacy rules; do not try to work around withheld items. If items are "
        "pending approval, tell the user and retry after they approve."
    ),
)


@mcp.tool()
def request_data(request: str) -> dict:
    """Describe in plain language what data you need and why (e.g. 'free days next month for a
    3-day trip'). The gatekeeper chooses the minimal data that serves the task."""
    try:
        return gk.request_data(AGENT, request, _interp())
    except Exception as exc:  # model backend down etc.
        print(f"interpreter error: {exc}", file=sys.stderr)
        return {"status": "error", "error": "interpreter_unavailable",
                "detail": "Use a typed tool such as get_free_slots instead."}


@mcp.tool()
def get_free_slots(start: str | None = None, end: str | None = None, min_hours: float = 0) -> dict:
    """Free time windows between start and end (ISO datetimes). No event details are revealed."""
    return gk.handle(AGENT, "get_free_slots", {"start": start, "end": end, "min_hours": min_hours})


@mcp.tool()
def get_events(start: str | None = None, end: str | None = None,
               fields: list[str] | None = None) -> dict:
    """Calendar events with chosen fields (title, start, end, attendees, notes). Sensitive events
    may be withheld."""
    return gk.handle(AGENT, "get_events", {"start": start, "end": end, "fields": fields})


@mcp.tool()
def get_preferences(category: str) -> dict:
    """User preferences for one category: travel, dietary, shopping, communication."""
    return gk.handle(AGENT, "get_preferences", {"category": category})


@mcp.tool()
def get_profile_field(name: str) -> dict:
    """One profile field, e.g. preferred_name, timezone, home_city."""
    return gk.handle(AGENT, "get_profile_field", {"name": name})


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
