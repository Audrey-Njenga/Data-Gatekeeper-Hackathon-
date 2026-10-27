"""Typed operations. Each turns raw source data into labelled Items.

Agents can only call these; there is no "read everything" operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .classifier import classify_text
from .models import Item
from .sources import Event, load_events, load_profile, load_transactions

EVENT_FIELDS = {"title", "start", "end", "attendees", "notes"}
DEFAULT_EVENT_FIELDS = ["title", "start", "end"]


@dataclass
class DataBundle:
    events: list[Event]
    profile: dict
    transactions: list[dict]

    @classmethod
    def load(cls) -> "DataBundle":
        return cls(load_events(), load_profile(), load_transactions())


def _dt(value, default: datetime) -> datetime:
    if value is None:
        return default
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))


def get_free_slots(data: DataBundle, now: datetime, start=None, end=None, min_hours: float = 0) -> list[Item]:
    """Free windows only. Computed from ALL events but reveals no titles/attendees."""
    start = _dt(start, now)
    end = _dt(end, start + timedelta(days=30))
    busy = sorted(
        (max(e.start, start), min(e.end, end)) for e in data.events if e.end > start and e.start < end
    )
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
        Item(
            id=f"slot:{s.isoformat()}",
            data={"start": s.isoformat(), "end": e.isoformat(), "hours": round((e - s).total_seconds() / 3600, 1)},
            categories={"general"},
        )
        for s, e in slots if e - s >= min_len
    ]


def get_events(data: DataBundle, now: datetime, start=None, end=None, fields=None) -> list[Item]:
    start = _dt(start, now)
    end = _dt(end, start + timedelta(days=30))
    fields = [f for f in (fields or DEFAULT_EVENT_FIELDS) if f in EVENT_FIELDS]
    items = []
    for e in data.events:
        if not (e.end > start and e.start < end):
            continue
        cats = set(e.source_tags) | classify_text(e.title)
        if "notes" in fields and e.notes:
            cats |= classify_text(e.notes) | {"private_notes"}
        if "attendees" in fields and e.attendees:
            cats.add("people")
        payload = {
            "title": e.title, "start": e.start.isoformat(), "end": e.end.isoformat(),
            "attendees": e.attendees, "notes": e.notes,
        }
        items.append(Item(id=e.id, data={k: payload[k] for k in fields}, categories=cats or {"general"}))
    return items


def get_preferences(data: DataBundle, now: datetime, category: str = "travel") -> list[Item]:
    prefs = data.profile.get("preferences", {})
    if category not in prefs:
        return []
    cats = {"general"} | classify_text(str(prefs[category]))
    return [Item(id=f"pref:{category}", data={category: prefs[category]}, categories=cats)]


def get_profile_field(data: DataBundle, now: datetime, name: str = "") -> list[Item]:
    field_ = data.profile.get("fields", {}).get(name)
    if not field_:
        return []
    return [Item(id=f"profile:{name}", data={name: field_["value"]}, categories=set(field_["tags"]))]


def get_transactions(data: DataBundle, now: datetime) -> list[Item]:
    return [
        Item(id=f"txn:{i}", data=t, categories={"financial"})
        for i, t in enumerate(data.transactions)
    ]


OPERATIONS = {
    "get_free_slots": get_free_slots,
    "get_events": get_events,
    "get_preferences": get_preferences,
    "get_profile_field": get_profile_field,
    "get_transactions": get_transactions,
}
