"""Data source loader. DATA_SOURCE=sample (default) reads local files; google is not wired up yet."""
from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Event:
    id: str
    calendar: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str] = field(default_factory=list)
    notes: str = ""
    source_tags: tuple[str, ...] = ()


def _source() -> str:
    return os.getenv("DATA_SOURCE", "sample").lower()


def load_events() -> list[Event]:
    if _source() != "sample":
        raise NotImplementedError("Only DATA_SOURCE=sample is supported for now.")
    raw = json.loads((DATA_DIR / "calendar.json").read_text())
    tags = {c["id"]: tuple(c["source_tags"]) for c in raw["calendars"]}
    return [
        Event(
            id=e["id"], calendar=e["calendar"], title=e["title"],
            start=datetime.fromisoformat(e["start"]), end=datetime.fromisoformat(e["end"]),
            attendees=e.get("attendees", []), notes=e.get("notes", ""),
            source_tags=tags.get(e["calendar"], ()),
        )
        for e in raw["events"]
    ]


def load_profile() -> dict:
    return json.loads((DATA_DIR / "profile.json").read_text())


def load_transactions() -> list[dict]:
    with (DATA_DIR / "transactions.csv").open() as f:
        return list(csv.DictReader(f))
