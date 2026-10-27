"""Admin CLI (stand-in for the dashboard).

  python -m gatekeeper.admin status
  python -m gatekeeper.admin approve <escalation_id> always|never|dismiss
  python -m gatekeeper.admin template strict|balanced|open
  python -m gatekeeper.admin rule deny financial [--agent NAME]
  python -m gatekeeper.admin connect|revoke <agent>
  python -m gatekeeper.admin ledger
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .core import Gatekeeper
from .store import Store

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    p = argparse.ArgumentParser(prog="gatekeeper.admin")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("ledger")
    a = sub.add_parser("approve"); a.add_argument("id"); a.add_argument("choice")
    t = sub.add_parser("template"); t.add_argument("name")
    r = sub.add_parser("rule"); r.add_argument("effect"); r.add_argument("category")
    r.add_argument("--agent", default="*")
    for name in ("connect", "revoke"):
        s = sub.add_parser(name); s.add_argument("agent")
    args = p.parse_args()

    gk = Gatekeeper(Store(os.getenv("GATEKEEPER_DB", str(ROOT / "gatekeeper.db"))))
    if args.cmd == "status":
        print("template:", gk.store.get_setting("template"))
        print("user rules:", [(r.id, r.effect.value, r.category, r.agents)
                              for r in gk.store.list_rules() if r.source == "user"])
        print("grants:", [(g["agent"], "revoked" if g["revoked"] else g["expires_at"].isoformat())
                          for g in gk.store.list_grants()])
        print("pending:", [(e["id"], e["agent"], e["category"], e["item_count"])
                           for e in gk.store.list_escalations()])
        print("digest:", json.dumps(gk.digest()))
    elif args.cmd == "ledger":
        for e in gk.store.ledger(20):
            print(json.dumps(e))
    elif args.cmd == "approve":
        print(gk.resolve_escalation(args.id, args.choice))
    elif args.cmd == "template":
        gk.apply_template(args.name); print("template ->", args.name)
    elif args.cmd == "rule":
        print(gk.add_user_rule(args.effect, args.category, agents=(args.agent,)))
    elif args.cmd == "connect":
        gk.connect_agent(args.agent); print("connected", args.agent)
    elif args.cmd == "revoke":
        gk.revoke_agent(args.agent); print("revoked", args.agent)


if __name__ == "__main__":
    main()
