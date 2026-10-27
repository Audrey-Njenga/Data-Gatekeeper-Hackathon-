"""Example connector: user profile and preferences (sample data)."""
from __future__ import annotations

import json
from pathlib import Path

from ..classifier import classify_text
from ..models import Item
from .base import Connector, Context, Operation


class ProfileConnector(Connector):
    name = "profile"
    description = "The user's personal profile fields and stated preferences."

    def __init__(self, path: Path):
        self.path = path
        self._data: dict | None = None

    @property
    def data(self) -> dict:
        if self._data is None:
            self._data = json.loads(self.path.read_text())
        return self._data

    def operations(self) -> list[Operation]:
        return [
            Operation("preferences", "The user's preferences for one topic.", self.preferences,
                      {"category": f"one of {sorted(self.data.get('preferences', {}))}"}, exposure=2),
            Operation("field", "A single profile field.", self.field,
                      {"name": f"one of {sorted(self.data.get('fields', {}))}"}, exposure=2),
        ]

    def preferences(self, ctx: Context, category: str = "") -> list[Item]:
        prefs = self.data.get("preferences", {})
        if category not in prefs:
            return []
        return [Item(id=f"pref:{category}", data={category: prefs[category]},
                     categories={"general"} | classify_text(str(prefs[category])))]

    def field(self, ctx: Context, name: str = "") -> list[Item]:
        f = self.data.get("fields", {}).get(name)
        if not f:
            return []
        return [Item(id=f"profile:{name}", data={name: f["value"]}, categories=set(f["tags"]))]
