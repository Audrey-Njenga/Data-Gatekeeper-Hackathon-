"""MCP server exposing the gatekeeper to MCP clients such as Claude Desktop (stdio).

Source-agnostic: exposes discovery + two generic tools. Whatever connectors are registered
become reachable without changing this file.
Each client config sets GATEKEEPER_AGENT, so one process == one agent identity.
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
        "All access to the user's personal data goes through this gatekeeper. Prefer "
        "request_data and describe what you need and why. Results may be filtered by the "
        "user's privacy rules; do not try to work around withheld items. If items are pending "
        "approval, tell the user and retry after they approve."
    ),
)


@mcp.tool()
def request_data(request: str) -> dict:
    """Describe in plain language what personal data you need and why (e.g. 'free days next
    month to plan a 3-day trip'). The gatekeeper chooses the minimal data that serves the task."""
    try:
        return gk.request_data(AGENT, request, _interp())
    except Exception as exc:  # model backend down etc.
        print(f"interpreter error: {exc}", file=sys.stderr)
        return {"status": "error", "error": "interpreter_unavailable",
                "detail": "Call list_sources, then query with an explicit operation."}


@mcp.tool()
def list_sources() -> dict:
    """List available data sources and their operations (descriptions and parameters only,
    no user data). Prefer operations with lower 'exposure'."""
    return gk.registry.catalog()


@mcp.tool()
def query(operation: str, params: dict | None = None) -> dict:
    """Run one operation from list_sources, addressed as 'source.operation'
    (e.g. 'calendar.free_slots'). Results are filtered by the user's privacy rules."""
    return gk.handle(AGENT, operation, params or {})


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
