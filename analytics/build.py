#!/usr/bin/env python3
"""Build the Clinch Report sidecar site.

Usage:
    python3 build.py                          # rebuild from everything ingested
    python3 build.py export1.zip export2.zip  # ingest new exports, then rebuild
    python3 build.py --latest 2               # render only the newest 2 seasons
    python3 build.py --years 2038-2039        # render only these years
    python3 build.py --no-player-pages        # skip per-player pages (88% of the site)

Drop research-export zips (from the game's /research/export page) anywhere and
pass their paths here. Ingested data is cached under analytics/data/ so you
only need to re-pass a zip if you're re-exporting a season that changed.

‼️ INGESTING AND RENDERING ARE SEPARATE, and at fourteen seasons that matters.
The cache is the almanac: every season you have ever ingested stays in
analytics/data/ whatever you render, and it costs a few MB of CSV. The SITE is
what gets big, because it is O(seasons x entities) and one season-gender alone
renders ~13,500 player pages at ~221 MB — 88% of a 250 MB build. Fourteen years
of both genders is several GB and will fill a disk.

So render the seasons you are actually working on. `--latest 2` is the useful
default for market work: it is the smallest window that still has the
season-over-season diffs, because MOVEMENT and DEVELOPMENT are differences
between CONSECUTIVE years — render one season alone and every transfer and
growth number is legitimately blank, since there is no prior year on screen to
diff against. Nothing is lost from the cache; re-run without the flag whenever
you want the whole almanac back.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ptc_analytics import ingest, render


def _parse_years(spec: str) -> set[int]:
    """'2039' / '2038-2039' / '2031,2038-2039' -> {years}."""
    years: set[int] = set()
    for part in spec.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            lo, _, hi = part.partition("-")
            years.update(range(int(lo), int(hi) + 1))
        else:
            years.add(int(part))
    return years


def select(bundles: list[dict], years: set[int] | None,
           latest: int | None, gender: str | None) -> list[dict]:
    """Narrow the ingested cache to the seasons worth rendering.

    `--latest N` counts the newest N years PER GENDER, not the newest N
    bundles: a year is two bundles when both genders are ingested, so counting
    bundles would silently give you one gender's last two years and the other's
    none."""
    out = list(bundles)
    if gender:
        out = [b for b in out if b["scope"].get("gender") == gender]
    if years:
        out = [b for b in out if int(b["scope"]["year"]) in years]
    if latest:
        keep: set[tuple] = set()
        by_gender: dict[str, set] = {}
        for b in out:
            by_gender.setdefault(b["scope"].get("gender", ""), set()).add(int(b["scope"]["year"]))
        for g, yrs in by_gender.items():
            for y in sorted(yrs)[-latest:]:
                keep.add((g, y))
        out = [b for b in out if (b["scope"].get("gender", ""), int(b["scope"]["year"])) in keep]
    return out


def _size(path: Path) -> str:
    total = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024 or unit == "GB":
            return f"{total:.0f} {unit}" if unit == "B" else f"{total:.1f} {unit}"
        total /= 1024
    return ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="Build the Clinch Report from ingested research exports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="The cache keeps every season you ingest; these flags only "
               "control what gets RENDERED. See the module docstring.")
    ap.add_argument("zips", nargs="*", help="research-export zips to ingest first")
    ap.add_argument("--years", metavar="SPEC",
                    help="render only these years: 2039, 2038-2039, 2031,2038-2039")
    ap.add_argument("--latest", type=int, metavar="N",
                    help="render only the newest N years, per gender "
                         "(use 2 or more: movement and development need a prior year)")
    ap.add_argument("--gender", choices=("boys", "girls", "men", "women"),
                    help="render only this gender")
    ap.add_argument("--no-player-pages", action="store_true",
                    help="skip the per-player career pages — they are ~88%% of the "
                         "site's size; names render unlinked and everything else stays")
    args = ap.parse_args(argv)

    for path in args.zips:
        keys = ingest.ingest_zip(path)
        for key in keys:
            print(f"ingested {path} -> data/{key}")

    cached = ingest.all_bundles()
    if not cached:
        print("No data ingested yet. Pass one or more research-export zip paths.")
        return 1

    years = _parse_years(args.years) if args.years else None
    bundles = select(cached, years, args.latest, args.gender)
    if not bundles:
        print(f"Nothing to render: {len(cached)} season(s) cached, none matched that "
              f"selection. Cached seasons:")
        for b in cached:
            print(f"  - {b['scope']}")
        return 1

    # ‼️ Say what was left out. A shorter site that does not explain itself is
    # the same trap as a silently capped list: it reads as "this is what there
    # is" when it is "this is what you asked for".
    skipped = len(cached) - len(bundles)
    if skipped:
        print(f"rendering {len(bundles)} of {len(cached)} cached season(s); "
              f"{skipped} left out of the SITE but kept in the cache")
    if args.no_player_pages:
        print("skipping per-player career pages (--no-player-pages)")

    render.build_site(bundles, player_pages=not args.no_player_pages)
    print(f"built site/ from {len(bundles)} season(s):")
    for b in bundles:
        print(f"  - {b['manifest']['dataset_family']} {b['scope']}")

    site = Path(render.SITE)
    print(f"\nsite is {_size(site)}"
          + (f" · players/ is {_size(site / 'players')} of it"
             if (site / "players").exists() and any((site / "players").iterdir()) else ""))
    print(f"Open {site / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
