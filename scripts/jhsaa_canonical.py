#!/usr/bin/env python3
"""The canonical JHSAA history (owner request 2026-09): freeze the lab save's
simmed decades as THE association's past — backdated so the final played season
renders as 2026-27 — and start fresh runs FROM that snapshot, each with fresh
match dice, so every future diverges while the canonical past never moves.

Two commands, both read-only without --apply (the integrate_lab_world idiom):

    python3 scripts/jhsaa_canonical.py freeze            # preflight
    python3 scripts/jhsaa_canonical.py freeze --apply
        Backdate the lab save (display offset = its world year, so the newest
        archived season shows as 2027 and the history reads behind it), then
        snapshot it to ~/.tennis-team-manager/jhsaa_canonical.db. One-time;
        refuses to overwrite an existing canonical file.

    python3 scripts/jhsaa_canonical.py new-run           # preflight
    python3 scripts/jhsaa_canonical.py new-run --apply
        Move the current lab database aside (timestamped — NEVER deleted),
        restore the canonical snapshot to ~/.tennis-team-manager/jhsaa_lab.db,
        and stamp a fresh per-run dice salt (`jhsaa.RUN_SALT_SETTING`). New
        seasons then re-roll their match dice while every roster, pid, name and
        archived season stays identical to the canonical past.

Run with the lab server STOPPED — this swaps the file a live process holds open.
Continuing the CURRENT run needs nothing from here: just keep advancing on the
lab page; freeze once, whenever the history is worth keeping.

‼️ Every copy is the SQLite backup API, never a file copy: under WAL, committed
rows live in the -wal sidecar until a checkpoint, so a plain copy can hand the
target fewer archive rows than the preflight just reported.
"""
from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
import sys

LAB_DB = os.path.abspath(os.path.expanduser("~/.tennis-team-manager/jhsaa_lab.db"))
CANONICAL_DB = os.path.abspath(
    os.path.expanduser("~/.tennis-team-manager/jhsaa_canonical.db"))
BASE = 2026        # world.BASE_YEAR; not imported so the preflight never binds
#                    app.world to a database path


def _inspect(path: str):
    """One world row + archive shape, read-only. Returns (world, max_idx, n_years,
    offset, run_salt) or exits with a message."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM world ORDER BY id")]
        arch = conn.execute(
            "SELECT MAX(year) y, COUNT(DISTINCT year) n FROM world_jhsaa").fetchone()
        try:
            cfg = {r["key"]: r["value"] for r in conn.execute(
                "SELECT key, value FROM world_setting")}
        except sqlite3.OperationalError:
            cfg = {}
    finally:
        conn.close()
    if len(rows) != 1:
        print(f"‼️ expected exactly ONE world row in {path}, found {len(rows)} — "
              "run scripts/cleanup_stray_worlds.py against it first.")
        raise SystemExit(1)
    off = int(cfg.get("display_year_offset") or 0)
    return rows[0], arch["y"], arch["n"], off, (cfg.get("jhsaa_run_salt") or "")


def _backup(src: str, dst: str) -> None:
    with sqlite3.connect(f"file:{src}?mode=ro", uri=True) as sconn, \
         sqlite3.connect(dst) as dconn:
        sconn.backup(dconn)
    sconn.close(); dconn.close()


def _bind(path: str):
    """Bind the app to `path` and import world — AFTER every read-only preflight."""
    # TENNIS_DB_PATH alone — deliberately NOT JHSAA_LAB_MODE, whose canonical-path
    # invariant fails closed on a --lab override; resolve_db_path honours the env
    # either way and nothing here needs a lab-mode route.
    os.environ["TENNIS_DB_PATH"] = path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app import world as wd
    return wd


def freeze(args) -> int:
    if not os.path.exists(args.lab):
        print(f"‼️ lab database not found: {args.lab}")
        return 1
    if os.path.exists(args.canonical):
        print(f"‼️ canonical snapshot already exists: {args.canonical} — refusing "
              "to overwrite the frozen history. Move it aside by hand if you "
              "really mean to re-freeze.")
        return 1
    w, max_idx, n_years, off, rs = _inspect(args.lab)
    season = BASE + w["year"] + 1
    print(f"lab world: seed {w['seed']}, year {w['year']} (JHSAA season {season}), "
          f"salt {w.get('salt') or '(none)'}; {n_years} season(s) archived, "
          f"newest index {max_idx}; display offset {off}, run salt "
          f"{rs or '(none)'}")
    if max_idx is not None and max_idx != w["year"]:
        print(f"‼️ archive newest index {max_idx} != world year {w['year']} — "
              "finish or replay the lab season before freezing.")
        return 1
    target_off = w["year"]
    if off and off != target_off:
        print(f"‼️ lab save already carries display offset {off} — refusing to "
              "restack a backdate. This save was frozen or integrated before.")
        return 1
    print(f"plan: set display offset {target_off} on the lab save (newest season "
          f"{season} renders as {season - target_off}, the history from "
          f"{BASE + 1 - target_off} behind it), then snapshot → {args.canonical}.")
    if not args.apply:
        print("read-only preflight — re-run with --apply to freeze.")
        return 0
    wd = _bind(args.lab)
    wd.set_display_offset(target_off)
    print(f"display offset {target_off} set on {args.lab}.")
    print("snapshotting (SQLite backup API) …")
    _backup(args.lab, args.canonical)
    print(f"done: canonical history frozen at {args.canonical} — "
          f"{n_years} seasons, displayed {BASE + 1 - target_off}–{season - target_off}. "
          "Keep advancing the lab to continue this run; "
          "`new-run --apply` starts a fresh future from this snapshot.")
    return 0


def _free_aside(lab: str, stamp: str) -> str:
    """A destination for the kept run that overwrites NOTHING. `os.rename`
    replaces an existing file on POSIX, so two `new-run --apply` calls landing
    on the same second — or a leftover archive with that name — would silently
    delete a previously preserved run. Probe the db name AND its -wal/-shm
    sidecars and take the first fully-free candidate."""
    n = 0
    while True:
        cand = f"{lab}.{stamp}" + (f"-{n}" if n else "")
        if not any(os.path.exists(cand + sfx) for sfx in ("", "-wal", "-shm")):
            return cand
        n += 1


def new_run(args) -> int:
    if not os.path.exists(args.canonical):
        print(f"‼️ no canonical snapshot at {args.canonical} — run `freeze --apply` "
              "first.")
        return 1
    w, max_idx, n_years, off, _ = _inspect(args.canonical)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_salt = args.run_salt or f"run-{stamp}"
    aside = _free_aside(args.lab, stamp) if os.path.exists(args.lab) else None
    print(f"canonical: world year {w['year']}, {n_years} season(s), display offset "
          f"{off} (newest season shows as {BASE + w['year'] + 1 - off}).")
    print(f"plan: {'move current lab db aside to ' + aside + ', then ' if aside else ''}"
          f"restore canonical → {args.lab}, stamp run salt {run_salt!r}.")
    if not args.apply:
        print("read-only preflight — re-run with --apply to start the new run.")
        return 0
    if aside:
        # NEVER delete a save. Move the -wal/-shm sidecars WITH the file, or a
        # stale WAL left beside the restored database would be replayed into the
        # NEW file on first open — silent corruption of both universes.
        os.rename(args.lab, aside)
        for suffix in ("-wal", "-shm"):
            if os.path.exists(args.lab + suffix):
                os.rename(args.lab + suffix, aside + suffix)
        print(f"previous run kept at {aside}")
    print("restoring canonical (SQLite backup API) …")
    _backup(args.canonical, args.lab)
    wd = _bind(args.lab)
    from app import worldconfig
    from app import jhsaa
    worldconfig.set(jhsaa.RUN_SALT_SETTING, run_salt)
    print(f"done: {args.lab} is the canonical history again ({n_years} seasons, "
          f"newest displayed {BASE + w['year'] + 1 - off}), run salt {run_salt!r} "
          "stamped. New seasons advanced from the lab page roll fresh match dice "
          "on the SAME programs and players — the canonical past never changes.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["freeze", "new-run"])
    ap.add_argument("--lab", default=LAB_DB,
                    help=f"lab database (default {LAB_DB})")
    ap.add_argument("--canonical", default=CANONICAL_DB,
                    help=f"canonical snapshot file (default {CANONICAL_DB})")
    ap.add_argument("--run-salt", default=None,
                    help="new-run only: the per-run dice salt to stamp "
                         "(default run-<UTC timestamp>)")
    ap.add_argument("--apply", action="store_true",
                    help="act; without it, report only")
    args = ap.parse_args()
    return freeze(args) if args.cmd == "freeze" else new_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
