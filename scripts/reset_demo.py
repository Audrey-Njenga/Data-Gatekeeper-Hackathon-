"""Reset the gatekeeper DB to a clean demo state: Balanced template, no rules/grants/history."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gatekeeper.core import Gatekeeper  # noqa: E402
from gatekeeper.store import Store  # noqa: E402

db = ROOT / "gatekeeper.db"
store = Store(str(db))
for table in ("ledger", "escalations", "grants", "rules", "settings"):
    store.db.execute(f"DELETE FROM {table}")
store.db.commit()
Gatekeeper(store)  # re-applies the Balanced template
print(f"Reset {db.name}: template=balanced, no rules, grants or history.")
print("Claude Desktop reconnects automatically on its next start.")
