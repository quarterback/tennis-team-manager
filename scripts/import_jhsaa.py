#!/usr/bin/env python3
"""
Build the JHSAA — Jefferson's high-school tennis association — from `prep-network`.

Writes `data/jhsaa/schools.json`: every Jefferson school that sponsors tennis, with its
classification, city/county/area, mascot, colours, and its DISTRICT for each gender.

Two things this does NOT do, deliberately:

  * It does not import prep-network's players. That repo supplies INSTITUTIONS; the
    season is played here by this engine with players generated here.
  * It does not inherit prep-network's `sports` flags for tennis. That generator rolled
    `boys-tennis` and `girls-tennis` independently per school, producing 202 boys teams
    against 441 girls and only 117 schools fielding both — 3A alone has 10 boys teams
    and 81 girls. It is an artifact, and it leaves the boys' season unschedulable (20
    one-team leagues). Sponsorship is re-derived below on the real-world pattern.

Sponsorship: girls-sponsoring is the SUPERSET, boys a ~88% subset of it. Schools that
field girls tennis but not boys are common; the reverse essentially does not happen.
Co-op programs are not modelled — single schools only.

Districts: prep-network's 99 conferences are all-sport geographic groupings and 92 of
them span classifications, so they shatter when filtered to one class and to tennis
sponsors. Tennis draws its own map the way Oregon does — balanced districts of <= 12 per
classification, geographically contiguous, named for their dominant area (falling through
to the dominant county when that area name is already used in the same classification).

Deterministic: seeded, so two runs are identical. Idempotent.

    python3 scripts/import_jhsaa.py [--prep-network ../prep-network] [--dry-run]

See docs/DESIGN-jhsaa-high-school-season.md.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_OUT_DIR = os.path.join(_REPO, "data", "jhsaa")
_OUT = os.path.join(_OUT_DIR, "schools.json")

SEED = 11
MAX_DISTRICT = 12

# Girls sponsorship rate by classification; boys is a subset of the girls sponsors.
# 2A and 1A are deliberately well above a realistic sponsorship rate (owner rule
# 2027-08). Splitting 3A-1A into two championships left 2A-1A with 18 programs and an
# 8-team state field — 44% of the classification making state, which is not a
# tournament. The fix the owner chose is more programs rather than a smaller field —
# and then MORE again: 2A/1A sponsor at rates no real state would post, because a
# huge, ragged small-school classification is the fun of it. The talent bands say
# what the level is; the roster count says how much of it there is to watch.
GIRLS_RATE = {"7A": 0.85, "6A": 0.70, "5A": 0.55, "4A": 0.35,
              "3A": 0.26, "2A": 0.78, "1A": 0.62}
BOYS_OF_GIRLS = 0.88

# Forced-in schools that field GIRLS tennis only. `always_sponsor()` puts a named
# school in for BOTH genders, which is right for nearly all of them; this is the
# exception list for the rare one that doesn't field a boys team (own-source fact,
# not a random draw the way an unforced girls-only program is). Girls-sponsoring
# being the superset (see the sponsorship note above) means there's no equivalent
# ALWAYS_BOYS_ONLY case to mirror.
ALWAYS_GIRLS_ONLY = {
    "St. Agnes Preparatory",
}

# Schools the owner wants in the association without giving them an archetype. The
# archetype seed list is folded in automatically — see `always_sponsor`.
ALWAYS_EXTRA = [
    "Abbey Prep",
    "Annie Springs",
    "Arrieta Treasure Valley",
    "Aurelia",
    "Bahía Leal",
    "Bahía Leal Costa Verde",    # → "Housatonic" in this association (RENAMES)
    "Baptist HS",
    "Beacon Hill",
    "Breakwater",
    "Calderwood School",
    "Caswell Depot High",
    "Central Christian",
    "Chaminade",
    "Commonwealth",
    "Condotti Vanguard Academy",
    "Cortland",
    "Crown Hill",
    "Dolores Huerta",
    "Dry Lake",
    "Eastmont Christian",
    "Echevarria Foundry High",
    "Elk Bluff",
    "Elk Crossing",
    "Emerson",
    "Ferris Union",
    "Fort Valois",
    "Gagarin School of Public Service",
    "Galena",
    "George Washington Carver",
    "Gold Hollow",
    "Gold Junction",
    "Golden Gate",
    "Gwendolyn Brooks",
    "Halfway House",
    "Harlan Cole",
    "Harrow",
    "Hazel Bennett",
    "High Prairie",
    "Homestead",
    "Jean Lindgren",
    "Keldale",
    "Las Norias",
    "Las Palmas",
    "Latgaway",
    "Lorraine Calder",
    "Mabryville",
    "Marlow County",
    "Mesa Dorada",
    "Montelago",
    "Netherwood",
    "New Leiden",
    "Newark River North",
    "North Valley Christian",
    "Owl Canyon",
    "Pacific Friends School",
    "Paul Robeson",
    "Pinecrest School",
    "Port Meridian Polytechnic",
    "Port Meridian West",
    "Providence Academy",
    "Puerto Gallego",
    "Ransom Spur",
    "Redwood Coast",
    "Romero-Finniski",
    "Sage Point",
    "Saint Francis",
    "San Borondón",
    "San Cordero",
    "San Tomás",
    "Santa Cruz del Norte",
    "Santa Laura",
    "Santa Laura North",
    "Seafarer High",
    "Selbyville",
    "Silver Glen",
    "Sisters of Mercy",
    "Snowline",
    "St. Agnes Academy",
    "St. Basil Academy",
    "St. Gabriel Preparatory",
    "St. Isidore",
    "St. Norbert Abbey",
    "St. Perpetua",
    "St. Sebastian Prep",
    "St. Vincent School",
    "Steelbridge",
    "Summervale Northwest",
    "Svenja Ekström",
    "Telfair",
    "Telfair Country Day School",
    "Three Saints",
    "Timberline",
    "Treasure Valley",
    "Trinity Catholic",
    "Twin Rivers",
    "Valderra",
    "Valley Christian",
    "Wales City",
    "Westover",
    "Westside Christian",
    "Winifred Booker",
]

# ABSORPTION-STYLE RENAMES (owner rule 2027-08) — the same pattern the college
# import uses for programs standing on Jefferson ground (Oregon Tech → Cascade
# Polytechnic): the INSTITUTION comes from prep-network, which stays untouched
# (its published record — seasons, titles, editorial — keeps the source name);
# the tennis association knows the school by the owner's name.
#
# ⚠️ Keyed by SOURCE name and applied ONLY when a row is emitted, never at load:
# the sponsorship dice in `sponsors()` are drawn positionally over the
# name-sorted school list, so renaming before the draw would shift every school
# between the two alphabetical positions onto its neighbour's roll and reshuffle
# a chunk of the association. Everything internal — forcing, dice, district
# drawing — runs on the source name; only the written row carries the new one.
RENAMES = {
    "Bahía Leal Costa Verde": "Housatonic",      # keeps its Warthogs
    "Belyakov Academy of Music and Media": "Belyakov North",
    "Belyakov Environmental Sciences Academy": "Belyakov South",
    "Belyakov I-50 Technical": "Belyakov East",
    "Belyakov Polytechnic Institute": "Belyakov West",
    "Belyakov School of Design and Engineering": "Theodore Roosevelt",
    "Belyakov School of Public Service": "Abraham Lincoln",
    "Belyakov School of Science and Industry": "Belyakov Technical",
    "Belmonte Agricultural Sciences Academy": "Belmonte North",
    "Belmonte Applied Sciences Institute": "Belmonte South",
    "Belmonte Civic Leadership Academy": "Belmonte East",
    "Belmonte Health Sciences Academy": "Belmonte West",
    "Belmonte Classical Academy": "James Madison",
    "Belmonte Technical Arts Academy": "Woodrow Wilson",
    "St. Basil School": "St. Ignatius",
    "Caswell Classical School": "Cherry Hill",
    "Caswell Depot High": "Cherry Hill North",
    "Caswell I-50 Technical": "Cherry Hill South",
    "Caswell School of Science and Industry": "Andrew Jackson",
    "Caswell University Prep": "Caswell West",
    "Aldecoa Academy of Arts and Letters": "Aldecoa North",
    "Aldecoa Applied Sciences Institute": "Aldecoa South",
    "Aldecoa Depot High": "Ulysses Grant",
    "Echevarria Foundry High": "Echevarria North",
    "Echevarria I-50 Technical": "Echevarria South",
    "Echevarria School of Commerce": "William McKinley",
    "Orellana Foundry High": "Orellana North",
    "Orellana School of Commerce": "Orellana South",
    "Eagleton School of Science and Industry": "Eagleton West",
    "Port Veles Agricultural Sciences Academy": "Port Veles North",
    "Port Veles Civic Leadership Academy": "Port Veles South",
    "Nadia Sidorov": "Anton Sidorov",
    "Port Meridian Polytechnic": "Port Meridian North",
    "San Borondón Agricultural Sciences Academy": "San Borondón North",
    "San Borondón Environmental Sciences Academy": "San Borondón South",
    "Puerto de los Reyes International School": "Puerto de los Reyes North",
    "Puerto de los Reyes School of Commerce": "Puerto de los Reyes South",
    "Llerena Civic Leadership Academy": "Llerena North",
    "Llerena School of Science and Industry": "Llerena South",
    "Javier Villalba": "Alonso Villalba",
    "Serrano Applied Sciences Institute": "Serrano North",
    "Serrano Depot High": "Serrano South",
    "Halbrook Technical": "Halbrook East",
    "Greaves Junction Treasure Valley": "Greaves Junction South",
    "Cortland Environmental Sciences Academy": "Cortland North",
    "Cortland Foundry High": "Harry S. Truman",
    "Valderra Aviation and Engineering Academy": "Valderra North",
    "Valderra Technical Arts Academy": "Dwight Eisenhower",
    "Mercer City Technical Arts Academy": "Mercer City North",
    "Montelago Agricultural Sciences Academy": "Montelago South",
    "Moriarty Foundry High": "Moriarty West",
    "Las Norias Foundry High": "Las Norias East",
    "Lake Esperanza School of Science and Industry": "Lake Esperanza North",
    "Harriman Civic Leadership Academy": "Harriman North",
    "Harriman Maritime Academy": "John F. Kennedy",
    "San Cordero Maritime Academy": "San Cordero North",
    "San Cordero School of Commerce": "San Cordero South",
    "Fort Valois School of Design and Engineering": "Fort Valois North",
    "Gagarin School of Public Service": "Gagarin East",
    "Fellows Mill International School": "Fellows Mill South",
    "Rye Academy of Arts and Letters": "Rye North",
    "Ansotegui Siding Commonwealth": "Ansotegui Siding North",
}

# ‼️ THE FLAGSHIP PLAYS THE SPORT (owner rule 2027-08). Nine cities had a MAGNET
# school in the tennis association while the plain city high school — which
# exists in prep-network and is usually the bigger, older school — sat out. That
# is backwards: an arts-and-letters academy or a polytechnic institute mostly
# does not field teams, and if a city sends one program to the state tournament
# it is the flagship. So these are SUBSTITUTIONS, not renames: the magnet's seat
# in the association is given to the bare-named school, which then plays under
# its OWN classification, enrollment, mascot and colours (they differ — Altamonte
# is 5A where its School of Commerce was 4A). Nothing is deleted; the magnet
# simply does not sponsor tennis, exactly as it would not in life.
#
# Applied AFTER the sponsorship draw for the same reason RENAMES is applied at
# emit: the dice are positional over the name-sorted list, so swapping names
# earlier would reshuffle everyone in between.
SUBSTITUTIONS = {
    "Altamonte School of Commerce": "Altamonte",
    "Bellacosta University Prep": "Bellacosta",
    "Calder Aviation and Engineering Academy": "Calder",
    "Copper Lake Academy of Music and Media": "Copper Lake",
    "Copperview Polytechnic Institute": "Copperview",
    "Fort Meriwether School of Public Service": "Fort Meriwether",
    "Mercer City School of Design and Engineering": "Mercer City",
    "Mount Horeb Academy of Arts and Letters": "Mount Horeb",
    "Puerto de los Reyes Civic Leadership Academy": "Puerto de los Reyes",
}


# Championship groups. 3A stands ALONE and 2A/1A combine (owner rule 2027-08): the
# enrollment gap across the old 3A-1A group was the widest in the association — medians
# of 1,043 / 385 / 199 — so a 1,370-student school and a 108-student one were competing
# for the same trophy.
# ⚠️ RECLASSIFICATION (owner rule 2027-08). prep-network's 2A holds 88 schools and its
# 1A 111, so a combined 2A-1A dwarfed 3A's 140 — 151 tennis sponsors against 46. States
# readjust their enrollment cutoffs all the time, and this is that: the largest 2A schools
# move up to 3A, which balances the two smallest championships without splitting 2A from
# 1A (the owner does not want separate 2A and 1A tennis).
#
# ⚠️ RECLASSIFICATION, ROUND 2 (owner rule, follow-up to 2027-08). 430 turned out to be
# above every 2A school's enrollment in the current pool (max 397) — the promotion never
# actually fired, so 3A stayed the association's smallest classification (60 sponsors)
# while 2A-1A stayed nearly as big as 7A (103 vs 105). Same fix, lower bar: pulling the
# line down to 300 promotes the top 15 of 2A's 31 schools, landing 3A at 75 (tied with
# 5A) and 2A-1A at 88 — no longer an outlier, now roughly level with 6A (89). Move the
# threshold again before reaching for a second lever (like sponsoring MORE 3A schools) —
# thinning 2A is the cheaper knob and it isn't tapped out yet (16 2A schools remain,
# enrollment 225-283).
#
# By ENROLLMENT, because that is what a classification IS. Nothing here looks at who
# sponsors tennis or at how good anybody is.
PROMOTE_2A_ABOVE = 300          # 2A schools at or above this enrollment become 3A


def reclassify(schools: list[dict]) -> int:
    moved = 0
    for s in schools:
        if s["classification"] == "2A" and s.get("enrollment", 0) >= PROMOTE_2A_ABOVE:
            s["classification"] = "3A"
            moved += 1
    return moved


_CANONICAL = {new: src for src, new in RENAMES.items()}   # display -> roster identity

# ⚠️ Display names carry NO institutional suffix (owner rule 2027-08: "you don't
# need to have HS or High School ever, or even 'School' because nobody uses it").
# Applied at EMIT, exactly like RENAMES: everything internal (dice, districts,
# identity) runs on the source name, and `School.source` keeps the pre-strip name
# so pids never move. Only the TAIL strips — "San Cordero School of Commerce"
# ends in "Commerce" and is untouched.
_SUFFIX_RE = re.compile(r"\s+(High School|HS|School)$", re.IGNORECASE)


# "School of X" collapses (owner rule 2027-08, sharpened twice: "you just say
# San Cordero Commerce or Plainfield Science", then "Jesuit Sacramento is
# exactly what it'd be called. Just like Chicago or Boston Latin"):
#   * SUBJECT of-phrases collapse to the first subject — "Calder Science",
#     "Bronx Science" ("Science and Industry" truncates at "and").
#   * PLACE of-phrases collapse too — "Jesuit Sacramento", "Wilmington Charter".
#     ORDER follows usage: normally PRE + PLACE ("Jesuit Sacramento"), but the
#     classic type-named schools read PLACE + TYPE ("Chicago Latin",
#     "Boston English", "Wilmington Charter") — the _TYPE_FIRST set.
#   * "of the X" where X is NOT a subject stays whole ("Jewish Community High
#     School of the Bay", "Carnahan High School of the Future") — there is no
#     colloquial collapse for those.
#   * "College Preparatory School of" collapses like "School of", which is how
#     "Jesuit College Preparatory School of Dallas" reads "Jesuit Dallas".
_SUBJECTS = {"science", "technology", "commerce", "industry", "arts", "art",
             "design", "engineering", "public", "business", "agriculture",
             "agricultural", "medicine", "health", "law", "mathematics", "math",
             "media", "music", "leadership", "communication", "communications",
             "humanities", "advanced", "applied", "performing", "visual",
             "environmental", "innovation", "trades", "aviation"}
_TYPE_FIRST = {"latin", "english", "charter"}
_SCHOOL_OF_RE = re.compile(
    r"^(?P<pre>.+?)\s+(?:(?:College\s+Preparatory|High)\s+)?Schools?\s+of\s+(?P<obj>.+)$",
    re.IGNORECASE)


def _collapse_school_of(name: str) -> str:
    m = _SCHOOL_OF_RE.match(name)
    if not m:
        return name
    pre, obj = m.group("pre"), m.group("obj")
    the = obj.lower().startswith("the ")
    if the:
        obj = obj[4:]
    if obj.split()[0].lower() in _SUBJECTS:
        return f"{pre} {obj.split(' and ')[0].strip()}"
    if the:
        return name                   # "of the Bay" / "of the Future" — the name
    if pre.lower().startswith("the "):
        pre = pre[4:]                 # "The Catholic ... of Baltimore" -> Catholic
    if pre.split()[-1].lower() in _TYPE_FIRST:
        return f"{obj} {pre}"         # Chicago Latin, Boston English
    return f"{pre} {obj}"             # Jesuit Sacramento


def _display_name(name: str) -> str:
    name = _collapse_school_of(name)
    while True:
        stripped = _SUFFIX_RE.sub("", name).strip()
        if stripped == name or not stripped:
            return name
        name = stripped


def canon(name: str) -> str:
    """A school's STABLE identity, whichever name prep-network currently uses.

    ‼️ This is what makes the import invariant to the source rename. The
    sponsorship dice are drawn positionally over a NAME-SORTED list, so once
    prep-network was renamed to match (`scripts/rename_prep_network.py`), the
    alphabet moved and every school inherited its neighbour's roll: measured, the
    association swapped a large slice of its membership and quietly re-admitted
    magnet schools this cleanup had just removed. Sorting and forcing on the
    canonical name reproduces the ORIGINAL order in BOTH states — pre-rename a
    source name misses the map and returns itself, post-rename a display name
    maps back — so the same schools sponsor tennis either way."""
    return _CANONICAL.get(name, name)


def champ_group(classification: str) -> str:
    return classification if classification in ("7A", "6A", "5A", "4A", "3A") else "2A-1A"


GROUPS = ("7A", "6A", "5A", "4A", "3A", "2A-1A")


def _load(prep: str) -> tuple[list[dict], dict[str, dict]]:
    orgs = os.path.join(prep, "records", "orgs")
    sp, cp = os.path.join(orgs, "schools.json"), os.path.join(orgs, "cities.json")
    for p in (sp, cp):
        if not os.path.exists(p):
            sys.exit(f"not found: {p}\nPoint --prep-network at a prep-network checkout.")
    with open(sp, encoding="utf-8") as fh:
        schools = json.load(fh)["schools"]
    with open(cp, encoding="utf-8") as fh:
        cities = json.load(fh)
    cities = cities["cities"] if isinstance(cities, dict) else cities
    return schools, {c["name"]: c for c in cities}


def always_sponsor() -> set[str]:
    """Schools that sponsor tennis because the OWNER says they do.

    ⚠️ Sponsorship below is a seeded coin flip per school against a per-classification
    rate — a reasonable way to pick ~335 tennis programs out of Jefferson's 840 schools,
    and a terrible way to decide whether a school the owner has named as a blue blood
    exists. Forty of the first seventy-eight archetype nominations landed outside the
    roll, which reads as "your list is wrong" when the truth is that a dice roll had
    already voted on it.

    So a named school is always in. Sourced from `data/jhsaa/archetypes.json` (the
    archetype seed list) plus `ALWAYS_EXTRA` for schools the owner wants in the
    association without tagging them. Names are matched accent- and punctuation-
    insensitively against prep-network, which is the source of truth for what exists."""
    out = set(ALWAYS_EXTRA)
    arch = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "jhsaa", "archetypes.json")
    try:
        with open(arch, encoding="utf-8") as fh:
            out |= set(json.load(fh).get("programs", {}))
    except (FileNotFoundError, ValueError):
        pass
    # ⚠️ `archetypes.json` is keyed by the name the ASSOCIATION uses (the emitted,
    # possibly renamed one) because `jhsaa.archetype()` looks a school up by the
    # name on its roster row. Forcing, though, happens against prep-network's
    # SOURCE names. So a renamed school's archetype entry has to be translated
    # back here, or it silently stops forcing that school into the association —
    # and, being a blue blood the dice never drew, it vanishes.
    back = {new: src for src, new in RENAMES.items()}
    return {back.get(n, n) for n in out}


def _key(name: str) -> str:
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", n).strip()


def sponsors(schools: list[dict]) -> tuple[set[str], set[str]]:
    """(girls, boys) school names. One roll for girls; boys drawn from that set — except
    that owner-named schools are in regardless, for both genders."""
    rng = random.Random(SEED)
    # Everything here keys on `canon()`, never the current name — see that
    # function. Forcing lists mix both vocabularies (archetypes.json is keyed by
    # the association's display name, ALWAYS_EXTRA by prep-network's), and
    # canonicalising both sides lands them on one identity.
    forced = {_key(canon(n)) for n in always_sponsor()}
    girls_only = {_key(canon(n)) for n in ALWAYS_GIRLS_ONLY}
    girls, boys = set(), set()
    for s in sorted(schools, key=lambda s: canon(s["name"])):  # stable order = stable draw
        hit = rng.random() < GIRLS_RATE[s["classification"]]  # drawn either way, so the
        sub = rng.random() < BOYS_OF_GIRLS                    # roll stays reproducible
        if _key(canon(s["name"])) in forced:
            girls.add(s["name"])
            if _key(canon(s["name"])) not in girls_only:
                boys.add(s["name"])
        elif hit:
            girls.add(s["name"])
            if sub:
                boys.add(s["name"])
    # THE FLAGSHIP PLAYS THE SPORT: hand each substituted magnet's seat to the
    # bare-named school in its city, per gender, after the draw (see
    # SUBSTITUTIONS). The bare school may also have been drawn on its own — sets
    # make that a no-op rather than a double entry.
    for side in (girls, boys):
        for magnet, flagship in SUBSTITUTIONS.items():
            if magnet in side:
                side.discard(magnet)
                side.add(flagship)
    return girls, boys


def draw_districts(pool: list[dict], cities: dict) -> dict[str, str]:
    """school name -> district name, for ONE classification group.

    Sorted by area → county → city so a district is geographically contiguous, then cut
    into the fewest balanced blocks of <= MAX_DISTRICT."""
    def county(s):
        return cities.get(s["city"], {}).get("county", "?")

    # `canon`, not the display name — same reason as `sponsors`: the blocks are cut
    # off this ORDER, so sorting on a name the owner can rename moves schools
    # between districts every time one is renamed.
    pool = sorted(pool, key=lambda s: (s["area"], county(s), s["city"], canon(s["name"])))
    n = len(pool)
    if not n:
        return {}
    k = max(1, -(-n // MAX_DISTRICT))
    # ⚠️ SPREAD THE REMAINDER, don't dump it in the last block. Filling `k` blocks
    # of a fixed `ceil(n/k)` leaves the tail whatever is left over, which is fine
    # when it divides evenly and awful when it doesn't: 100 7A boys into blocks of
    # 12 gives eight full districts and a NINTH OF FOUR — an eight-dual league
    # season against everyone else's twenty-two, because district size IS the
    # schedule here. Sizes now differ by at most one (`n % k` blocks take the
    # extra), so the same 100 becomes one 12 and eight 11s.
    big, base = n % k, n // k
    bounds, at = [], 0
    for i in range(k):
        step = base + (1 if i < big else 0)
        bounds.append((at, at + step))
        at += step
    out, used = {}, set()
    for lo, hi in bounds:
        block = pool[lo:hi]
        if not block:
            continue
        # name for the dominant area, else the dominant county, else a numbered fallback
        cands = [f"{Counter(s['area'] for s in block).most_common(1)[0][0]} District"]
        cands += [f"{c} District"
                  for c, _ in Counter(county(s) for s in block).most_common()]
        name = next((c for c in cands if c not in used),
                    f"{block[0]['area']} {len(used) + 1} District")
        used.add(name)
        for s in block:
            out[s["name"]] = name
    return out


def build(schools: list[dict], cities: dict) -> list[dict]:
    moved = reclassify(schools)
    girls, boys = sponsors(schools)
    by_name = {s["name"]: s for s in schools}
    dist = {"girls": {}, "boys": {}}
    for g in GROUPS:
        for gender, pool_names in (("girls", girls), ("boys", boys)):
            pool = [by_name[n] for n in pool_names
                    if champ_group(by_name[n]["classification"]) == g]
            dist[gender].update(draw_districts(pool, cities))
    out = []
    for name in sorted(girls | boys):
        s = by_name[name]
        city = cities.get(s["city"], {})
        display = _display_name(RENAMES.get(name, name))
        # ‼️ The ROSTER IDENTITY (`jhsaa.School.source`), and it must be stable
        # forever — it seeds the RNG that builds a program's twelve players and
        # the pids on their records, so if it moves, every renamed school gets
        # twelve strangers and its archived awards point at nobody.
        #
        # Derived from the DISPLAY name through the inverse map, NOT from the
        # name prep-network currently uses, because prep-network is itself being
        # renamed to match (`scripts/rename_prep_network.py`). Once that lands,
        # `name` here IS the new name, `RENAMES.get` misses, and a source-side
        # identity would silently become the new name — churning every roster a
        # second time. Keying off the display name gives the same answer in both
        # states, which is the whole point. `RENAMES` is therefore a PERMANENT
        # historical record; do not prune it once prep-network is updated.
        canonical = canon(name)
        out.append({
            "name": display,
            # Only written when it differs — a school nobody renamed is its own
            # identity, and an absent key reads as "name" in `School.ident`.
            **({"source": canonical} if canonical != display else {}),
            "city": s["city"],
            "county": city.get("county", ""),
            "area": s["area"],
            "classification": s["classification"],
            "group": champ_group(s["classification"]),
            "enrollment": s["enrollment"],
            "private": s["private"],
            "mascot": s["mascot"],
            "colors": s["colors"],
            "girls": name in girls,
            "boys": name in boys,
            "girls_district": dist["girls"].get(name, ""),
            "boys_district": dist["boys"].get(name, ""),
        })
    out.sort(key=lambda r: r["name"])     # renamed rows land at their NEW name
    return out


def report(rows: list[dict]) -> None:
    print(f"{'group':8}{'girls':>7}{'boys':>7}{'G dists':>9}{'B dists':>9}")
    for g in GROUPS:
        rs = [r for r in rows if r["group"] == g]
        gi = [r for r in rs if r["girls"]]
        bo = [r for r in rs if r["boys"]]
        print(f"{g:8}{len(gi):>7}{len(bo):>7}"
              f"{len({r['girls_district'] for r in gi}):>9}"
              f"{len({r['boys_district'] for r in bo}):>9}")
    gi = [r for r in rows if r["girls"]]
    bo = [r for r in rows if r["boys"]]
    print(f"{'TOTAL':8}{len(gi):>7}{len(bo):>7}")
    print(f"  {len(rows)} schools sponsor tennis; "
          f"{len(gi) - len(bo)} girls-only, {len([r for r in rows if r['boys'] and not r['girls']])} boys-only")
    # A district is keyed by (group, gender, name) — the same place name is reused
    # across classifications, exactly as "6A-1 PIL" and "5A-1 PIL" would be in Oregon.
    for gender, key in (("girls", "girls_district"), ("boys", "boys_district")):
        sizes = Counter((r["group"], r[key]) for r in rows if r[gender])
        big = [k for k, v in sizes.items() if v > MAX_DISTRICT]
        print(f"  {gender}: {len(sizes)} districts, sizes {min(sizes.values())}-{max(sizes.values())}"
              + (f"  OVERSIZED: {big}" if big else ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--prep-network",
                    default=os.path.join(os.path.dirname(_REPO), "prep-network"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    schools, cities = _load(args.prep_network)
    rows = build(schools, cities)
    report(rows)
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return
    os.makedirs(_OUT_DIR, exist_ok=True)
    with open(_OUT, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "_doc": ["JHSAA tennis-sponsoring schools with per-gender districts.",
                     "Generated by scripts/import_jhsaa.py from prep-network's",
                     "records/orgs/. Sponsorship is RE-DERIVED, not inherited —",
                     "see that script's docstring and",
                     "docs/DESIGN-jhsaa-high-school-season.md."],
            "schools": rows,
        }, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {os.path.relpath(_OUT, _REPO)}")


if __name__ == "__main__":
    main()
