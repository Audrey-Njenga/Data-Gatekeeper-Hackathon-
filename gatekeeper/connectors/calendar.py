"""Example connector: a calendar (sample data). Just one of many possible sources."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from ..classifier import classify_text
from ..models import Item
from .base import Connector, Context, Operation

EVENT_FIELDS = ("title", "start", "end", "attendees", "notes")
DEFAULT_FIELDS = ["title", "start", "end"]


@dataclass(frozen=True)
class Event:
    id: str
    title: str
    start: datetime
    end: datetime
    attendees: list[str] = field(default_factory=list)
    notes: str = ""
    source_tags: tuple[str, ...] = ()


def _dt(value, default: datetime) -> datetime:
    if value is None:
        return default
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


class CalendarConnector(Connector):
    name = "calendar"
    description = "The user's calendar: appointments, meetings and personal events."

    def __init__(self, path: Path):
        self.path = path
        self._events: list[Event] | None = None

    @property
    def events(self) -> list[Event]:
        if self._events is None:
            raw = json.loads(self.path.read_text())
            tags = {c["id"]: tuple(c["source_tags"]) for c in raw["calendars"]}
            self._events = [
                Event(id=e["id"], title=e["title"], start=datetime.fromisoformat(e["start"]),
                      end=datetime.fromisoformat(e["end"]), attendees=e.get("attendees", []),
                      notes=e.get("notes", ""), source_tags=tags.get(e["calendar"], ()))
                for e in raw["events"]
            ]
        return self._events

    def operations(self) -> list[Operation]:
        period = {"start": "ISO datetime, start of the search period (optional)",
                  "end": "ISO datetime, end of the search period (optional)"}
        return [
            Operation("free_slots",
                      "Free time windows only, no event details. Best for scheduling, availability "
                      "or trip planning.",
                      self.free_slots,
                      {**period, "min_hours": "minimum window length in HOURS (e.g. 3 days = 72)"},
                      exposure=1),
            Operation("events",
                      "Calendar events with chosen fields. Only when the task truly needs event details.",
                      self.list_events,
                      {**period, "fields": f"subset of {list(EVENT_FIELDS)}"},
                      exposure=3),
        ]

    def _window(self, ctx: Context, start, end) -> tuple[datetime, datetime]:
        s = _dt(start, ctx.now)
        return s, _dt(end, s + timedelta(days=30))

    def free_slots(self, ctx: Context, start=None, end=None, min_hours=0) -> list[Item]:
        start, end = self._window(ctx, start, end)
        busy = sorted((max(e.start, start), min(e.end, end))
                      for e in self.events if e.end > start and e.start < end)
        merged: list[list[datetime]] = []
        for s, e in busy:
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        slots, cursor = [], start
        for s, e in merged:
            if s > cursor:
                slots.append((cursor, s))
            cursor = max(cursor, e)
        if cursor < end:
            slots.append((cursor, end))
        min_len = timedelta(hours=float(min_hours))
        return [
            Item(id=f"slot:{s.isoformat()}",
                 data={"start": s.isoformat(), "end": e.isoformat(),
                       "hours": round((e - s).total_seconds() / 3600, 1)},
                 categories={"general"})
            for s, e in slots if e - s >= min_len
        ]

    def list_events(self, ctx: Context, start=None, end=None, fields=None) -> list[Item]:
        start, end = self._window(ctx, start, end)
        if isinstance(fields, str):
            fields = [f.strip() for f in fields.split(",")]
        fields = [f for f in (fields or DEFAULT_FIELDS) if f in EVENT_FIELDS]
        items = []
        for e in self.events:
            if not (e.end > start and e.start < end):
                continue
            cats = set(e.source_tags) | classify_text(e.title)
            if "notes" in fields and e.notes:
                cats |= classify_text(e.notes) | {"private_notes"}
            if "attendees" in fields and e.attendees:
                cats.add("people")
            payload = {"title": e.title, "start": e.start.isoformat(), "end": e.end.isoformat(),
                       "attendees": e.attendees, "notes": e.notes}
            items.append(Item(id=e.id, data={k: payload[k] for k in fields}, categories=cats or {"general"}))
        return items
