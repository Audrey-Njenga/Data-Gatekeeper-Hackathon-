"""Connector abstraction. A connector is any personal data source (calendar, notes, email,
bank, health records...). The gatekeeper core knows nothing about specific sources.

A connector exposes typed *operations*. Each operation returns labelled Items, and every
Item then goes through the same policy engine. Operations declare an `exposure` level so
the interpreter can prefer the least revealing one:
    1 = derived answer (e.g. free/busy, totals)
    2 = selected fields
    3 = raw records
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from ..models import Item

EXPOSURE_LABELS = {1: "derived", 2: "fields", 3: "raw"}


@dataclass(frozen=True)
class Context:
    now: datetime  # naive local time, used for relative defaults


@dataclass
class Operation:
    name: str
    description: str
    fn: Callable[..., list[Item]]
    params: dict[str, str] = field(default_factory=dict)  # name -> description (units, format)
    exposure: int = 2


class Connector:
    name: str = ""
    description: str = ""

    def operations(self) -> list[Operation]:
        raise NotImplementedError


class Registry:
    """All connectors available to the gatekeeper. Operations are addressed as 'source.op'."""

    def __init__(self, connectors: list[Connector]):
        self.connectors = {c.name: c for c in connectors}
        self.ops: dict[str, Operation] = {}
        for c in connectors:
            for op in c.operations():
                self.ops[f"{c.name}.{op.name}"] = op

    def __contains__(self, qualified: str) -> bool:
        return qualified in self.ops

    def run(self, qualified: str, ctx: Context, params: dict) -> list[Item]:
        op = self.ops[qualified]
        unknown = set(params) - set(op.params)
        if unknown:
            raise ValueError(f"Unknown parameter(s) for {qualified}: {sorted(unknown)}")
        return op.fn(ctx, **{k: v for k, v in params.items() if v not in (None, "")})

    def catalog(self) -> dict:
        """Grouped by source; for the dashboard and MCP discovery. Contains no user data."""
        return {
            name: {
                "description": c.description,
                "operations": {
                    op.name: {"description": op.description, "params": op.params, "exposure": op.exposure}
                    for op in c.operations()
                },
            }
            for name, c in self.connectors.items()
        }

    def flat_catalog(self) -> dict[str, dict]:
        """Qualified op -> spec; for the interpreter."""
        return {
            q: {"source": q.split(".")[0], "source_description": self.connectors[q.split(".")[0]].description,
                "description": op.description, "params": op.params,
                "exposure": f"{op.exposure} ({EXPOSURE_LABELS[op.exposure]})"}
            for q, op in self.ops.items()
        }
