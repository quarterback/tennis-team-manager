"""
Catch desynced universes back up to the rest of the world.

Every active division×gender universe is meant to advance together under
`world.advance_week`. The Season Hub's per-universe advance used to step ONE of
them on its own, which left the world clock and every other universe behind —
the rankings then compared a men's field 25 duals into its year against a
women's field that had played 12 and barely opened conference play. The route is
fixed; this repairs saves that already drifted.

It only plays the duals the lagging universes owe — the world week is untouched,
because the leading universe already consumed those weeks.

Usage:
    python3 scripts/resync_universes.py            # report the drift only
    python3 scripts/resync_universes.py --fix      # play the missing weeks
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.world as world


def _report() -> list[dict]:
    unis = world.universe_progress()
    if not unis:
        print("no active universes")
        return unis
    lead = max(u["key"] for u in unis)
    print(f"{'universe':<14} {'phase':<18} {'week':>6}   status")
    for u in sorted(unis, key=lambda x: x["key"], reverse=True):
        status = "level" if u["key"] == lead else "BEHIND"
        print(f"{u['division'] + ' ' + u['gender']:<14} {u['phase']:<18} "
              f"{u['week']:>3}/{u['total']:<3} {status}")
    return unis


def main() -> None:
    if not world.exists():
        print("no world in this save — nothing to sync")
        return
    unis = _report()
    if not unis:
        return
    if len({u["key"] for u in unis}) <= 1:
        print("\nall universes are in sync")
        return
    if "--fix" not in sys.argv:
        print("\nout of sync — re-run with --fix to play the missing weeks")
        return
    print("\nplaying the missing weeks (this takes a while)…")
    res = world.resync_universes()
    for uni, steps in sorted(res["stepped"].items()):
        print(f"  {uni}: advanced {steps} step(s)")
    if res["blocked"]:
        print("  held at the fall-portal barrier (commit it from /fall-portal): "
              + ", ".join(res["blocked"]))
    print(f"\nin sync: {res['in_sync']}")
    _report()


if __name__ == "__main__":
    main()
