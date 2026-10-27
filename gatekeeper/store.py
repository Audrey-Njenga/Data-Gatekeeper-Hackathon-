"""SQLite persistence: rules, grants, escalations, ledger.

The ledger stores item IDs and categories only, never the released content.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime

from .models import Effect, Rule

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS rules(
  id TEXT PRIMARY KEY, effect TEXT, category TEXT, agents TEXT, operations TEXT,
  source TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS grants(
  agent TEXT PRIMARY KEY, operations TEXT, expires_at TEXT, revoked INTEGER DEFAULT 0,
  created_at TEXT);
CREATE TABLE IF NOT EXISTS escalations(
  id TEXT PRIMARY KEY, agent TEXT, operation TEXT, category TEXT, item_count INTEGER,
  status TEXT, created_at TEXT, resolved_at TEXT, resolution TEXT);
CREATE TABLE IF NOT EXISTS ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, agent TEXT, operation TEXT, params TEXT,
  outcome TEXT, released TEXT, hidden TEXT, escalations TEXT, interpreted_from TEXT);
"""


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # settings
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, value))
        self.db.commit()

    # rules
    def list_rules(self) -> list[Rule]:
        return [
            Rule(id=r["id"], effect=Effect(r["effect"]), category=r["category"],
                 agents=tuple(json.loads(r["agents"])), operations=tuple(json.loads(r["operations"])),
                 source=r["source"])
            for r in self.db.execute("SELECT * FROM rules ORDER BY created_at")
        ]

    def add_rule(self, rule: Rule, now: datetime) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO rules VALUES(?,?,?,?,?,?,?)",
            (rule.id, rule.effect.value, rule.category, json.dumps(list(rule.agents)),
             json.dumps(list(rule.operations)), rule.source, now.isoformat()),
        )
        self.db.commit()

    def delete_rule(self, rule_id: str) -> None:
        self.db.execute("DELETE FROM rules WHERE id=?", (rule_id,))
        self.db.commit()

    def delete_template_rules(self) -> None:
        self.db.execute("DELETE FROM rules WHERE source='template'")
        self.db.commit()

    # grants
    def upsert_grant(self, agent: str, operations: list[str], expires_at: datetime, now: datetime) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO grants VALUES(?,?,?,0,?)",
            (agent, json.dumps(operations), expires_at.isoformat(), now.isoformat()),
        )
        self.db.commit()

    def get_grant(self, agent: str) -> dict | None:
        row = self.db.execute("SELECT * FROM grants WHERE agent=?", (agent,)).fetchone()
        if not row:
            return None
        return {**dict(row), "operations": json.loads(row["operations"]),
                "expires_at": datetime.fromisoformat(row["expires_at"]), "revoked": bool(row["revoked"])}

    def list_grants(self) -> list[dict]:
        return [self.get_grant(r["agent"]) for r in self.db.execute("SELECT agent FROM grants")]

    def revoke_grant(self, agent: str) -> None:
        self.db.execute("UPDATE grants SET revoked=1 WHERE agent=?", (agent,))
        self.db.commit()

    # escalations
    def open_escalation(self, agent: str, operation: str, category: str, now: datetime) -> str:
        row = self.db.execute(
            "SELECT id FROM escalations WHERE agent=? AND category=? AND status='pending'",
            (agent, category),
        ).fetchone()
        if row:
            self.db.execute("UPDATE escalations SET item_count=item_count+1 WHERE id=?", (row["id"],))
            self.db.commit()
            return row["id"]
        esc_id = uuid.uuid4().hex[:8]
        self.db.execute(
            "INSERT INTO escalations VALUES(?,?,?,?,1,'pending',?,NULL,NULL)",
            (esc_id, agent, operation, category, now.isoformat()),
        )
        self.db.commit()
        return esc_id

    def get_escalation(self, esc_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM escalations WHERE id=?", (esc_id,)).fetchone()
        return dict(row) if row else None

    def list_escalations(self, status: str | None = "pending") -> list[dict]:
        q, args = "SELECT * FROM escalations", ()
        if status:
            q, args = q + " WHERE status=?", (status,)
        return [dict(r) for r in self.db.execute(q + " ORDER BY created_at", args)]

    def resolve_escalation(self, esc_id: str, resolution: str, now: datetime) -> None:
        self.db.execute(
            "UPDATE escalations SET status='resolved', resolution=?, resolved_at=? WHERE id=?",
            (resolution, now.isoformat(), esc_id),
        )
        self.db.commit()

    # ledger
    def log(self, entry: dict) -> int:
        cur = self.db.execute(
            "INSERT INTO ledger(ts,agent,operation,params,outcome,released,hidden,escalations,interpreted_from)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (entry["ts"], entry["agent"], entry["operation"], json.dumps(entry.get("params", {}), default=str),
             entry["outcome"], json.dumps(entry.get("released", [])), json.dumps(entry.get("hidden", [])),
             json.dumps(entry.get("escalations", [])), entry.get("interpreted_from")),
        )
        self.db.commit()
        return cur.lastrowid

    def ledger(self, limit: int = 200) -> list[dict]:
        rows = self.db.execute("SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (limit,))
        out = []
        for r in rows:
            d = dict(r)
            for k in ("params", "released", "hidden", "escalations"):
                d[k] = json.loads(d[k])
            out.append(d)
        return out
