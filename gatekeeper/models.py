"""Core schemas shared by every gatekeeper component."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Category(str, Enum):
    FINANCIAL = "financial"
    HEALTH = "health"
    LOCATION = "location"
    PEOPLE = "people"
    CREDENTIALS = "credentials"
    PRIVATE_NOTES = "private_notes"
    WORK = "work"
    GENERAL = "general"


CATEGORIES = {c.value for c in Category}


class Effect(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


@dataclass(frozen=True)
class Rule:
    id: str
    effect: Effect
    category: str
    agents: tuple[str, ...] = ("*",)
    operations: tuple[str, ...] = ("*",)
    source: str = "template"  # "template" | "user"

    def matches(self, agent: str, operation: str, category: str) -> bool:
        return (
            self.category == category
            and ("*" in self.agents or agent in self.agents)
            and ("*" in self.operations or operation in self.operations)
        )


@dataclass
class Item:
    """One unit of data an operation wants to release, with its sensitivity labels."""
    id: str
    data: dict
    categories: set[str] = field(default_factory=set)


@dataclass
class Decision:
    effect: Effect
    per_category: dict[str, Effect]
    rule_ids: list[str]

    @property
    def ask_categories(self) -> list[str]:
        return [c for c, e in self.per_category.items() if e == Effect.ASK]
