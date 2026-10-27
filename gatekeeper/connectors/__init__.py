"""Connector registry. Add new data sources here; nothing else in the gatekeeper changes."""
from __future__ import annotations

from pathlib import Path

from .base import Connector, Context, Operation, Registry
from .calendar import CalendarConnector
from .finance import FinanceConnector
from .profile import ProfileConnector

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

__all__ = ["Connector", "Context", "Operation", "Registry", "default_registry"]


def default_registry(data_dir: Path = DATA_DIR) -> Registry:
    return Registry([
        CalendarConnector(data_dir / "calendar.json"),
        ProfileConnector(data_dir / "profile.json"),
        FinanceConnector(data_dir / "transactions.csv"),
    ])
