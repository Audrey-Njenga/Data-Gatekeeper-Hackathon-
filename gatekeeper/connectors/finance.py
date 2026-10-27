"""Example connector: bank transactions (sample data)."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from ..models import Item
from .base import Connector, Context, Operation


class FinanceConnector(Connector):
    name = "finance"
    description = "The user's bank transactions and spending."

    def __init__(self, path: Path):
        self.path = path

    def _rows(self) -> list[dict]:
        with self.path.open() as f:
            return list(csv.DictReader(f))

    def operations(self) -> list[Operation]:
        return [
            Operation("spending_summary",
                      "Total spending per category. Enough for budgeting without revealing "
                      "individual transactions.", self.spending_summary, {}, exposure=1),
            Operation("transactions", "Individual bank transactions with merchant and amount.",
                      self.transactions, {}, exposure=3),
        ]

    def spending_summary(self, ctx: Context) -> list[Item]:
        totals: dict[str, float] = defaultdict(float)
        for r in self._rows():
            totals[r["category"]] += float(r["amount_gbp"])
        return [Item(id="finance:summary", data={k: round(v, 2) for k, v in totals.items()},
                     categories={"financial"})]

    def transactions(self, ctx: Context) -> list[Item]:
        return [Item(id=f"txn:{i}", data=r, categories={"financial"}) for i, r in enumerate(self._rows())]
