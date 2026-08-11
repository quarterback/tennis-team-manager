#!/usr/bin/env python3
"""
Build the state of Jefferson's college footprint: ~37 programs across D1-D4.

Jefferson is the fictional West Coast state imported by `scripts/import_jefferson.py`
(see that script and docs/AAR-jefferson-state-integration.md). Its 17.6M people had
no colleges. This script gives it a footprint sized like California's — ~2.0
programs per million — through TWO distinct moves that must not be confused:

  ABSORB   Jefferson's 20 counties stand on real ground, and real programs stand on
           that ground. When the state secedes it takes them: Nevada (Reno, Washoe
           County) becomes Galena University, Oregon Tech (Klamath Falls) becomes
           Cascade Polytechnic, Southern Oregon (Ashland) becomes Siskiyou, Cal Poly
           Humboldt (Arcata) becomes Humboldt Polytechnic, College of Idaho
           (Caldwell, Canyon County) becomes the College of Jefferson. These are
           RENAMES of the same institution, so each keeps its own logo — that is how
           Galena keeps the Wolf Pack lineage honestly rather than borrowing a mark.

  RELOCATE Three of the ten fictional Cal State campuses of the Golden State
           Athletic Association move to Jefferson and are renamed. Only three: the
           GSAA was built to fill a D3 California hole (CA went 5 -> 20 in
           docs/AAR-western-sky-seas-conference-split.md) and emptying it would undo
           that. The seven that stay carry unmistakably Southern-California place
           names; the three that move had generic western ones. The small-state
           seeds from that same pass — Dean (WY), Elms (NV), Lasell (AK), Talladega
           (VI), Judson (NV), Voorhees (GU), Fontbonne (WY) — are NEVER touched:
           they exist to keep those states on the map.

Everything else is net-new. Two new conferences are created (D1 `JVC`, D3 `JAA`) and
one D2 (`JCC`); the absorbed programs move into them, which shrinks GNAC-D2 15->13
and CCAA 12->10. No existing conference is renamed and no existing program is
displaced — deliberately, so the blast radius stays inside Jefferson.

Idempotent: re-running is a no-op. Run `--dry-run` first; it prints the full plan.

    python3 scripts/build_jefferson_colleges.py --dry-run
    python3 scripts/build_jefferson_colleges.py
    python3 scripts/make_badges.py        # draws the net-new programs' marks

AFTER RUNNING, the Python rating tables in app/ncaa.py must be hand-edited — this
script PRINTS the exact lines to paste. Those tables are curated, never machine
written. See the "PASTE INTO app/ncaa.py" section of the output.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_NCAA = os.path.join(_REPO, "data", "ncaa")
_LOGO_DIR = os.path.join(_REPO, "app", "web", "static", "logos")

# --- Conferences -------------------------------------------------------------
# abbr -> (division, display name). Abbrs must be unique across ALL divisions.
CONFS = {
    "JVC": ("D2", "Jefferson Valley Conference"),
    "JCC": ("D2", "Jefferson Collegiate Conference"),
    "JAA": ("D3", "Jefferson Athletic Association"),
}

# --- The programs ------------------------------------------------------------
# Each entry: school, city, conference abbr, and one origin:
#   "new"                  net-new program (gets a generated badge)
#   {"rename": "Old"}      an existing program renamed in place (keeps its logo)
#   {"reuse": "Donor"}     net-new, but wearing a copy of a live program's mark
# `move` is the destination conference when a renamed program also changes league.
PROGRAMS: list[dict] = [
    # ---- D1 (12) -----------------------------------------------------------
    # Eleven form the new Jefferson Valley Conference; Galena renames Nevada
    # inside the Mountain West, so no existing league changes size.
    # The flagship sits in the PAC-16, at `top` tier — a 17.6M state's flagship
    # funds like a blue blood. Owner decision: rather than rename the conference or
    # subsume anybody, Colorado State moves out to the Mountain West (where it
    # actually plays in real life, so the swap reads as a correction) and the Pac
    # stays at exactly 16. See MOVES below.
    {"school": "University of Jefferson", "city": "Ashbury", "div": "D1",
     "conf": "Pac-16", "meta": ("JU", "#043e7c")},
    {"school": "Jefferson State University", "city": "Mercer City", "div": "D1",
     "conf": "WAC", "meta": ("JSU", "#003167")},
    {"school": "University of Southern Jefferson", "city": "San Borondón", "div": "D1",
     "conf": "Big West", "meta": ("USJ", "#1d2b53")},
    {"school": "Jefferson A&M University", "city": "Rostova Junction", "div": "D1",
     "conf": "CUSA", "meta": ("JAMU", "#fcc624")},
    # ---- D2: the Jefferson Valley Conference (8) ---------------------------
    {"school": "Port Veles University", "city": "Port Veles", "div": "D2", "conf": "JVC"},
    {"school": "Belmonte State University", "city": "Belmonte", "div": "D2", "conf": "JVC"},
    {"school": "San Borondón State University", "city": "San Borondón", "div": "D2",
     "conf": "JVC"},
    {"school": "Valderra University", "city": "Valderra", "div": "D2", "conf": "JVC"},
    {"school": "Santa Michaela State University", "city": "Santa Michaela", "div": "D2",
     "conf": "JVC"},
    {"school": "Belyakov State University", "city": "Belyakov", "div": "D2", "conf": "JVC"},
    {"school": "Harriman State University", "city": "Harriman", "div": "D2", "conf": "JVC"},
    # Galena is NET-NEW and joins the MW, giving Jefferson one major-tier program.
    # It was briefly written as a rename of Nevada — Galena County is Washoe County,
    # so absorbing UNR looked geographically tidy. OWNER RULE, do not redo it: a real
    # FLAGSHIP is never subsumed. Jefferson may take the ground and it may take the
    # regional publics, but UNR keeps existing. Galena and Reno are simply two towns
    # on the same ground in different fictions.
    {"school": "Galena University", "city": "Galena", "div": "D2", "conf": "JVC"},

    # ---- D2 (14) — the new Jefferson Collegiate Conference ------------------
    {"school": "Cascade Polytechnic University", "city": "Redfork", "div": "D2",
     "conf": "JCC", "origin": {"rename": "Oregon Tech"}},        # Klamath Falls
    {"school": "Siskiyou University", "city": "Boyerstown", "div": "D2",
     "conf": "JCC", "origin": {"rename": "Southern Oregon"}},    # Ashland
    {"school": "Humboldt Polytechnic University", "city": "Puerto de los Reyes",
     "div": "D2", "conf": "JCC", "origin": {"rename": "Cal Poly Humboldt"}},  # Arcata
    {"school": "Bidwell State University", "city": "Lake Esperanza", "div": "D2",
     "conf": "JCC", "origin": {"rename": "Chico State"}},
    {"school": "Cedarport State University", "city": "Cedarport", "div": "D2", "conf": "JCC"},
    {"school": "Montelago State University", "city": "Montelago", "div": "D2", "conf": "JCC"},
    {"school": "Redfork State University", "city": "Redfork", "div": "D2", "conf": "JCC"},
    {"school": "Newark River University", "city": "Newark River", "div": "D2", "conf": "JCC"},
    {"school": "Wales City University", "city": "Wales City", "div": "D2", "conf": "JCC"},
    {"school": "Orellana State University", "city": "Orellana", "div": "D2", "conf": "JCC"},
    {"school": "Moriarty State University", "city": "Moriarty", "div": "D2", "conf": "JCC"},
    {"school": "Cortland State University", "city": "Cortland", "div": "D2", "conf": "JCC"},
    {"school": "University of the High Desert", "city": "Millport", "div": "D2", "conf": "JCC"},
    {"school": "Jefferson Maritime University", "city": "Port Meridian", "div": "D2",
     "conf": "JCC"},

    # ---- D3 (8) — the new Jefferson Athletic Association --------------------
    # Three are the relocated Golden State campuses (they keep their badges).
    {"school": "Copper Lake College", "city": "Copper Lake", "div": "D3", "conf": "JAA",
     "origin": {"rename": "Cal State Redwood Coast"}},
    {"school": "St. Varian College", "city": "St. Varian", "div": "D3", "conf": "JAA",
     "origin": {"rename": "Cal State Sierra"}},
    {"school": "Averill College", "city": "Averill", "div": "D3", "conf": "JAA",
     "origin": {"rename": "Cal State High Desert"}},
    {"school": "Fort Meriwether College", "city": "Fort Meriwether", "div": "D3", "conf": "JAA"},
    {"school": "Madrigal College", "city": "Madrigal", "div": "D3", "conf": "JAA"},
    {"school": "Altamonte College", "city": "Altamonte", "div": "D3", "conf": "JAA"},
    {"school": "Serrano College", "city": "Serrano", "div": "D3", "conf": "JAA"},
    {"school": "Los Robles College", "city": "Los Robles", "div": "D3", "conf": "JAA"},
    # Fontbonne was a Pacific Frontier relocation to Jackson WY; the owner took it
    # for Jefferson. Wyoming keeps Dean (D3, Cheyenne), so the state stays on the
    # D3 map. Fontbonne is a Sisters-of-St-Joseph college, hence a saint-named town.
    {"school": "Santa Laura College", "city": "Santa Laura", "div": "D3", "conf": "JAA",
     "origin": {"rename": "Fontbonne"}},

    # ---- D4 (3) — Jefferson's academic tier, joining the NWC ----------------
    # Caldwell ID sits in Canyon County = Jefferson's Halbrook County. "College of
    # Idaho" -> "College of Jefferson" mirrors the real College of Idaho /
    # University of Idaho pair, which is why both names can coexist here.
    {"school": "College of Jefferson", "city": "Halbrook", "div": "D4", "conf": "NWC",
     "origin": {"rename": "College of Idaho"}},
    {"school": "Ashbury College", "city": "Ashbury", "div": "D4", "conf": "NWC"},
    {"school": "New Leiden College", "city": "New Leiden", "div": "D4", "conf": "NWC"},
    # Carroll (MT), taken for Jefferson by owner decision. Note the cost, which is
    # real: Montana had exactly one D4 program and now has none. Carroll is a
    # Catholic liberal-arts college, so it keeps that character here.
    {"school": "Aurelia College", "city": "Aurelia", "div": "D4", "conf": "NWC",
     "origin": {"rename": "Carroll (MT)"}},
]

STATE = "JF"
_GENDERS = ("men", "women")

# --- Conference moves for EXISTING programs (no rename, no relocation) --------
# Jefferson's flagship joins the Pac-16 at `top` tier, and rather than rename the
# conference (its abbr is a key in CONF_PRESTIGE, CONF_TIER, web/state.py::_P5 and
# polls.py::_POWER_CONFS) or delete anybody, one member steps out so the Pac stays
# at 16. Colorado State to the Mountain West is where it plays in real life, so
# this reads as a correction rather than a demotion.
MOVES = [
    {"school": "Colorado State", "div": "D1", "from": "Pac-16", "to": "MW"},
]


def _slug(school: str) -> str:
    """Match the slug convention already in data/ncaa/logos.json ("TCU" -> "tcu",
    "NC State" -> "nc-state")."""
    s = re.sub(r"[^a-z0-9]+", "-", school.lower()).strip("-")
    return re.sub(r"-+", "-", s)


def _load(name: str) -> dict:
    with open(os.path.join(_NCAA, name), encoding="utf-8") as fh:
        return json.load(fh)


def _save(name: str, data: dict, *, sort_keys: bool = False) -> None:
    with open(os.path.join(_NCAA, name), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(data, indent=2, ensure_ascii=False,
                            sort_keys=sort_keys) + "\n")


def _insert_sorted(mapping: dict, key: str, value) -> dict:
    """`mapping[key] = value`, placed before the first existing key that sorts
    after it. Keeps an already-ordered map ordered without re-sorting the rest."""
    if key in mapping:
        mapping[key] = value
        return mapping
    out: dict = {}
    placed = False
    for k, v in mapping.items():
        if not placed and k > key:
            out[key] = value
            placed = True
        out[k] = v
    if not placed:
        out[key] = value
    return out


def _conf_of(div_data: dict, abbr: str) -> dict | None:
    for c in div_data["conferences"]:
        if c["abbr"] == abbr:
            return c
    return None


def _drop_team(div_data: dict, school: str) -> str | None:
    """Remove `school` from whatever conference holds it. Returns that abbr."""
    for c in div_data["conferences"]:
        if school in c["teams"]:
            c["teams"].remove(school)
            return c["abbr"]
    return None


def plan() -> list[str]:
    """Human-readable summary, also the dry-run output."""
    out, by_div = [], {}
    for mv in MOVES:
        out.append(f"\nmove  {mv['school']} ({mv['div']}) {mv['from']} -> {mv['to']}")
    for p in PROGRAMS:
        by_div.setdefault(p["div"], []).append(p)
    for div in ("D1", "D2", "D3", "D4"):
        rows = by_div.get(div, [])
        out.append(f"\n{div} — {len(rows)} Jefferson programs")
        for p in rows:
            o = p.get("origin")
            if isinstance(o, dict) and "rename" in o:
                tag = f"absorb {o['rename']}"
            elif isinstance(o, dict) and "reuse" in o:
                tag = f"net-new, mark from {o['reuse']}"
            else:
                tag = "net-new, badge"
            out.append(f"    {p['school']:36} {p['city']:22} {p['conf']:5} ({tag})")
    return out


def apply_changes(dry: bool) -> None:
    locations = _load("locations.json")
    logos = _load("logos.json")
    divisions = {(d, g): _load(f"{d.lower()}_{g}.json")
                 for d in ("d1", "d2", "d3", "d4") for g in _GENDERS}
    notes: list[str] = []

    # Conference moves first, so a vacated seat exists before the Jefferson program
    # that replaces it is inserted.
    for mv in MOVES:
        for g in _GENDERS:
            data = divisions[(mv["div"].lower(), g)]
            dest = _conf_of(data, mv["to"])
            if dest is None:
                notes.append(f"  ! {mv['to']} missing in {mv['div']} {g}")
                continue
            if mv["school"] in dest["teams"]:
                continue                              # already moved (re-run)
            if _drop_team(data, mv["school"]) is None:
                notes.append(f"  ! {mv['school']} not found in {mv['div']} {g}")
                continue
            dest["teams"].append(mv["school"])
            dest["teams"].sort()

    for p in PROGRAMS:
        school, div, conf = p["school"], p["div"], p["conf"]
        origin = p.get("origin") or {}
        old = origin.get("rename")
        donor = origin.get("reuse")

        # RELOCATE, don't duplicate. This table is the source of truth for where a
        # Jefferson program plays, and it gets edited — the JVC moved D1 -> D2 and
        # Galena swapped down into it. Without dropping the school from wherever it
        # currently sits first, a re-run would ADD it to its new conference and leave
        # the old copy behind, so the program would exist in two divisions at once.
        # "Idempotent" has to mean "converges on the table", not "only ever inserts".
        for g in _GENDERS:
            for (d, gg), data in divisions.items():
                if gg != g or (d == div.lower() and _conf_of(data, conf)
                               and school in (_conf_of(data, conf) or {}).get("teams", ())):
                    continue
                if _drop_team(data, school) is not None:
                    notes.append(f"  ~ moved {school} out of {d.upper()} {g}")

        for g in _GENDERS:
            data = divisions[(div.lower(), g)]
            if old:
                # A renamed program may also be changing league; drop it wherever
                # it currently sits, in this division's file for this gender.
                if _drop_team(data, old) is None and school not in _flat(data):
                    notes.append(f"  ! {old} ({div} {g}) not found — skipped")
                    continue
            dest = _conf_of(data, conf)
            if dest is None:
                if conf not in CONFS:
                    notes.append(f"  ! conference {conf} missing in {div} {g}")
                    continue
                dest = {"name": CONFS[conf][1], "abbr": conf,
                        "autobid": True, "teams": []}
                data["conferences"].append(dest)
            if school not in dest["teams"]:
                dest["teams"].append(school)
                dest["teams"].sort()

        # locations: the program is in Jefferson now. Insert in alphabetical
        # position rather than appending or re-sorting the whole map — the file is
        # already near-alphabetical, and a global sort would bury 37 real additions
        # under 500 lines of reordering.
        if old:
            locations["schools"].pop(old, None)
        locations["schools"] = _insert_sorted(
            locations["schools"], school, {"city": p["city"], "state": STATE})

        # logos
        if old:
            # Same institution under a new name — it keeps its own art (that is how
            # Galena keeps the Wolf Pack mark honestly). Recording the origin keeps
            # the provenance greppable.
            # Idempotency matters here: on a re-run `old` is already gone, and
            # rebuilding the entry from scratch would mint a fresh slug pointing at
            # a PNG that was never drawn. If the new name already resolves, leave it.
            inherited = logos.pop(old, None)
            if school not in logos:
                entry = dict(inherited or {})
                entry.pop("espn_id", None)   # the id belongs to the old identity
                entry.setdefault("slug", _slug(school))
                entry["logo_source"] = f"rename:{old}"
                logos[school] = entry
        elif donor:
            # Deliberate mark reuse. COPY the art to a new slug — never share a
            # slug and never copy the donor's espn_id, or the logo collision pass
            # flags the real owner as the loser. The donor is left untouched.
            dslug = (logos.get(donor) or {}).get("slug")
            nslug = _slug(school)
            if dslug and not dry:
                src = os.path.join(_LOGO_DIR, f"{dslug}.png")
                if os.path.exists(src):
                    shutil.copyfile(src, os.path.join(_LOGO_DIR, f"{nslug}.png"))
                else:
                    notes.append(f"  ! donor art missing: {src}")
            logos[school] = {"slug": nslug, "logo_source": f"reuse:{donor}"}
        elif school not in logos:
            # Net-new: hand off to scripts/make_badges.py, which draws every entry
            # flagged `placeholder` and rewrites it as `badge: True`.
            logos[school] = {"slug": _slug(school), "placeholder": True}

    if dry:
        print("\n".join(notes) if notes else "  (no warnings)")
        print("\n--dry-run: nothing written")
        return

    # Conference ORDER is meaningful in these files (power leagues first), so new
    # conferences are appended and the existing order is never re-sorted. Team
    # lists inside a conference ARE alphabetical, and so is locations.schools —
    # keep both, or the diff buries the real change.
    for (d, g), data in divisions.items():
        _save(f"{d}_{g}.json", data)
    _save("locations.json", locations)
    _save("logos.json", logos, sort_keys=True)
    print("\n".join(notes) if notes else "  (no warnings)")
    print(f"\nwrote data/ncaa/*.json  ({len(PROGRAMS)} Jefferson programs)")


def _flat(div_data: dict) -> set[str]:
    return {t for c in div_data["conferences"] for t in c["teams"]}


def paste_block() -> str:
    """The curated app/ncaa.py table lines. Printed, never written — those tables
    are hand-maintained (a machine rewrite would lose their comments)."""
    meta = [(p["school"], *p["meta"]) for p in PROGRAMS if p.get("meta")]
    lines = [
        "",
        "=" * 72,
        "PASTE INTO app/ncaa.py — curated tables, edit by hand",
        "=" * 72,
        "",
        "# CONF_PRESTIGE (D1 abbr-keyed) — add:",
        '    "JVC": 0.56,',
        "",
        "# CONF_TIER — add. Drives the recruiting budget band; an unregistered D1",
        '# conference silently defaults to "low" (the 6-7 floor).',
        '    "JVC": "mid",',
        "",
        "# CONF_PRESTIGE_D2 (NAME-keyed) — add:",
        '    "Jefferson Collegiate Conference": 0.42,',
        "# CONF_PRESTIGE_D2_ALIASES — add (abbr -> name):",
        '    "JCC": "Jefferson Collegiate Conference",',
        "",
        "# CONF_PRESTIGE_D3 (NAME-keyed) — add:",
        '    "Jefferson Athletic Association": 0.44,',
        "# CONF_PRESTIGE_D3_ALIASES — add:",
        '    "JAA": "Jefferson Athletic Association",',
        "",
        "# SCHOOL_META — pin the crests. Without these the fallback initialises",
        '# "University of Southern Jefferson" to "UOSJ".',
    ]
    lines += [f'    "{s}": ("{a}", "{c}"),' for s, a, c in meta]
    lines += [
        "",
        "# PRESTIGE_SCHOOLS — the flagship and the land-grant HBCU:",
        '    "University of Jefferson": 0.12,',
        '    "Jefferson A&M University": 0.13,',
        "",
        "# ACADEMIC_SCHOOLS — the D4 academic tier. recruit_economy.d4_academic_min",
        "# derives each D4's admissions gate from this; unset lands at 0.50 and",
        "# admits nearly anyone.",
        '    "College of Jefferson": 0.80,',
        '    "Ashbury College": 0.86,',
        '    "New Leiden College": 0.83,',
        "=" * 72,
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    print("\n".join(plan()))
    print()
    apply_changes(args.dry_run)
    print(paste_block())


if __name__ == "__main__":
    main()
