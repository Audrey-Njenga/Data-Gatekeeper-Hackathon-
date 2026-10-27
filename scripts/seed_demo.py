"""Seed demo activity through the HTTP API (dashboard must be watching :8000).

Usage: .venv/bin/python scripts/seed_demo.py [--no-model]
"""
import json
import sys

import httpx

B = "http://localhost:8000/api"
NOV = {"start": "2026-11-01T00:00:00", "end": "2026-12-01T00:00:00"}
c = httpx.Client(timeout=120)


def show(label, r):
    body = r.json()
    print(f"\n# {label}\n  {body.get('message') or body.get('error') or body}")
    if "interpreted_as" in body:
        print(f"  interpreted as: {json.dumps(body['interpreted_as'])}")


for a in ("travel-agent", "shopping-agent"):
    c.post(f"{B}/agents", json={"agent": a})

if "--no-model" not in sys.argv:
    show("travel-agent asks for the full calendar (model narrows it)",
         c.post(f"{B}/request", json={"agent": "travel-agent",
                                      "request": "I need the full calendar to plan a 3-day trip in November"}))
show("travel-agent reads November events directly",
     c.post(f"{B}/query", json={"agent": "travel-agent", "operation": "calendar.events", "params": NOV}))
show("shopping-agent asks for bank transactions",
     c.post(f"{B}/query", json={"agent": "shopping-agent", "operation": "finance.transactions"}))
show("shopping-agent reads shopping preferences",
     c.post(f"{B}/query", json={"agent": "shopping-agent", "operation": "profile.preferences",
                                "params": {"category": "shopping"}}))
c.post(f"{B}/agents/shopping-agent/revoke")
show("shopping-agent after revocation",
     c.post(f"{B}/query", json={"agent": "shopping-agent", "operation": "profile.preferences",
                                "params": {"category": "shopping"}}))

ov = c.get(f"{B}/overview").json()
print("\ndigest:", ov["digest"])
print("pending:", [(e["agent"], e["category"]) for e in ov["escalations"]])
