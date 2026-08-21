#!/usr/bin/env python3
"""Write the association's name mapping into prep-network as plain text.

    python3 scripts/prep_network_name_map.py [--prep-network PATH]

‼️ WHY IT LIVES IN THE OTHER REPO. The tennis association renames a lot of
prep-network's institutions at emit, and prep-network keeps the published record
under the ORIGINAL names — the two disagree on purpose. Somebody reading a record
THERE and finding a different name in the tennis coverage has no way to know why,
and the authoritative tables are Python dicts in a repo they may not have open. So
the mapping is written out where the confusion happens, as text.

It is generated, not hand-kept, for the same reason `jhsaa_name_list.py` is: the
renames are an ongoing owner pass, and a mapping that lags the tables is worse than
no mapping. Re-run after any batch, alongside `jhsaa_name_list.py`.

‼️ THE FILE IS A REFERENCE, NOT AN INSTRUCTION. The prep-network sync is approved
but deferred, and when it runs it runs off `import_jhsaa.RENAMES` via
`scripts/rename_prep_network.py` — never by hand off this text.
"""
import argparse
import importlib.util
import io
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DATA = os.path.join(_REPO, "data", "jhsaa", "schools.json")
_OUT = os.path.join("docs", "JHSAA-name-map.txt")


def _import_jhsaa():
    spec = importlib.util.spec_from_file_location(
        "import_jhsaa", os.path.join(_HERE, "import_jhsaa.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(m, rows: list[dict], prep: dict) -> str:
    out = io.StringIO()
    w = out.write
    by_ident = {(r.get("source") or r["name"]): r for r in rows}

    w("JHSAA SCHOOL AND TOWN NAME CHANGES — the tennis association's mapping\n")
    w("=" * 78 + "\n")
    w("Generated from quarterback/tennis-team-manager by\n"
      "scripts/prep_network_name_map.py. Re-run after any rename batch.\n\n")
    w("WHAT THIS IS. The tennis association (the JHSAA) is built from THIS repo's\n"
      "institution records, and it renames a lot of them at emit. This repo keeps the\n"
      "published record under the ORIGINAL names, so the two disagree ON PURPOSE. This\n"
      "file is the mapping, written down so that anybody reading a record here and\n"
      "finding a different name in the tennis coverage knows why, and so the eventual\n"
      "sync has a plain-text reference that does not require reading Python.\n\n")
    w("IT IS NOT AN INSTRUCTION TO RENAME ANYTHING HERE. The sync is approved but\n"
      "deferred — see docs/NOTE-tennis-association-name-changes.md. When it is run it\n"
      "is run by scripts/rename_prep_network.py off the authoritative tables in the\n"
      "tennis repo, never by hand off this file.\n\n")
    w("  * SOURCE  — the name in records/orgs/schools.json\n"
      "  * BECOMES — the name the tennis association uses\n")

    # ‼️ THREE BUCKETS, NOT TWO — and the middle one is the whole reason this file is
    # worth writing. An earlier partial sync already renamed a chunk of THIS repo to the
    # tennis names, so for many entries the KEY is gone from here and the TARGET is what
    # the record is now called. Filing those as "source missing" would read as breakage;
    # they are done. The tennis side keeps the old key as the school's permanent
    # identity (its roster is generated from that string), so its rows stay correct.
    live, done, gone = [], [], []
    for k, v in sorted(m.RENAMES.items()):
        r = by_ident.get(k)
        disp = m._display_name(v)
        row = (k, disp, r["classification"] if r else "", r["city"] if r else "")
        if k in prep:
            live.append(row)
        elif disp in prep:
            done.append(row)
        else:
            gone.append(row)

    w("\n" + "=" * 78 + f"\nSCHOOLS — {len(live)} renames whose source record is still in this repo\n")
    w("=" * 78 + "\n")
    w(f"{'SOURCE':<46}{'BECOMES':<34}{'CLASS':<6}CITY\n")
    for k, disp, cl, city in live:
        w(f"{k:<46}{disp:<34}{cl:<6}{city}\n")

    if done:
        w("\n" + "=" * 78 + f"\nSCHOOLS — {len(done)} ALREADY ADOPTED HERE\n")
        w("=" * 78 + "\n")
        w("This repo is already calling these by the BECOMES name — an earlier partial\n"
          "sync landed them. Nothing to do. They are listed because the tennis side still\n"
          "keys on the old string as the school's permanent identity (its roster is\n"
          "generated from that string), so the pairing still has to be readable.\n\n")
        for k, disp, cl, city in done:
            w(f"{k:<46}{disp:<34}{cl:<6}{city}\n")

    if gone:
        w("\n" + "=" * 78 + f"\nSCHOOLS — {len(gone)} where neither name is in this repo\n")
        w("=" * 78 + "\n")
        w("Neither the source string nor the tennis name is a record here — this repo has\n"
          "renamed the school to some THIRD name, or the record has gone. Nothing to do,\n"
          "but these are the rows to look at first if the two repos ever need reconciling\n"
          "properly, because they are the ones no automated pass can pair up.\n\n")
        for k, disp, cl, city in gone:
            w(f"{k:<46}{disp:<34}{cl:<6}{city}\n")

    for label, table in (("TOWNS", m.CITY_RENAMES), ("AREAS", m.AREA_RENAMES)):
        w("\n" + "=" * 78 + f"\n{label} — {len(table)} renames\n" + "=" * 78 + "\n")
        for k, v in sorted(table.items()):
            w(f"{k:<46}{v}\n")

    w("\n" + "=" * 78 + "\nSUBSTITUTIONS — not renames\n" + "=" * 78 + "\n")
    w("A magnet school's TENNIS SEAT was given to its city's flagship. Both schools keep\n"
      "their own identity here; the magnet simply fields no tennis team, exactly as it\n"
      "would not in life. NOTHING in this repo changes for these.\n\n")
    for k, v in sorted(m.SUBSTITUTIONS.items()):
        w(f"{k:<46}seat -> {v}\n")

    w("\n" + "=" * 78 + "\nALSO ASSOCIATION-SIDE ONLY — nothing to sync\n" + "=" * 78 + "\n")
    w("  * LOCALITY — programs in the five big metros carry a settlement name (a CDP,\n"
      "    an unincorporated place, an absorbed town) beside their city. The CITY is\n"
      "    unchanged; the locality is a tennis-side field with no counterpart here.\n"
      "  * SPONSORSHIP — which schools field tennis is a decision the tennis repo makes\n"
      "    about its own association. A school joining or leaving it changes nothing in\n"
      "    these records.\n")
    return out.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep-network",
                    default=os.path.join(os.path.dirname(_REPO), "prep-network"))
    args = ap.parse_args()

    m = _import_jhsaa()
    with open(_DATA, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc["schools"] if isinstance(doc, dict) else doc
    src, _ = m._load(args.prep_network)
    prep = {s["name"] for s in src}

    dest = os.path.join(args.prep_network, _OUT)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    text = build(m, rows, prep)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {dest} ({text.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
