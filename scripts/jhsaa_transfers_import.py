#!/usr/bin/env python3
"""Apply a CSV of JHSAA transfers as one offseason batch — the delegate-an-agent path.

    python3 scripts/jhsaa_transfers_import.py moves.csv [--year 2034] [--apply]

CSV rows are `pid, destination school` (a header row of pid/player_id is skipped;
the research export's `player_id` column is the same identifier). Default is a
DRY RUN that prints the full validation report and writes nothing; `--apply`
writes the valid rows through the same `set_jhsaa_transfer` records the player
card's form does — effective next season, applied at the rollover like every
transfer. Invalid rows are reported loudly and never block valid ones; the exit
code is non-zero whenever any row was rejected, so a driving agent can't miss it.

`--year` defaults to the season after the newest archived one — the ordinary
offseason move. Point `TENNIS_DB_PATH` at the save to operate on (defaults to
the repo's ./tennis.db, same as the app).
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="CSV of pid,destination (use - for stdin)")
    ap.add_argument("--year", type=int, default=None,
                    help="effective season (default: newest archived season + 1)")
    ap.add_argument("--apply", action="store_true",
                    help="write the valid rows (default: dry run, report only)")
    args = ap.parse_args()

    from app import jhsaa, world

    w = world.load_world(world.DEFAULT_SEED)
    year = args.year
    if year is None:
        if not w:
            sys.exit("No world in this database — pass --year explicitly.")
        latest = world.jhsaa_latest_season_year(w["id"], "girls") \
            or world.jhsaa_latest_season_year(w["id"], "boys")
        if latest is None:
            sys.exit("No archived JHSAA season — pass --year explicitly.")
        year = latest + 1
    salt = world.active_salt(world.DEFAULT_SEED) if w else ""

    fh = sys.stdin if args.csv == "-" else open(args.csv, encoding="utf-8")
    pairs = []
    with fh:
        for row in csv.reader(fh):
            if not row or not row[0].strip() or row[0].lstrip().startswith("#"):
                continue
            if row[0].strip().lower() in ("pid", "player_id"):
                continue
            pairs.append((row[0].strip(), row[1].strip() if len(row) > 1 else ""))
    if not pairs:
        sys.exit("No rows to process.")

    report = jhsaa.transfer_batch(pairs, year, salt, apply=args.apply)
    ok = sum(r["ok"] for r in report)
    for r in report:
        mark = "OK " if r["ok"] else "ERR"
        who = f"{r['name']} ({r['pid']})" if r["name"] else r["pid"]
        print(f"  {mark} {who:44} {r['from'] or '?':30} -> {r['to'] or '?':30} {r['msg']}")
    verb = "applied" if args.apply else "valid (dry run — nothing written)"
    print(f"{ok} of {len(report)} {verb}; effective season {year}")
    return 0 if ok == len(report) else 1


if __name__ == "__main__":
    sys.exit(main())
