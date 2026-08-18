#!/usr/bin/env python3
"""Build the Clinch Report sidecar site.

Usage:
    python3 build.py                          # rebuild from everything already ingested
    python3 build.py export1.zip export2.zip  # ingest new exports, then rebuild

Drop research-export zips (from the game's /research/export page) anywhere
and pass their paths here. Ingested data is cached under analytics/data/ so
you only need to re-pass a zip if you're re-exporting a season that changed;
`build` with no args just re-renders the site from whatever's already cached.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ptc_analytics import ingest, render


def main(argv: list[str]) -> int:
    for path in argv:
        key = ingest.ingest_zip(path)
        print(f"ingested {path} -> data/{key}")

    bundles = ingest.all_bundles()
    if not bundles:
        print("No data ingested yet. Pass one or more research-export zip paths.")
        return 1

    render.build_site(bundles)
    print(f"built site/ from {len(bundles)} season(s):")
    for b in bundles:
        print(f"  - {b['manifest']['dataset_family']} {b['scope']}")
    print(f"\nOpen {Path(__file__).resolve().parent / 'site' / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
