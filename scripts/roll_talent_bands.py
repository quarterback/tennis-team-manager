"""Write every JHSAA program's ROLLED talent tier into `data/jhsaa/talent_bands.json`.

The roll (`jhsaa.rolled_band`) is deterministic on the school name, so a school
missing from the file generates exactly what this writes — the file is the
RECORD the owner edits, not a different answer. Run once at ship, and again
after adding schools (existing assignments are kept; `--reroll` overwrites)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JHSAA_LAB_DEV_OVERRIDE", "1")


def main(reroll: bool = False) -> None:
    from app import jhsaa, overrides as ov
    ov.init_schema()
    programs = {} if reroll else dict(jhsaa._band_seed())
    amap = jhsaa._arch_map(ov.jhsaa_archetype_version())
    names = sorted({r["name"] for r in jhsaa.playup_rows()})
    added = 0
    for n in names:
        if n not in programs:
            programs[n] = jhsaa.rolled_band(n, amap.get(n, ""))
            added += 1
    jhsaa._write_band_doc(programs=programs)
    from collections import Counter
    print(f"{added} rolled, {len(programs)} assigned")
    for k, v in Counter(programs.values()).most_common():
        print(f"  {k:14s} {v}")


if __name__ == "__main__":
    main(reroll="--reroll" in sys.argv)
