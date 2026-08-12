"""
JHSAA — Jefferson's high-school tennis association.

The one place a high-school season is played. Jefferson's ~335 girls' and ~292 boys'
programs play a district schedule and a state dual-team tournament here, in this engine,
with players generated and developed here. `prep-network` supplied the institutions only
(see `scripts/import_jhsaa.py`); nothing about a player comes from that repo.

The point is that Jefferson's entries on the college recruit board are not invented — they
are the kids who just finished four years in this association, carrying their real records.
`graduating_class()` is that hand-off.

FORMATS (owner rule 2027-08) — read them through `dual_format()`, never by literal:
  * regular season  5 singles / 2 doubles  → 7 points
  * state tournament 1 singles / 4 doubles → 5 points
Both totals are ODD, so a dual cannot be tied and no tie-breaking exists anywhere.
Every match plays to completion — there is no clinch in high school
(`simulate_dual(play_all=True)`, as D3/D4 already do).

SCORING is a separate axis from shape and is the SAME for every line, singles and
doubles: a full best-of-3, no-ad, tiebreak sets, a real third set (`MATCH_FORMAT`).
High-school doubles is NOT the college 8-game pro set — that is `engine.dual`'s
default, so both formats are passed explicitly.

TALENT is far below the college floor and much wider (`_TALENT`). A 7A number one may be
a future D1 signee; a 1A number one would lose to a college walk-on. That spread inside a
single dual is the character of the level, not a calibration bug.

See docs/DESIGN-jhsaa-high-school-season.md.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
from collections import defaultdict
from dataclasses import dataclass, field

from engine.dual import DualFormat, Team, simulate_dual
from engine.format import PRESETS
from .development import Prospect, generate_prospect, make_pid, overall_to_str

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "jhsaa", "schools.json")

GROUPS = ("7A", "6A", "5A", "4A", "3A", "2A-1A")
GENDERS = ("girls", "boys")

# --- formats ----------------------------------------------------------------
FORMATS = {
    "regular": DualFormat(n_singles=5, n_doubles=2, doubles_team_point=False),
    "state":   DualFormat(n_singles=1, n_doubles=4, doubles_team_point=False),
}


# The two POSTSEASON phases. They share everything that matters — the 1S/4D shape, the
# strict best-nine lineup, and exclusion from the TOSS rating — and differ only in which
# event they belong to. The TOC carries its own phase rather than borrowing "state"
# because the archive is the only place the two can be told apart afterwards: written as
# "state" its duals landed on a program's state-tournament record, and a program that
# reached the Tournament of Champions had no way to say so.
POSTSEASON = ("state", "toc")


def dual_format(phase: str) -> DualFormat:
    """The dual shape for `phase` ("regular" | "district" | "state" | "toc"). District
    tournaments play the regular-season shape; the postseason events switch."""
    return FORMATS["state"] if phase in POSTSEASON else FORMATS["regular"]


# SCORING (owner rule 2027-08), a different axis from the SHAPE above: every high-school
# match — singles AND doubles — is a full best-of-3, no-ad, tiebreak sets, real third set.
# College doubles is an 8-game pro set and `engine.dual` defaults to it, so both formats
# are passed explicitly at every call; without them a JHSAA doubles line scores "5-8".
MATCH_FORMAT = PRESETS["high_school"]


def lineup_need(phase: str) -> int:
    """Players a program must dress for `phase` with nobody doubling up."""
    f = dual_format(phase)
    return f.n_singles + 2 * f.n_doubles          # 5+4 = 9 regular, 1+8 = 9 state


ROSTER_SIZE = 12          # 9 is the hard floor; carry depth for injuries and rotation

# Non-district duals per team (owner rule 2027-08). The POSTSEASON IS EXEMPT.
# This is an ALLOWANCE ON TOP of the district double round-robin, not a season total:
# district size already sets most of the schedule (a 12-team district is 22 league duals,
# a 6-team one is 10), so a fixed season total would force wildly different non-league
# loads on schools of different districts. To shorten seasons, shrink the districts —
# `MAX_DISTRICT` in `scripts/import_jhsaa.py` — not this.
NONDISTRICT_MIN, NONDISTRICT_MAX = 4, 8

# How that allowance is spread across the season (owner rule 2027-08). A high-school
# card is not "all the non-league games, then all the league ones" — it opens
# non-district, runs the league, breaks for a mid-season window, runs the league back
# the other way, and has room for a tune-up before districts. USTA's model treats
# district, non-district and tournament play as separate schedule TYPES rather than one
# undifferentiated block, and this is where that shows up in the order of play.
EARLY_SHARE = 0.55        # of the non-challenge non-district card, played before league
MID_NONDISTRICT = 1       # non-district duals in the mid-season window, besides the challenge

# --- the mid-season challenge (owner rule 2027-08) ---------------------------
# One cross-district dual in the mid-season window, paired AFTER the first league pass
# on how the season has actually gone — the scheduling idea behind college basketball's
# old BracketBusters: hold a date open, then match comparable programs from different
# leagues once you know who is comparable. So the #3 team in one district draws the #3
# in another, not whoever geography threw up in February.
#
# It is NON-DISTRICT and can never touch district place; it is an ordinary result
# everywhere else (overall record, TOSS, at-large selection), which is the point of
# playing it. Hosting alternates on a hash of the pairing and the year, so no program
# is systematically at home for it.
CHALLENGE_ENABLED = True
CHALLENGE_PLACE_SLACK = 1     # pair a #3 with a #2-#4; never a #1 with a #8
CHALLENGE_GEO_WEIGHT = 6.0    # travel matters, but less than getting the level right

# High school runs at "fast" fidelity, deliberately. `full` resolves every POINT, which
# is 6.7x the cost and is meant for the college season you actually watch; a season here
# is ~5,100 duals per gender and at full fidelity it added ~100s to the first recruit
# class build — on the request thread, which is the outage class CLAUDE.md warns about.
# Winners, scores and individual records are all unaffected; only per-point box detail is.
FIDELITY = "fast"

# --- state tournament (owner-decided) ---------------------------------------
# field size, and how many per district qualify automatically. 7A is deliberately the
# most district-driven classification: two from every district get in on the court.
# 2A-1A is the BIGGEST classification (151 girls / 136 boys across 13 districts), so
# it gets the biggest bracket alongside 7A. At 24 it was the hardest class in the
# association to qualify from -- 13 automatic bids left only 11 at-large places for
# 138 other programs -- which is exactly backwards for the level that is supposed to
# be the sprawling, everybody-plays one.
# 24 into a 32-team draw is deliberate, not a rounding-down (owner rule 2027-08): the
# top eight seeds bye and seeds 9-24 play in, so nobody reaches the number one seed
# without having won a dual. A full 32 gives a 1 v 32 opener, which is a bye with
# extra steps. It also keeps the girls' and boys' cutlines close where a
# classification is lopsided by gender.
FIELD = {"7A": 32, "6A": 32, "5A": 24, "4A": 24, "3A": 24, "2A-1A": 32}
AUTO_PER_DISTRICT = {"7A": 2, "6A": 1, "5A": 1, "4A": 1, "3A": 1, "2A-1A": 1}

# --- talent ------------------------------------------------------------------
# (mean, spread) of the 20-80 grade per classification. Well beneath the college bands
# (D1 men 60/16, D3 men 39/27) and far wider — a 7A roster and a 1A roster barely
# belong to the same sport. Girls sit a little under boys, mirroring the college split.
# NOTE these are CEILING targets, not current ability: `generate_prospect` treats
# `talent` as the potential and derives a much lower current from maturity, so a 7A
# number one with a ceiling of 46 still plays at a current ~30 while in school. That is
# the whole reason the bands look high for high schoolers — do not "fix" them downward
# by comparing them to the college _TALENT means, which ARE current.
# The top-190 graduating seniors are Jefferson's entry on the national recruit board.
# MEASURED, not asserted: best ~#227 of 2500, median ~#483, i.e. the hand-off sits in the
# top fifth of the class rather than astride its median. (The comment here used to claim
# "best ~#25, median near the national median"; it was ~#274/#527 before this rebalance
# too, so it was describing an intention rather than the numbers. Re-measure before
# quoting it — `graduating_class` against `world.board_class`.)
# ⚠️ SMALLER SCHOOLS ARE THINNER, NOT CAPPED (owner rule 2027-08). Tennis is not a
# sport where the big school simply has better players — good players turn up
# everywhere, and what enrollment actually buys you is DEPTH. So the classifications
# differ in the BULK of the distribution (the mean) while the upper tail stays broadly
# common (the spread WIDENS as the mean falls), and 7A/6A are near-indistinguishable at
# the top with the real steps coming below.
#
# The previous ladder was a flat -5/-4 shift per class with the spread NARROWING as the
# mean fell, which gets the sport backwards in a way that only shows if you measure the
# lineup position by position. Measured on the old numbers (boys, mean current OVR):
#
#            #1     #9   drop   best #1 seen
#   7A     54.4   31.1   23.2     60.0
#   3A-1A  42.0   22.8   19.2     51.0
#
# The #1s were 12.4 apart and the #9s only 8.3 — the TOP fell faster than the depth, and
# the drop from #1 to #9 was FLATTER at a small school than a big one. A 3A-1A program
# could not produce a 60 at all, so it could never be the small school sitting top-10 in
# the state, which is a completely ordinary thing in real high-school tennis (in Oregon's
# 2026 boys table, Oregon Episcopal — the smallest classification — finished No. 9
# statewide, and four of the top eight were 5A).
#
# Widening the spread as the mean falls does both jobs at once, because 12 ceilings are
# drawn and the best 9 dress: a wide draw lifts the number one a long way and drags the
# number nine down. Do NOT "tidy" these back into an even ladder with shrinking spreads.
_TALENT = {
    ("7A", "boys"):   (58.0, 15.0), ("7A", "girls"):   (53.0, 14.0),
    ("6A", "boys"):   (56.5, 15.5), ("6A", "girls"):   (51.5, 14.5),
    ("5A", "boys"):   (51.0, 17.5), ("5A", "girls"):   (46.5, 16.5),
    ("4A", "boys"):   (46.0, 19.0), ("4A", "girls"):   (42.0, 18.0),
    ("3A", "boys"):    (43.5, 20.0), ("3A", "girls"):    (38.0, 19.0),
    ("2A-1A", "boys"): (38.5, 22.0), ("2A-1A", "girls"): (34.5, 21.0),
}
# --- PROGRAM ARCHETYPES (owner rule 2027-08) ---------------------------------
#
# A school-level modifier ON TOP of the classification bands above, never a replacement
# for them: a blue-blood 3A-1A program is a strong SMALL-SCHOOL program, not a 7A one.
# It describes DURABLE PROGRAM CONDITIONS — facilities, feeder networks, community
# participation, coaching tradition, reputation — not current team strength, and it is
# deliberately NOT derived from classification or public/private. Those may inform who
# gets seeded onto the list; the property belongs to the individual school and is
# editable (`/editor`, `overrides.set_jhsaa_archetype`) so the owner can promote and
# demote programs as Jefferson's history develops.
#
#   blue_blood   generates better, and CLUSTERS — several strong players in one roster
#   development  generates normal CURRENT ability but high POTENTIAL, and develops it
#                faster, so the effect shows over a four-year career rather than on
#                arrival
#   doubles      generates normally; the edge is in DOUBLES ONLY, as a per-match boost
#   upstart      a TEMPORARY multi-year run, rolled per world — see `upstarts()`
#   (untagged)   normal
#
# `mean` shifts the classification band's centre; `spread` scales its width; `pot` is a
# ceiling-only bonus (potential without present ability); `mature` accelerates how much
# of that ceiling has surfaced by each grade.
ARCHETYPES = {
    # BETTER ON BALANCE than a development programme (owner rule 2027-08) — that is what
    # makes it a blue blood — and it shows on ARRIVAL: its ninth-graders are already in
    # the low thirties, where an ordinary program's are mid-twenties. A development
    # program can still beat one in a given season; it just has to earn it over four
    # years rather than have it on day one.
    "blue_blood":  {"mean": +15.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "Blue blood"},
    # A development programme SHOULD be able to beat a blue blood outright (owner rule
    # 2027-08) — that is the point of it, and it is how coaching levels a playing field
    # that facilities and reputation tilt. What separates them is the SHAPE, not the
    # ceiling: `mean` is 0 and the maturity bonus starts at ZERO for freshmen and
    # compounds by grade, so this program's ninth-graders look ordinary and its seniors
    # are the best in the association. Arrive good vs leave great.
    "development": {"mean":  0.0, "spread": 1.05, "pot": +6.0, "mature": 0.038,
                    "label": "Development program"},
    "doubles":     {"mean":  0.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "Doubles school"},
    "upstart":     {"mean":  0.0, "spread": 1.00, "pot": 0.0, "mature": 0.00,
                    "label": "Upstart"},
}

# A blue blood does not just draw higher, it draws TOGETHER: a share of its seats are
# re-rolled and the better draw kept, which is what "several strong players in the same
# roster" means. Applied per seat, so it lifts the top of the lineup much more than the
# bottom — the same best-of-n effect the classification spread uses.
BLUE_BLOOD_REDRAW = 0.70

# UPSTART — a temporary run, not a promotion. ~10 programs statewide at any time, each
# for a few seasons, rolled deterministically from the world salt so a save reproduces
# its own history and the run EXPIRES on its own.
UPSTART_N = 10
UPSTART_RUN = (2, 4)              # seasons a run lasts
UPSTART_LIFT = (0.15, 0.30)       # 15-30% stronger than the program's own baseline

# DOUBLES SCHOOLS — the edge is ephemeral and per-match, not a better roster. There was
# no existing per-match boost to reuse (`coaches.development_multiplier` is a growth
# rate, not a match modifier), so this is the first: `_squad` already builds doubles as
# its OWN lineup (`Team.doubles_players`), so a boosted copy of those players is confined
# to doubles by construction and cannot leak into a singles court.
DOUBLES_BOOST = (5.0, 11.0)


# TWO LAYERS, as the owner specified: the SEED list ships with the repo as school data
# (`data/jhsaa/archetypes.json`), and the override table is the editable layer on top, so
# a save can promote or demote a program without editing the file — and clearing an
# override reverts that program to whatever the seed says. An override of "none"
# explicitly DEMOTES a seeded program, which is different from having no override at all.
_ARCH_SEED_PATH = os.path.join(os.path.dirname(_DATA), "archetypes.json")
_arch_cache: dict = {}


def _arch_seed() -> dict:
    try:
        with open(_ARCH_SEED_PATH, encoding="utf-8") as fh:
            return {k: v for k, v in json.load(fh).get("programs", {}).items() if v}
    except (FileNotFoundError, ValueError):
        return {}


def archetype(school: str) -> str:
    """A program's archetype tag, or "" — the seed list with the editable table on top."""
    from app import overrides as ov
    return _arch_map(ov.jhsaa_archetype_version()).get(school, "")


def _arch_map(version: str) -> dict:
    """{school: archetype}, memoised on the override table's fingerprint. Computed into a
    LOCAL and published (the gthread rule); never read back out of the dict it wrote."""
    hit = _arch_cache.get(version)
    if hit is not None:
        return hit
    from app import overrides as ov
    out = _arch_seed()
    for school, kind in ov.get_jhsaa_archetypes().items():
        if kind == "none":
            out.pop(school, None)           # an explicit demotion of a seeded program
        else:
            out[school] = kind
    _arch_cache.clear()                     # one entry: only the current version matters
    _arch_cache[version] = out
    return out


def upstarts(year: int, salt: str = "") -> dict[str, float]:
    """{school: lift} for the programs currently on an upstart run.

    Rolled per world rather than stored, because an upstart is a RUN and a stored tag
    would make it permanent. Each candidate's run start and length are derived from the
    salt, so the same save always tells the same story and a run ends by itself.

    Already-tagged programs are skipped — an upstart is a school having a moment, not a
    blue blood having a slightly better one — but they are skipped AT APPLICATION, never
    removed from the pool the draw runs over. Filtering the pool made the archetype table
    non-local: tagging one school changed which OTHER schools drew an upstart that
    season, because it changed what `rng.sample` was sampling from. A tag must only ever
    affect the school it is on."""
    tagged = set(_arch_map(__import__("app.overrides", fromlist=["x"]).jhsaa_archetype_version()))
    pool = sorted({s.name for s in load_schools("girls")} | {s.name for s in load_schools("boys")})
    if not pool:
        return {}
    out: dict[str, float] = {}
    # Walk a window of seasons so runs overlap and roughly UPSTART_N are live at once.
    lo, hi = UPSTART_RUN
    for start in range(year - hi + 1, year + 1):
        rng = random.Random(f"{salt}|jhsaa-upstart|{start}")
        per_season = max(1, round(UPSTART_N / ((lo + hi) / 2)))
        for n in rng.sample(pool, min(per_season, len(pool))):
            run = rng.randint(lo, hi)
            lift = round(rng.uniform(*UPSTART_LIFT), 3)
            if start <= year < start + run and n not in tagged:
                out[n] = lift
    return out


def _program_mod(school: School, year: int, salt: str) -> dict:
    """The combined school-level modifier for one program-season."""
    a = ARCHETYPES.get(archetype(school.name), {})
    mod = {"mean": a.get("mean", 0.0), "spread": a.get("spread", 1.0),
           "pot": a.get("pot", 0.0), "mature": a.get("mature", 0.0),
           "kind": archetype(school.name)}
    lift = upstarts(year, salt).get(school.name)
    if lift:
        # A percentage of the program's OWN baseline, so an upstart 1A is a strong 1A.
        mean, _spread = _TALENT[(school.group, school.gender)]
        mod["mean"] += mean * lift
        mod["kind"] = mod["kind"] or "upstart"
    return mod


GRADE_FLOOR = 12.0        # below the 20-80 scale's nominal floor on purpose: 1A depth

# High school is grades 9-12 and nothing else. A player enters at 9 and leaves after 12.
GRADES = (9, 10, 11, 12)
PER_CLASS = 3                                  # 3 x 4 grades = ROSTER_SIZE

# MATURITY is the share of a player's ceiling that is visible as current ability, and it
# is what keeps high school looking like high school. College freshmen already sit at
# 0.83 (`ncaa._CLASS_MATURITY`); a 9th grader shows well under half of what they will
# become. So ceilings can be as high as the talent deserves — a future D1 star really is
# in here — while nobody PLAYS beyond a high-school range until they leave.
# It also is the aging model: the same player's current rises every year purely because
# more of their ceiling has surfaced.
_MATURITY = {9: (0.40, 0.48), 10: (0.50, 0.58), 11: (0.60, 0.68), 12: (0.70, 0.78)}

# ⚠️ A FEW FRESHMEN ARRIVE FINISHED (owner rule 2027-08). Roughly 1 in 100 shows up with
# most of their ceiling already accessible — the kid who has been playing juniors since
# they were eight and walks straight into the number one spot. This is NOT a potential
# bonus: a prodigy can be an ordinary 45 ceiling who simply arrives at 40 instead of 20.
#
# It is a maturity FLOOR, and it persists for all four years, which is the whole point.
# The normal band rises with each grade, so a one-off ninth-grade boost would quietly
# un-mature them as a sophomore. Carrying the floor instead means they start near their
# ceiling and then barely grow — the early bloomer their classmates catch, which is what
# actually happens.
#
# Rolled on its OWN rng stream, not the roster one. Drawing it from the main sequence
# would shift every subsequent draw and regenerate every player in the association;
# keyed separately, the only rosters that change are the ones that gain a prodigy.
PRODIGY_RATE = 0.01
PRODIGY_MATURITY = (0.84, 0.93)


@dataclass
class School:
    name: str
    city: str
    county: str
    area: str
    classification: str
    group: str
    enrollment: int
    private: bool
    mascot: str
    colors: list
    district: str
    gender: str

    @property
    def key(self) -> str:
        return f"{self.name}|{self.gender}"


@dataclass
class TeamSeason:
    school: School
    roster: list
    wins: int = 0                       # overall, district + crossover
    losses: int = 0
    dwins: int = 0                      # DISTRICT only — what decides district place
    dlosses: int = 0
    points_for: float = 0.0
    points_against: float = 0.0
    district_place: int = 0
    # TOSS Power Index (raw, pre-display-normalisation), set once the regular season
    # is complete. It is what at-large selection and state seeding sort on, so it is
    # archived with the season rather than recomputed on read — see world.run_jhsaa.
    power: float = 0.0
    # pid -> [wins, losses] at any line. Awards are individual, so they need this.
    records: dict = field(default_factory=dict)
    by_pid: dict = field(default_factory=dict)
    # Every dual this team played, in order. Kept so a school's season can be read
    # match by match without replaying it — the college side's schedule view.
    schedule: list = field(default_factory=list)

    @property
    def record(self) -> str:
        return f"{self.wins}-{self.losses}"

    @property
    def district_record(self) -> str:
        return f"{self.dwins}-{self.dlosses}"

    @property
    def win_pct(self) -> float:
        n = self.wins + self.losses
        return self.wins / n if n else 0.0

    @property
    def district_pct(self) -> float:
        n = self.dwins + self.dlosses
        return self.dwins / n if n else 0.0


_schools_cache: dict | None = None


def load_schools(gender: str) -> list[School]:
    """Every JHSAA program for `gender`, with its district."""
    global _schools_cache
    if _schools_cache is None:
        with open(_DATA, encoding="utf-8") as fh:
            _schools_cache = json.load(fh)["schools"]
    out = []
    for r in _schools_cache:
        if not r.get(gender):
            continue
        out.append(School(
            name=r["name"], city=r["city"], county=r["county"], area=r["area"],
            classification=r["classification"], group=r["group"],
            enrollment=r["enrollment"], private=r["private"], mascot=r["mascot"],
            colors=r["colors"], district=r[f"{gender}_district"], gender=gender,
        ))
    return out


def districts(gender: str, group: str) -> dict[str, list[School]]:
    d = defaultdict(list)
    for s in load_schools(gender):
        if s.group == group:
            d[s.district].append(s)
    return dict(d)


# --- rosters -----------------------------------------------------------------

def _ceiling(rng: random.Random, group: str, gender: str,
             mod: dict | None = None) -> float:
    """A player's CEILING, drawn independently per player. The ladder is not assigned —
    it emerges from who is actually best, so a great freshman can play number one over a
    senior, which is how high school works.

    `mod` is the program-level modifier (`_program_mod`) applied ON TOP of the
    classification band — it shifts and scales that band, it never replaces it, so a
    blue-blood 3A-1A remains a strong SMALL-SCHOOL program."""
    mean, spread = _TALENT[(group, gender)]
    if mod:
        mean += mod.get("mean", 0.0)
        spread *= mod.get("spread", 1.0)
    draw = rng.gauss(mean, spread)
    if mod and mod.get("kind") == "blue_blood" and rng.random() < BLUE_BLOOD_REDRAW:
        # Draw twice, keep the better — clustering, not just a higher mean. Best-of-two
        # lifts the top of a roster far more than the bottom, which is what a programme
        # with the courts and the feeder network actually produces.
        draw = max(draw, rng.gauss(mean, spread))
    return max(GRADE_FLOOR, min(80.0, draw))


def build_roster(school: School, year: int, salt: str = "") -> list[Prospect]:
    """A program's roster for season `year` — its four classes, grades 9 through 12.

    A player is keyed on the year they ENTERED, not the season being played, so the
    same person carries the same pid, name and ceiling through all four years and simply
    matures: the junior who went 15-5 is the senior on next year's board. That is what
    makes a high-school career real without persisting every player — the world rebuilds
    an identical one from (school, gender, entry year, seat).
    """
    from generators import make_name_picker
    sex = "male" if school.gender == "boys" else "female"
    mod = _program_mod(school, year, salt)
    out = []
    for grade in GRADES:
        entry = year - (grade - 9)
        # A DEVELOPMENT program's edge compounds with time in the programme: the same
        # ceiling surfaces faster every year, so a freshman arrives looking ordinary and
        # a senior does not. `mature` is per grade, so it is worth four times as much to
        # a senior as to a freshman — which is the point.
        lo, hi = _MATURITY[grade]
        # (grade - 9), so a FRESHMAN gets nothing and the bonus compounds over four
        # years. Keyed off 8 it would land on ninth-graders too, and a development
        # program's whole character is that you cannot spot it in its freshmen.
        step = mod.get("mature", 0.0) * (grade - 9)
        maturity = (min(1.0, lo + step), min(1.0, hi + step))
        for seat in range(PER_CLASS):
            rng = random.Random(f"{salt}|jhsaa|{school.key}|{entry}|{seat}")
            # Keyed on (school, entry, seat) — the same identity the pid is built from —
            # so a prodigy is the SAME person every one of their four seasons rather than
            # a fresh dice roll each year.
            prng = random.Random(f"{salt}|jhsaa-prodigy|{school.key}|{entry}|{seat}")
            if prng.random() < PRODIGY_RATE:
                lo2, hi2 = PRODIGY_MATURITY
                maturity = (max(maturity[0], lo2), max(maturity[1], hi2))
            nm, _ = make_name_picker(random.Random(rng.randrange(1 << 30)), gender=sex,
                                     region_weights={"us": 1.0})()
            p = generate_prospect(rng, nm, "US", gender=sex,
                                  talent=min(80.0, _ceiling(rng, school.group,
                                                            school.gender, mod)
                                             + mod.get("pot", 0.0)),
                                  maturity_range=maturity,
                                  pid=make_pid("jhsaa", school.name, school.gender,
                                               entry, seat))
            p.class_year = str(grade)
            p.grade = grade
            p.entry_year = entry
            p.hometown = f"{school.city}, JF"
            p.high_school = school.name
            p.region, p.domestic = "Jefferson", True
            out.append(p)
    out.sort(key=lambda p: -p.current_overall())
    return out


def _squad(ts: TeamSeason, phase: str, lineup: list | None = None) -> Team:
    """Dress `lineup` (or the current best nine) for `phase`. Singles take the top;
    doubles is its OWN roster below them (`Team.doubles_players`), so the state
    format's four doubles pairs are eight different players rather than the singles
    re-permuted."""
    f = dual_format(phase)
    r = lineup if lineup is not None else _order(ts)[:lineup_need(phase)]
    if not r:
        raise ValueError(f"{ts.school.name} has an empty roster")
    def at(i):
        return r[i % len(r)]                       # degrade, never crash, on a short side
    # Prospect -> engine Player, the same conversion ncaa.squad_and_ladder uses.
    singles = [at(i).engine_player() for i in range(f.n_singles)]
    dbl = [at(f.n_singles + i).engine_player() for i in range(2 * f.n_doubles)]
    if archetype(ts.school.name) == "doubles":
        dbl = [_doubles_lift(at(f.n_singles + i), ts.school.name, i)
               for i in range(2 * f.n_doubles)]
    return Team(name=ts.school.name, singles=singles,
                doubles=[(2 * i, 2 * i + 1) for i in range(f.n_doubles)],
                doubles_players=dbl)


def _doubles_lift(prospect, school: str, seat: int):
    """A doubles-school player, lifted on the 20-80 GRADE scale for this match only.

    A doubles program generates normally — the roster is not better, the doubles is. So
    the lift is ephemeral: it is applied to a COPY of the player's current grades on the
    way into the engine, never to the Prospect, which `build_roster` caches globally and
    shares across every save. Mutating that would make a temporary edge permanent and
    leak it into every other league reading the same object.

    It also lands only on `Team.doubles_players` — the separate doubles lineup `_squad`
    already builds — so it is structurally incapable of reaching a singles court, rather
    than merely intended not to.

    (There was no existing per-match modifier to reuse: `coaches.development_multiplier`
    is a growth RATE applied at the rollover, a different thing entirely.)"""
    import copy
    lo, hi = DOUBLES_BOOST
    rng = random.Random(f"{school}|dbl|{prospect.pid}|{seat}")
    lift = rng.uniform(lo, hi)
    clone = copy.copy(prospect)
    clone.current = {a: min(80.0, v + lift) for a, v in prospect.current.items()}
    return clone.engine_player()


_SLOT = re.compile(r"^([SD])(\d+)$")

# Bench rotation (owner rule 2027-08): the lineup is re-set match to match on the BEST
# PERFORMING nine — results first, then OVR, STR last — so a hot bench player earns his
# way in. On top of that, coaches USE the bench in the regular season: most duals a
# reserve or two rotates into the bottom of the lineup, so nobody persisted plays zero
# times across a ~26-dual year (which would be absurd). The POSTSEASON is strict:
# your best nine, no rotation. (No injuries here — the JHSAA has no injury system.)
_ROTATE_ONE = 0.45          # chance the 9th seat goes to a bench player, per dual
_ROTATE_TWO = 0.15          # chance the 8th seat does too


# ‼️ A CHALLENGE LADDER IS SEEDED ON ABILITY AND MOVED BY RESULTS — never ranked on a
# win COUNT. This sorted on cumulative wins first (`-w`), with ability third, and that
# is a ratchet rather than a ladder: a win total measures OPPORTUNITY, so dressing earns
# wins, wins earn the next start, and a player who dropped his first two duals — or who
# was ninth in week one and never got a start — can never climb back, because every
# team-mate who kept playing sits above him on a number he is not being allowed to add
# to. Ability was in the key but was unreachable behind it. It also ranked 5-15 above
# 4-0, and doubles credits BOTH partners, so a rotation player racked up wins faster
# than a number one playing the hardest opponent on the card.
#
# Measured over a full boys' season before the fix: on 55 of 400 rosters a top-four
# player finished outside the nine, 21 of them under seven matches all year — a 51-OVR
# senior sitting behind a 28-OVR team-mate on the same team.
#
# So the coach seeds on ability and lets the season move you: `LADDER_SWING` is what a
# perfect record is worth against a winless one, in OVR points, and `LADDER_PRIOR` is
# how much evidence it takes before a record carries about half its weight — which is
# what stops a 1-2 opening week from outranking a whole season, and what leaves a player
# who has not played AT HIS SEED instead of at the bottom.
LADDER_SWING = 14.0         # a season-long perfect record ≈ +7 OVR, winless ≈ -7
LADDER_PRIOR = 8.0          # matches before results carry ~half their weight


def ladder_score(p, record: list[int] | None) -> float:
    """Where the coach ranks `p` — ability, adjusted by what he has actually done."""
    w, l = record or (0, 0)
    n = w + l
    if not n:
        return p.current_overall()
    return p.current_overall() + LADDER_SWING * (w / n - 0.5) * n / (n + LADDER_PRIOR)


def _order(ts: TeamSeason) -> list:
    """The ladder as the coach reads it: ability, moved by results, then STR."""
    return sorted(ts.roster,
                  key=lambda p: (-ladder_score(p, ts.records.get(p.pid)),
                                 -p.str_value()))


def _lineup(ts: TeamSeason, phase: str, rng: random.Random) -> list:
    """The nine who dress for THIS dual."""
    order = _order(ts)
    need = lineup_need(phase)
    nine, bench = order[:need], order[need:]
    if phase not in POSTSEASON and bench:          # playoffs: strict best nine
        if rng.random() < _ROTATE_ONE:
            nine[-1] = bench[rng.randrange(len(bench))]
        if len(bench) > 1 and rng.random() < _ROTATE_TWO:
            pick = bench[rng.randrange(len(bench))]
            if pick is not nine[-1]:
                nine[-2] = pick
    return nine


def _slot_players(lineup: list, phase: str, slot: str) -> list:
    """The players who played `slot` ("S3", "D2"), by the SAME indexing the squad was
    dressed with — never a second opinion on who was on court."""
    m = _SLOT.match(slot or "")
    if not m or not lineup:
        return []
    kind, i = m.group(1), int(m.group(2))
    f = dual_format(phase)
    at = lambda k: lineup[k % len(lineup)]                        # noqa: E731
    if kind == "S":
        return [at(i - 1)]
    base = f.n_singles + 2 * (i - 1)
    return [at(base), at(base + 1)]


def _credit(ts: TeamSeason, lineup: list, phase: str, slot: str, won: bool) -> None:
    for p in _slot_players(lineup, phase, slot):
        rec = ts.records.setdefault(p.pid, [0, 0])
        rec[0 if won else 1] += 1
        ts.by_pid.setdefault(p.pid, p)


def _score_str(ln) -> str:
    res = getattr(ln, "result", None)
    sets = getattr(res, "set_scores", None) or []
    return ", ".join(f"{h}-{w}" for h, w in sets)


def play_dual(a: TeamSeason, b: TeamSeason, *, seed: int, phase: str = "regular",
              district: bool = False, challenge: bool = False):
    """One dual. Always to completion — high school has no clinch. `district` marks it
    as counting toward district place as well as the overall record.

    `challenge` is a LABEL on a non-district dual, not a phase: the mid-season challenge
    is played under the ordinary 5S/2D regular-season rules and counts everywhere a
    non-district dual counts (overall record, TOSS, at-large selection). Making it a
    `phase` would have quietly changed its dual format and dropped it out of the rating,
    which is the opposite of why it exists.

    It is deliberately IN-MEMORY ONLY and is not archived to `world_jhsaa_dual`: the
    owner does not want the challenge distinguished on a card, so after persistence it
    reads as the ordinary non-district dual it is. The flag exists so the scheduler can
    keep the window's one paired-on-results dual apart from the window's ordinary ones,
    and so the tests can assert it never reaches a district record. If a view ever needs
    to mark it, the column comes first — do not infer it from position in the card."""
    lrng = random.Random(f"lineup|{seed}")
    la, lb = _lineup(a, phase, lrng), _lineup(b, phase, lrng)
    res = simulate_dual(_squad(a, phase, la), _squad(b, phase, lb), seed=seed,
                        play_all=True, fidelity=FIDELITY, dual_fmt=dual_format(phase),
                        singles_fmt=MATCH_FORMAT, doubles_fmt=MATCH_FORMAT)
    lines = []
    for ln in res.lines:                       # individual records, for awards
        hw = getattr(ln, "home_won", None)
        if hw is None:
            continue
        slot = getattr(ln, "slot", "")
        _credit(a, la, phase, slot, bool(hw))
        _credit(b, lb, phase, slot, not hw)
        lines.append({"slot": slot,
                      "home": [x.name for x in _slot_players(la, phase, slot)],
                      "away": [x.name for x in _slot_players(lb, phase, slot)],
                      "score": _score_str(ln), "home_won": bool(hw)})
    a.points_for += res.home_points
    a.points_against += res.away_points
    b.points_for += res.away_points
    b.points_against += res.home_points
    # DualResult.winner is an INT — 0 home, 1 away. Comparing it to "home" silently
    # credits the away team every dual; under the home-and-home schedule this used to
    # run, that left every side at exactly .500 with correct-looking point
    # differentials. Cost an hour.
    a.schedule.append({"opp": b.school.name, "home": True, "phase": phase,
                       "pf": res.home_points, "pa": res.away_points,
                       "won": res.winner == 0, "district": district,
                       "challenge": challenge, "lines": lines})
    b.schedule.append({"opp": a.school.name, "home": False, "phase": phase,
                       "pf": res.away_points, "pa": res.home_points,
                       "won": res.winner == 1, "district": district,
                       "challenge": challenge, "lines": lines})
    if res.winner == 0:
        a.wins += 1
        b.losses += 1
        if district:
            a.dwins += 1
            b.dlosses += 1
    else:
        b.wins += 1
        a.losses += 1
        if district:
            b.dwins += 1
            a.dlosses += 1
    return res


# --- the season --------------------------------------------------------------

def run_district(schools: list[School], year: int, *, seed: int,
                 salt: str = "") -> list[TeamSeason]:
    """A district's regular season: DOUBLE round-robin, 5S/2D, every match completed.
    Returns its teams ordered by finish (win %, then point differential).

    You play every league opponent home AND away (owner rule 2027-08); the rest of the
    card is out-of-district, in `_crossover`. District size therefore sets the season
    length on its own — a 12-team district is 22 league duals before a single non-league
    one — so if seasons need to be shorter, shrink `MAX_DISTRICT` in
    `scripts/import_jhsaa.py`, don't cut the second leg.

    Split from `district_teams` so `run_season` can play the NON-district card first —
    see `_crossover`. Standalone (tests, a single district) this still does both."""
    teams = district_teams(schools, year, salt)
    play_district(teams, year, salt)
    return teams


def district_teams(schools: list[School], year: int, salt: str = "") -> list[TeamSeason]:
    """A district's programs with this year's rosters, before a ball is struck."""
    return [TeamSeason(school=s, roster=build_roster(s, year, salt)) for s in schools]


# --- the district round robin ------------------------------------------------
#
# ⚠️ A DOUBLE round robin is TWO SEPARATED PASSES, not a home-and-home series.
#
# This used to be `for a: for b: for leg in (0, 1)` — which plays a program's two
# meetings with an opponent on consecutive dates, all season long:
#
#     Mar 10  at Alder Landing        Mar 15  at Altamonte
#     Mar 12  vs Alder Landing        Mar 17  vs Altamonte
#
# Every card in the association read like that. It is a correct double round robin and
# a schedule no high school has ever played. The fix is structural, not cosmetic: the
# league is generated as ROUNDS (the circle method — every team plays exactly once per
# round), the first pass runs the rounds forward, the mid-season window goes in the
# middle, and the second pass runs them back the other way with the venue flipped. So a
# team meets its opponents A → B → … → G, breaks, then G → … → B → A, and the return
# match falls most of a season after the first one.
#
# `_rr_rounds` returns unordered pairs and `_orient` decides venue SEPARATELY, because
# the two are different constraints: the rounds fix WHO plays WHEN, the orientation bit
# fixes WHERE. One bit per pairing serves both meetings (pass 2 is its inverse), so
# "the return match reverses venue" holds by construction and cannot be broken by the
# home/away balancing, which only ever flips that one bit.

def _rr_rounds(n: int) -> list[list[tuple[int, int]]]:
    """Single round robin over 0..n-1 as ROUNDS, by the circle method.

    Every team appears at most once per round, so no program plays the same opponent on
    consecutive dates. An odd `n` gets a phantom entry whose pairing is dropped, which
    is the bye — that team simply has one fewer league date in the pass."""
    ix = list(range(n)) + ([None] if n % 2 else [])
    m = len(ix)
    rounds = []
    for _ in range(max(0, m - 1)):
        pairs = [(ix[i], ix[m - 1 - i]) for i in range(m // 2)]
        rounds.append([(min(a, b), max(a, b)) for a, b in pairs
                       if a is not None and b is not None])
        ix = [ix[0], ix[-1]] + ix[1:-1]           # rotate all but the fixed first seat
    return rounds


def _mirror_orders(n_rounds: int) -> list[list[int]]:
    """Candidate round orders for the SECOND pass, best separation first.

    ⚠️ A plain reverse is the obvious mirror and it is wrong at the fold. If pass 2 runs
    the rounds backwards, the LAST opponent of pass 1 is the FIRST of pass 2 — the two
    meetings land on consecutive league dates, which is the exact back-to-back pairing
    this whole rewrite exists to remove. It is invisible in a per-team card until you
    measure the gaps: eleven opponents beautifully spread, and one played twice in a row.

    So the second pass is a ROTATED mirror, and the rotation is chosen by measuring. A
    pair met in round `i` of pass 1 and round `j` of pass 2 (`order[j] == i`) is
    separated by `R + j - i` league dates. Every rotation of both families is scored by
    its WORST pair, and everything clearing HALF A PASS is kept:

      * serpentine  `rev`: pass 2 runs backwards, rotated — G → F → … → A
      * mirrored    `fwd`: pass 2 runs forwards, rotated  — A → B → … → G

    Un-rotated `fwd` is the textbook mirrored double round robin and scores a flat `R`,
    the maximum; the best serpentine reaches about `R/2`, which is still a return match
    half a season plus the whole mid-season window after the first meeting. Both clear
    the floor, so `district_rounds` draws from the band on the season seed and a
    program's opponent order genuinely differs year to year — which is the ask, since
    the second pass "does not need to be a perfect reverse every season". What does not
    vary is the floor."""
    R = n_rounds
    if R <= 1:
        return [list(range(R))]
    floor = (R + 1) // 2
    cands, seen = [], set()
    for family in ("rev", "fwd"):                 # serpentine first: it is the house shape
        for k in range(R):
            order = ([(R - 1 - j + k) % R for j in range(R)] if family == "rev"
                     else [(j + k) % R for j in range(R)])
            pos = {r: j for j, r in enumerate(order)}
            if min(R + pos[i] - i for i in range(R)) < floor:
                continue
            key = tuple(order)
            if key not in seen:                   # several k collapse at small R
                seen.add(key)
                cands.append(order)
    return cands or [list(range(R))]


def _venue_cost(seq: list[bool]) -> int:
    """How bad one team's home/away sequence is. Runs longer than two are penalised
    quadratically (three straight road dates is a real complaint; six is a different
    kind of complaint), plus a linear penalty for an unbalanced card. Round-robin
    scheduling treats both as first-class constraints rather than as an afterthought."""
    cost = run = 0
    for prev, cur in zip(seq, seq[1:]):
        run = run + 1 if prev == cur else 0
        if run >= 2:                               # a run of 3+ dates
            cost += (run - 1) ** 2
    return cost + abs(2 * sum(seq) - len(seq))


def _orient(order: list[list[tuple[int, int]]], mirror: list[int], n: int,
            rng: random.Random) -> dict[tuple[int, int], bool]:
    """Choose, per PAIRING, which meeting is at home — one bit that serves both passes.

    Seeded from the round/seat parity (a decent first cut), then greedily improved: flip
    any single bit that lowers the total venue cost, sweeping until nothing helps. Small
    districts make this trivial and a 12-team district has 66 bits, so a handful of
    sweeps is nothing next to simulating the duals themselves."""
    flip = {p: bool((r + i) % 2) for r, rnd in enumerate(order) for i, p in enumerate(rnd)}

    def sequences() -> dict[int, list[bool]]:
        seq: dict[int, list[bool]] = {t: [] for t in range(n)}
        for pass_no in (0, 1):
            rounds = order if pass_no == 0 else [order[i] for i in mirror]
            for rnd in rounds:
                for a, b in rnd:
                    home_is_a = flip[(a, b)] if pass_no == 0 else not flip[(a, b)]
                    seq[a].append(home_is_a)
                    seq[b].append(not home_is_a)
        return seq

    def total() -> int:
        return sum(_venue_cost(s) for s in sequences().values())

    pairs = [p for rnd in order for p in rnd]
    rng.shuffle(pairs)                             # deterministic, but not index-ordered
    best = total()
    for _ in range(4):
        improved = False
        for p in pairs:
            flip[p] = not flip[p]
            cost = total()
            if cost < best:
                best, improved = cost, True
            else:
                flip[p] = not flip[p]
        if not improved:
            break
    return flip


def district_rounds(teams: list[TeamSeason], year: int, salt: str = "") -> list[list[tuple]]:
    """The district's league card as an ordered list of ROUNDS of (home, away) teams —
    the first pass, then the second pass mirrored with venues reversed.

    The caller decides what goes BETWEEN the two passes (`run_season` puts the
    mid-season window there); playing the list straight through is a plain double round
    robin. The pass-2 rotation varies by season so a program's opponent order is not the
    same every year, and every variant is reproducible from the save seed."""
    n = len(teams)
    if n < 2:
        return []
    dname = teams[0].school.district
    rng = random.Random(f"{salt}|rr|{year}|{teams[0].school.gender}|{dname}")
    order = _rr_rounds(n)
    rng.shuffle(order)                    # which round leads varies by season
    variants = _mirror_orders(len(order))
    mirror = variants[rng.randrange(len(variants))]
    flip = _orient(order, mirror, n, rng)
    passes = [order, [order[i] for i in mirror]]
    out = []
    for pass_no, rounds in enumerate(passes):
        for rnd in rounds:
            date = []
            for a, b in rnd:
                home_is_a = flip[(a, b)] if pass_no == 0 else not flip[(a, b)]
                date.append((teams[a], teams[b]) if home_is_a else (teams[b], teams[a]))
            out.append(date)
    return out


def play_rounds(rounds: list[list[tuple]], year: int, salt: str, tag: str = "") -> None:
    """Play a list of rounds in order.

    ⚠️ The dual seed is derived from the PAIRING, never from its position in the list.
    A double round robin plays each unordered pair twice with the venue reversed, so the
    ORDERED pair (home, away) already identifies a dual uniquely — no round or seat index
    is needed, and including one would be a bug rather than extra entropy. The caller
    slices this list: `play_regular_season` plays `rounds[:half]`, runs the mid-season
    window, then plays `rounds[half:]`, and a local `enumerate` restarts at zero on the
    second call. Every second-pass dual would then be seeded differently from the same
    district played straight through by `play_district`, so a standalone run or a
    calibration script would produce different results for identical inputs. Keying on
    the pairing also makes a result independent of which rotation the season drew, which
    is the property you actually want: who wins depends on who is playing."""
    for date in rounds:
        for h, a in date:
            seed = int(hashlib.blake2s(
                f"{salt}|d|{year}|{tag}|{h.school.key}|{a.school.key}".encode(),
                digest_size=4).hexdigest(), 16)
            play_dual(h, a, seed=seed, phase="regular", district=True)


# --- district standings ------------------------------------------------------
#
# Place is district win %, and the TIEBREAK LADDER is the association's (owner rule
# 2027-08), in order:
#
#   1. HEAD-TO-HEAD record among the tied teams — a mini-league, so it settles a
#      three-way tie the same way it settles a two-way one.
#   2. If they split, the AGGREGATE of those meetings — courts won minus courts lost
#      across the season series, so a 6-1 / 3-4 split beats a 4-3 / 1-6 one.
#   3. Overall season record — the whole card, non-district included, deliberately.
#   4. Power Index (TOSS).
#   5. OOWP — opponents' opponents' win %, the deepest strength-of-schedule term.
#
# ⚠️ Every LEAGUE figure here is read off the district schedule entries, never off
# `points_for`/`points_against`. Those two fields accumulate over EVERY dual a team
# plays, non-district included, so using them to break a league tie lets a blowout in
# the early non-district window decide a district title. They are the right numbers for
# an overall margin and the wrong ones for anything labelled "district".

def _district_duals(t: TeamSeason, against: set[str] | None = None) -> list[dict]:
    """A team's league duals, optionally only those against a given set of schools."""
    return [x for x in t.schedule
            if x.get("district") and x.get("phase") == "regular"
            and (against is None or x["opp"] in against)]


def district_oowp(teams: list[TeamSeason]) -> dict[str, float]:
    """{school: opponents' opponents' win %} over the pool given.

    The last rung of the ladder, and the one that only ever matters when four teams have
    matched each other on everything else. Computed on overall win %, which is what OOWP
    means — the depth of a schedule is not a league-only property."""
    by = {t.school.name: t for t in teams}
    opps = {t.school.name: [x["opp"] for x in t.schedule if x.get("phase") == "regular"]
            for t in teams}

    def owp(name: str) -> float:
        seen = [by[o].win_pct for o in opps.get(name, ()) if o in by]
        return sum(seen) / len(seen) if seen else 0.0

    cache = {n: owp(n) for n in by}
    out = {}
    for name in by:
        seen = [cache[o] for o in opps.get(name, ()) if o in cache]
        out[name] = sum(seen) / len(seen) if seen else 0.0
    return out


def _tiebreak(group: list[TeamSeason], oowp: dict[str, float]) -> list[TeamSeason]:
    """Order teams that finished level on district win %, by the ladder above."""
    names = {t.school.name for t in group}
    h2h: dict[str, tuple[float, int]] = {}
    for t in group:
        met = _district_duals(t, names - {t.school.name})
        wins = sum(1 for x in met if x["won"])
        margin = sum(x["pf"] - x["pa"] for x in met)
        h2h[t.school.name] = (wins / len(met) if met else 0.0, margin)
    return sorted(group, key=lambda t: (
        -h2h[t.school.name][0],            # 1. head-to-head record
        -h2h[t.school.name][1],            # 2. aggregate of those meetings
        -t.win_pct,                        # 3. overall season record
        -t.power,                          # 4. Power Index (0.0 before it is computed)
        -oowp.get(t.school.name, 0.0),     # 5. OOWP
        t.school.name))


def settle_district(teams: list[TeamSeason],
                    oowp: dict[str, float] | None = None) -> list[TeamSeason]:
    """Sort by district win % with the tiebreak ladder, and stamp `district_place`.

    Split out of `play_district` so `run_season` can settle AFTER the Power Index exists
    — rung 4 of the ladder reads `t.power`, which is only stamped once the whole gender's
    regular season is finished. Settling earlier is not wrong, it just resolves that one
    rung as a tie and falls through to OOWP.

    A tie is resolved as a GROUP, not pairwise: head-to-head among three level teams is a
    mini-league, and a pairwise comparator on it would not even be transitive."""
    oowp = district_oowp(teams) if oowp is None else oowp
    teams.sort(key=lambda t: -t.district_pct)
    out: list[TeamSeason] = []
    i = 0
    while i < len(teams):
        j = i
        while j < len(teams) and teams[j].district_pct == teams[i].district_pct:
            j += 1
        out += _tiebreak(teams[i:j], oowp) if j - i > 1 else teams[i:j]
        i = j
    teams[:] = out
    for k, t in enumerate(teams, 1):
        t.district_place = k
    return teams


def play_district(teams: list[TeamSeason], year: int, salt: str = "") -> list[TeamSeason]:
    """Play the double round-robin straight through and settle district place. The
    standalone path (a single district, tests, calibration); `run_season` drives the two
    passes itself so it can put the mid-season window between them."""
    play_rounds(district_rounds(teams, year, salt), year, salt,
                teams[0].school.district if teams else "")
    power = power_index(teams)
    for t in teams:
        r = power.get(t.school.name)
        if r is not None:
            t.power = r.pi_raw
    return settle_district(teams)


# --- the Power Index (TOSS) ------------------------------------------------------
# At-large selection and seed order run on the POWER INDEX, not on raw win-loss.
# The model is TOSS — the Tennis Opponent-Strength System, oregontennis.org's
# three-part composite for rating high school programs statewide, and the same one
# `app.rating` already runs for the college league:
#
#     Power Index = 0.40 APR + 0.40 FQI + 0.20 oGS
#
#   APR  strength of schedule (RPI: 25% win% + 50% opponents' + 25% opponents'-opponents')
#   FQI  flight-weighted share of lines won, scaled by opponent APR / league median
#   oGS  share of GAMES won, scaled by the same opponent multiplier
#
# So beating a strong card across every flight rates above running up a record on a
# weak one, and a 4-3 win where you took the premier flights rates above a 4-3 win
# where you took the bottom of the lineup.
#
# Flight weights for the JHSAA's 5 singles / 2 doubles dual (owner rule 2027-08).
# #1 singles and #1 doubles carry EQUAL top weight, and the tail is deliberately steep:
# a team that wins the two premier flights has done most of the work, while depth at
# #4/#5 singles moves the number very little. They sum to a max of 3.70 per dual, which
# is the denominator of a fully contested match.
#
# These are the association's own numbers, not the college table (flatter across
# singles, doubles below #1 singles) and not Oregon's (a 4S/4D format that does not
# map). They are the only flight numbers in the pipeline — nothing else hard-codes one.
FLIGHT_WEIGHTS = {
    "S1": 1.00, "S2": 0.75, "S3": 0.25, "S4": 0.10, "S5": 0.10,
    "D1": 1.00, "D2": 0.50,
}
MAX_FLIGHT_WEIGHT = 3.70          # sum of the above; a fully contested dual


def _games(score: str) -> tuple[int, int]:
    """Games won by each side, parsed out of a line's score string ("6-4, 3-6, 7-5").

    Read back from the STRING rather than persisted alongside it: the archive already
    holds the score, so the opponent-weighted game share works on seasons that were
    played before the Power Index existed, and `world_jhsaa_dual` doesn't grow a column
    that would only ever restate what is already there."""
    h = a = 0
    for st in (score or "").split(","):
        bits = st.strip().split("-")
        if len(bits) != 2:
            continue
        try:
            h += int(bits[0]); a += int(bits[1])
        except ValueError:
            continue
    return h, a


def rating_duals(teams) -> list[dict]:
    """Every REGULAR-SEASON dual once, in the shape `rating.compute_ratings` consumes.

    A dual sits on BOTH sides' schedules, so only the home side's copy is taken —
    counting each meeting twice would flatten strength of schedule toward .500.

    Postseason duals — state AND the Tournament of Champions — are excluded on purpose.
    TOSS is the SEEDING input, so it has to be the regular season only; it would also
    drag the 1S/4D format's #3 and #4 doubles into a weight table that stops at #2,
    where they would silently take the fallback weight instead of a number anybody
    chose."""
    out = []
    for t in teams:
        for d in t.schedule:
            if not d.get("home") or d.get("phase") in POSTSEASON:
                continue
            lines = []
            for ln in d.get("lines") or ():
                hg, ag = _games(ln.get("score", ""))
                lines.append({"slot": ln.get("slot", ""), "home_won": ln.get("home_won"),
                              "home_games": hg, "away_games": ag})
            out.append({"home": t.school.name, "away": d["opp"], "home_won": d["won"],
                        "home_points": d["pf"], "away_points": d["pa"], "lines": lines})
    return out


def power_index(teams) -> dict:
    """Power Index for every program in a gender, keyed by school name.

    Run over the WHOLE gender rather than a classification at a time: non-district
    play crosses classifications, so a 7A team's schedule strength depends on the 6A
    teams it played, and rating each class in isolation would cut those edges out of
    the results graph."""
    from .rating import compute_ratings
    return compute_ratings(rating_duals(teams), weights=FLIGHT_WEIGHTS)


def qualifiers(group: str, standings: dict[str, list[TeamSeason]],
               power: dict | None = None) -> list[TeamSeason]:
    """The state field: automatic bids first (7A takes the top TWO from each district,
    everyone else the champion), then at-large until the bracket is full.

    At-large order and SEED order are the Power Index (`power`, from `power_index`);
    without one — a caller running a district in isolation — it falls back to win rate.
    An automatic bid still buys entry rather than a seed: a district champion with a
    thin index seeds below at-larges out of stronger districts."""
    auto_n, field_n = AUTO_PER_DISTRICT[group], FIELD[group]

    def key(t: TeamSeason):
        if power is not None and t.school.name in power:
            return (-power[t.school.name].pi_raw, t.school.name)
        return (-t.win_pct, -(t.points_for - t.points_against), t.school.name)

    auto, rest = [], []
    for teams in standings.values():
        auto.extend(teams[:auto_n])
        rest.extend(teams[auto_n:])
    rest.sort(key=key)
    field = auto + rest[:max(0, field_n - len(auto))]
    field.sort(key=key)
    return field[:field_n]


def run_state(field: list[TeamSeason], *, seed: int) -> dict:
    """The dual-team state tournament: 1S/4D, single elimination.

    The draw is SEEDED (`engine.tournament.seeded_draw`, the same helper the college
    championship uses): entrants go to the standard bracket anchors so the top seeds
    can only meet late, and a field that isn't a power of two seeds into the next size
    up with the **byes going to the top seeds**. A 12-team field is a 16 draw where
    seeds 1-4 sit out the opening round and seeds 5-12 play into an eight-team
    quarterfinal; a 24-team field is a 32 draw where the top eight sit out.

    The bracket is then FIXED — no reseeding between rounds (owner rule 2027-08; most
    states don't reseed either). Within a seed tier the anchors are shuffled, which is
    what `seeded_draw` does for the college championship too, so the pairings vary by
    seed while the tiers never do.

    It used to pad the field with `None` at the END of the slot list, which is not a
    draw at all: the Nones paired off with each other and vanished, nobody got a bye,
    and — because slot order was just finishing order — **the first round paired seed 1
    against seed 2**, seed 3 against seed 4, and so on. Every state tournament in the
    association was decided by a ladder that put its two best teams against each other
    first."""
    rng = random.Random(seed)
    size = 1
    while size < len(field):
        size *= 2
    # `n_seeds = len(field)`: the whole field is ranked (`qualifiers` orders it), so
    # every entrant is placed on its own anchor rather than drawn at random.
    from engine.tournament import seeded_draw
    slots: list[TeamSeason | None] = [None if r is None else field[r]
                                      for r in seeded_draw(len(field), size,
                                                           len(field), rng)]
    rounds = []
    while len(slots) > 1:
        nxt, games = [], []
        for i in range(0, len(slots), 2):
            a, b = slots[i], slots[i + 1]
            if a is None or b is None:              # bye
                nxt.append(a or b)
                continue
            res = play_dual(a, b, seed=rng.randrange(1 << 30), phase="state")
            win = a if res.winner == 0 else b
            games.append({"home": a.school.name, "away": b.school.name,
                          "home_points": res.home_points, "away_points": res.away_points,
                          "winner": win.school.name})
            nxt.append(win)
        if games:
            rounds.append(games)
        slots = nxt
    return {"champion": slots[0].school.name if slots and slots[0] else None,
            "rounds": rounds, "field": [t.school.name for t in field]}


def run_toc(champions: list[TeamSeason], *, seed: int) -> dict:
    """The TOURNAMENT OF CHAMPIONS — one dual-team champion for all of Jefferson.

    ONE champion per classification and nobody else — six teams now that 3A and 2A-1A
    crown separately. The field is not a `FIELD` size and never has been: it is exactly
    `len(GROUPS)`, and it grows or shrinks only when the association adds or merges a
    championship. (`FIELD` is the STATE tournament's bracket size per classification and
    has nothing to do with this event.)

    Seeded on the TOSS Power Index they finished the regular season with (`t.power`,
    already stamped by `play_regular_season`), NOT on classification: a 4A champion that
    rated above the 6A one is the higher seed, which is the whole reason the event is
    interesting.

    Six into a four-team semifinal, so the two lowest-rated pairs play in and the top two
    sit out; five would give one play-in and three byes. Then the semifinals and the
    final, under the state format (1S/4D) like the events that fed it.

    Returned in the same shape `run_state` uses, so it renders on the shared bracket tree
    with no new geometry."""
    field = sorted(champions, key=lambda t: (-t.power, t.school.name))
    if len(field) < 2:
        return {"champion": field[0].school.name if field else None,
                "rounds": [], "field": [t.school.name for t in field]}
    rng = random.Random(seed)

    def play(a: TeamSeason, b: TeamSeason) -> tuple[TeamSeason, dict]:
        # phase "toc", not "state": the shape and the lineup rules are the state
        # event's, but the dual has to be TELLABLE APART in `world_jhsaa_dual`, which
        # is all a program page has to read a TOC appearance back off.
        res = play_dual(a, b, seed=rng.randrange(1 << 30), phase="toc")
        win = a if res.winner == 0 else b
        return win, {"home": a.school.name, "away": b.school.name,
                     "home_points": res.home_points, "away_points": res.away_points,
                     "winner": win.school.name}

    # Cut to four in ONE round, then semifinals, then the final: 6 -> 4 -> 2 -> 1. The
    # play-in takes the bottom 2*(n-4) seeds and pairs them highest-against-lowest, so at
    # six the top two sit out while 3v6 and 4v5 play, and at five only 4v5 does. Playing
    # a single play-in regardless left five teams standing and produced a 6 -> 5 -> 3 -> 1
    # ladder — a three-team "semifinal" and a bye nobody earned.
    rounds: list[list[dict]] = []
    alive = list(field)
    if len(alive) > 4:
        n_in = 2 * (len(alive) - 4)
        block, byes = alive[-n_in:], alive[:-n_in]
        games, won = [], []
        for i in range(n_in // 2):
            w, gm = play(block[i], block[n_in - 1 - i])
            games.append(gm)
            won.append(w)
        rounds.append(games)
        alive = byes + won
    while len(alive) > 1:
        games, nxt = [], []
        for i in range(len(alive) // 2):
            w, gm = play(alive[i], alive[len(alive) - 1 - i])   # 1 v lowest, 2 v next
            games.append(gm)
            nxt.append(w)
        if len(alive) % 2:
            nxt.append(alive[len(alive) // 2])
        rounds.append(games)
        alive = nxt
    nxt = alive
    return {"champion": nxt[0].school.name if nxt else None,
            "rounds": rounds, "field": [t.school.name for t in field],
            "seeds": {t.school.name: i + 1 for i, t in enumerate(field)}}


_GROUP_IX = {g: i for i, g in enumerate(GROUPS)}   # 7A=0 … 3A-1A=4, so |i-j| = classes apart

# How a non-district opponent is chosen (owner rule 2027-08): geography first — you do
# not bus across Jefferson for a non-league dual — then talent, so a weak program isn't
# fed to teams that beat it every week. Because talent is read off THIS year's roster,
# the pairings re-form each season as programs rise and fall.
GEO_WEIGHT = 8.0          # per step of distance: same county 0, same area 1, else 2
SHORTLIST = 6             # score the candidates, then draw at random from the best few


def _strength(ts: TeamSeason) -> float:
    """Team talent: the mean current overall of the nine who'd dress. Read off the
    roster, not the record, so it doesn't depend on who happens to be scheduled yet."""
    top = sorted((p.current_overall() for p in ts.roster), reverse=True)[:9]
    return sum(top) / len(top) if top else 0.0


def _geo_gap(a: School, b: School) -> int:
    return 0 if a.county == b.county else (1 if a.area == b.area else 2)


def _nondistrict_pairs(teams: list[TeamSeason], rng: random.Random,
                       owed: dict[int, int], played: dict[int, set[str]]) -> list[tuple]:
    """PAIR the non-district card — it does not play it.

    Pairing and playing are separate because the season is no longer "all the
    non-district duals, then all the league ones". A card opens non-district, runs the
    league, breaks for a mid-season window and runs the league back; the same matcher
    fills each of those windows, so it has to be able to hand back pairs and let the
    caller decide when they happen.

    Opponents are drawn on the three things that actually decide a real non-league card:
      1. GEOGRAPHY  — same county, then same area, then anywhere (`GEO_WEIGHT`).
      2. TALENT     — nearest team strength, so the draw is competitive both ways.
      3. AVAILABILITY — both schools still owe duals this window, and haven't met.
    Classification is a gate on top: same level or ONE level apart, never further, so a
    7A card mixes 7A and 6A and never lands on 1A.

    `owed` and `played` are the CALLER'S dicts and are mutated in place, so quotas and
    the no-rematch rule carry across windows instead of each window rediscovering them."""
    strength = {id(t): _strength(t) for t in teams}
    short = lambda: [t for t in teams if owed.get(id(t), 0) > 0]          # noqa: E731
    pairs: list[tuple] = []
    need = short()
    guard = 0
    while len(need) > 1 and guard < 200000:
        guard += 1
        a = need[rng.randrange(len(need))]
        ga, sa = _GROUP_IX[a.school.group], strength[id(a)]
        cands = [t for t in need if t is not a
                 and (t.school.group, t.school.district)
                 != (a.school.group, a.school.district)
                 and t.school.name not in played[id(a)]
                 and abs(_GROUP_IX[t.school.group] - ga) <= 1]
        if not cands:
            owed[id(a)] = 0            # can't be topped up; drop it, don't stall the run
            need = short()
            continue
        cands.sort(key=lambda t: (GEO_WEIGHT * _geo_gap(a.school, t.school)
                                  + abs(strength[id(t)] - sa), t.school.name))
        b = cands[rng.randrange(min(SHORTLIST, len(cands)))]
        pairs.append((a, b))
        for x, y in ((a, b), (b, a)):
            owed[id(x)] -= 1
            played[id(x)].add(y.school.name)
        need = short()
    return pairs


def _play_pairs(pairs: list[tuple], rng: random.Random, *, challenge: bool = False) -> None:
    """Play a window's non-district pairs. Never district, so district place is
    untouched whatever else these results feed."""
    for a, b in pairs:
        play_dual(a, b, seed=rng.randrange(1 << 30), phase="regular",
                  district=False, challenge=challenge)


def play_regular_season(by_group: dict, year: int, gender: str,
                        salt: str = "") -> list[TeamSeason]:
    """Play a whole gender's regular season IN CALENDAR ORDER, and settle district place.

        early non-district → district pass 1 → mid-season window → district pass 2
                           → late non-district tune-up

    A dual's position in `schedule` is the only clock this association has — there is no
    date in the sim — so playing in this order IS the schedule. Every phase runs across
    the WHOLE gender before the next begins, which is what keeps one program's card in
    step with another's.

    `by_group` is {group: {district: [TeamSeason]}}. Takes a subset happily, which is how
    the schedule tests exercise this path rather than a re-implementation of it."""
    every_team = [t for st in by_group.values() for ts in st.values() for t in ts]
    xrng = random.Random(f"{salt}|xover|{gender}|{year}")

    # The non-district ALLOWANCE, split into windows up front. `owed`/`played` are shared
    # across every window, so a program's total card is the allowance it drew and no
    # pairing can quietly recreate a home-and-home that only the league is meant to have.
    quota = {id(t): NONDISTRICT_MIN + xrng.randrange(NONDISTRICT_MAX - NONDISTRICT_MIN + 1)
             for t in every_team}
    played: dict[int, set[str]] = {id(t): set() for t in every_team}
    reserved = MID_NONDISTRICT + (1 if CHALLENGE_ENABLED else 0)
    owed = {k: max(1, round((v - reserved) * EARLY_SHARE)) for k, v in quota.items()}
    _play_pairs(_nondistrict_pairs(every_team, xrng, owed, played), xrng)

    rounds = {(g, d): district_rounds(teams, year, salt)
              for g, st in by_group.items() for d, teams in st.items()}
    half = {k: len(v) // 2 for k, v in rounds.items()}
    for key, rr in rounds.items():
        play_rounds(rr[:half[key]], year, salt, key[1])

    # --- the mid-season window: a non-district date, then the challenge ---
    owed = {id(t): MID_NONDISTRICT for t in every_team}
    _play_pairs(_nondistrict_pairs(every_team, xrng, owed, played), xrng)
    if CHALLENGE_ENABLED:
        _play_pairs(_challenge_pairs(by_group, year, salt, played), xrng, challenge=True)

    for key, rr in rounds.items():
        play_rounds(rr[half[key]:], year, salt, key[1])

    # --- the late tune-up: whatever the allowance has left ---
    spent = {id(t): sum(1 for s in t.schedule if not s["district"]) for t in every_team}
    owed = {id(t): max(0, quota[id(t)] - spent[id(t)]) for t in every_team}
    _play_pairs(_nondistrict_pairs(every_team, xrng, owed, played), xrng)

    # Power Index BEFORE settling: rung 4 of the tiebreak ladder reads `t.power`, and it
    # is a function of the whole pool's results graph, so it cannot exist until every
    # regular-season dual is played. Computed once here and handed back, so `run_season`
    # does not recompute a ~5,000-dual rating it already has.
    power = power_index(every_team)
    for t in every_team:
        r = power.get(t.school.name)
        if r is not None:
            t.power = r.pi_raw
    oowp = district_oowp(every_team)
    for st in by_group.values():
        for teams in st.values():
            settle_district(teams, oowp)
    return every_team, power


def _challenge_pairs(by_group: dict, year: int, salt: str,
                     played: dict[int, set[str]]) -> list[tuple]:
    """The mid-season challenge slate, paired on how the season has actually gone.

    Run at the break, AFTER the first league pass, which is the whole idea: rank each
    district by its league record so far and match a #3 against another district's #3.
    That is a useful dual; the same programs paired in February on roster strength would
    have been another arbitrary non-league date.

    The early non-district card cannot work this way and must not be changed to — it is
    seeded on roster strength precisely so it can run BEFORE any results exist. This
    window is the one place in the season where a pairing reads results, and it can only
    exist because it sits after a pass.

    Pairing is greedy over (place gap, travel, level gap), gated to the same
    classification or one apart and never a rematch. Hosting alternates on a stable hash
    of the two school names and the year, so a program is not systematically at home."""
    slate: list[tuple] = []
    for group, dists in by_group.items():
        # Provisional standing INSIDE each district, on league results only.
        # LEAGUE results only, and the margin comes off the district duals — not
        # `points_for`/`points_against`, which accumulate over the early non-district
        # window too. Reading those here would let a February blowout against another
        # district decide who a program draws in the challenge, in a pairing whose whole
        # premise is "how the LEAGUE season has gone".
        ranked: list[tuple[int, TeamSeason]] = []
        for teams in dists.values():
            order = sorted(teams, key=lambda t: (
                -t.district_pct,
                -sum(x["pf"] - x["pa"] for x in _district_duals(t)),
                t.school.name))
            ranked += [(i, t) for i, t in enumerate(order, 1)]
        pool = sorted(ranked, key=lambda r: (r[0], r[1].school.name))
        taken: set[int] = set()
        for place, a in pool:
            if id(a) in taken:
                continue
            best = None
            for pl, b in pool:
                if id(b) in taken or b is a:
                    continue
                if b.school.district == a.school.district:
                    continue
                if abs(pl - place) > CHALLENGE_PLACE_SLACK:
                    continue
                if b.school.name in played[id(a)]:
                    continue
                score = (abs(pl - place) * 10.0
                         + CHALLENGE_GEO_WEIGHT * _geo_gap(a.school, b.school))
                if best is None or score < best[0]:
                    best = (score, b)
            if best is None:
                continue
            b = best[1]
            taken.add(id(a)); taken.add(id(b))
            # Host alternates on the pairing + the year, not on who was listed first.
            key = "|".join(sorted((a.school.name, b.school.name)))
            h = int(hashlib.blake2s(f"{salt}|chal|{year}|{group}|{key}".encode(),
                                    digest_size=4).hexdigest(), 16)
            slate.append((a, b) if h % 2 == 0 else (b, a))
            for x, y in ((a, b), (b, a)):
                played[id(x)].add(y.school.name)
    return slate


# --- awards -------------------------------------------------------------------
ALL_DISTRICT_N = 6            # per district, per gender
ALL_STATE_N = 6               # per classification group


def _player_rows(teams: list[TeamSeason]) -> list[dict]:
    rows = []
    for t in teams:
        for pid, (w, l) in t.records.items():
            p = t.by_pid.get(pid)
            if p is None:
                continue
            rows.append({"pid": pid, "name": p.name, "grade": p.grade,
                         "school": t.school.name, "district": t.school.district,
                         "group": t.school.group, "wins": w, "losses": l,
                         "pct": w / (w + l) if (w + l) else 0.0,
                         "ovr": p.current_overall()})
    return rows


def _rank(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (-r["wins"], -r["pct"], -r["ovr"], r["name"]))


def season_awards(teams: list[TeamSeason]) -> dict:
    """All-District, All-State and Player of the Year for one classification group.

    Individual honours off individual records — wins first, then win rate, then ability
    as the tiebreak. Jefferson is the only association with a simulated high-school
    season, so it is the only state whose recruits arrive with honours attached."""
    rows = _player_rows(teams)
    by_district: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_district[r["district"]].append(r)
    all_district = {d: _rank(rs)[:ALL_DISTRICT_N] for d, rs in by_district.items()}
    all_state = _rank(rows)[:ALL_STATE_N]
    return {"all_district": all_district, "all_state": all_state,
            "poy": all_state[0] if all_state else None}


def honors_for(pid: str, awards: dict, group: str) -> list[str]:
    """The honours one player earned, newest-sounding first."""
    out = []
    if awards.get("poy") and awards["poy"]["pid"] == pid:
        out.append(f"{group} Player of the Year")
    if any(r["pid"] == pid for r in awards.get("all_state", ())):
        out.append(f"All-State ({group})")
    for dname, rs in awards.get("all_district", {}).items():
        if any(r["pid"] == pid for r in rs):
            out.append(f"All-District ({dname})")
            break
    return out


_season_cache: dict = {}


def run_season(gender: str, year: int, *, seed: int = 0, salt: str = "") -> dict:
    """One full JHSAA season for `gender`: every district's regular season, the
    crossover schedule, the awards, and the five state tournaments.

    Memoized per (salt, gender, year, seed) — a season is deterministic, and both the
    recruit hand-off and any page that wants standings would otherwise re-simulate
    thousands of duals. Computed into a local and published, never returned out of the
    dict, per the threaded-worker rule in CLAUDE.md."""
    from app import overrides as _ov
    ck = (salt, gender, year, seed, _ov.jhsaa_archetype_version())
    hit = _season_cache.get(ck)
    if hit is not None:
        return hit
    out = {"year": year, "gender": gender, "groups": {}, "teams": {}, "awards": {}}
    # ORDER OF PLAY, and it is the shape of the season (owner rule 2027-08):
    #
    #   early non-district → district pass 1 → MID-SEASON WINDOW → district pass 2
    #                      → late non-district → district/state postseason
    #
    # It used to be "all the non-district duals, then the whole double round-robin", and
    # inside that round-robin every opponent was played home-and-away on back-to-back
    # dates. Both halves of that were wrong for a high-school card, and the second half
    # was the visible one. The league is now two SEPARATED passes (`district_rounds`)
    # with the non-district card spread around and through them.
    #
    # A dual's ORDER IN `schedule` is the only clock this association has — there is no
    # date in the sim, and `state._jh_dates` lays the persisted order on a spring
    # calendar — so playing in this order IS the schedule. Everything here plays a whole
    # phase across the WHOLE gender before moving on, which is what keeps every
    # program's card in step with every other one's.
    #
    # Non-district pairing still seeds on ROSTER STRENGTH, not results, so the early
    # window can lead. The one exception is the mid-season challenge, which is paired at
    # the break precisely because by then there are results worth pairing on.
    by_group = {group: {dname: district_teams(schools, year, salt)
                        for dname, schools in sorted(districts(gender, group).items())}
                for group in GROUPS}
    every_team, power = play_regular_season(by_group, year, gender, salt)
    # TOSS was computed over the whole gender inside `play_regular_season` — once, on the
    # finished regular season, before any state tournament, since it is both the seeding
    # input and rung 4 of the district tiebreak. Across all classifications together
    # because non-district play crosses them: rating a class in isolation would cut those
    # edges out of the results graph.
    out["power"] = power
    for group in GROUPS:
        standings = by_group[group]
        all_teams = [t for ts in standings.values() for t in ts]
        out["awards"][group] = season_awards(all_teams)
        field = qualifiers(group, standings, power)
        state = run_state(field, seed=seed + hash(group) % 9973)
        out["groups"][group] = {
            # `drecord`/`place` are archived alongside the overall record so a program's
            # year-by-year history reads like a college team's, without re-simulating.
            # `pi` is the TOSS Power Index the season was SEEDED on — archived, never
            # recomputed on read. The rating is a function of the whole gender's results
            # graph, so a later read could only reproduce it by chance, and a ranking
            # that drifts away from the seeds it produced is the NCAA bracket's
            # region-drift bug in a new league.
            #
            # Stored at FULL precision, deliberately. It was rounded to 6dp once, which
            # looks harmless — nothing displays more than 3 — but `qualifiers` seeds on
            # `pi_raw` while `world.jhsaa_group_ranking` re-sorts these stored values and
            # breaks ties by school name. Two teams inside 1e-6 of each other (measured
            # gaps get to 1.0e-06) collapse to the same stored number and the ranking
            # then contradicts the seeds it is supposed to explain. Round for the eye,
            # in the template; never in the archive.
            "standings": {d: [{"school": t.school.name, "record": t.record,
                               "drecord": t.district_record, "place": t.district_place,
                               "pf": t.points_for, "pa": t.points_against,
                               "pi": t.power}
                              for t in ts] for d, ts in standings.items()},
            "state": state,
        }
        out.setdefault("_champ_teams", {})[group] = next(
            (t for ts in standings.values() for t in ts
             if t.school.name == state["champion"]), None)
        for ts in standings.values():
            for t in ts:
                out["teams"][t.school.name] = t
    # The Tournament of Champions, last: it needs all five classification champions and
    # the Power Index they finished the regular season on.
    champs = [t for t in out.pop("_champ_teams", {}).values() if t is not None]
    out["toc"] = run_toc(champs, seed=seed + 7717)
    _season_cache[ck] = out
    return out


# --- the hand-off to the college recruit board --------------------------------

def graduating_class(gender: str, year: int, *, seed: int = 0, salt: str = "",
                     limit: int | None = None) -> list[Prospect]:
    """Jefferson's entry into the college recruit rankings: this year's JHSAA seniors,
    ranked by what they actually did, carrying their high-school record.

    Roughly 780 girls and 670 boys graduate a year against ~188 board slots per gender,
    so `limit` takes the best of them and the rest simply don't play college tennis —
    which is what happens. Selection is on RESULTS; nothing here touches a player's
    hidden ceiling, so who develops is still unknown.
    """
    season = run_season(gender, year, seed=seed, salt=salt)
    grads = []
    for name, ts in season["teams"].items():
        awards = season["awards"].get(ts.school.group, {})
        ladder = {p.pid: i + 1 for i, p in enumerate(ts.roster)}
        for p in [x for x in ts.roster if x.grade == 12]:
            w, l = ts.records.get(p.pid, [0, 0])
            p.high_school = name
            p.jhsaa = {
                "school": name, "district": ts.school.district,
                "group": ts.school.group, "classification": ts.school.classification,
                "team_record": ts.record, "district_record": ts.district_record,
                "ladder": ladder.get(p.pid, 0), "year": year,
                "record": f"{w}-{l}", "wins": w, "losses": l,
                "honors": honors_for(p.pid, awards, ts.school.group),
                "state_champion": season["groups"][ts.school.group]["state"]["champion"] == name,
            }
            grads.append(p)
    # best first: team strength then ladder position — a #1 at a strong 7A program
    # outranks a #1 at a thin 3A one, which is the whole point of classifications.
    grads.sort(key=lambda p: -p.current_overall())
    return grads[:limit] if limit else grads


def apply_to_class(klass, gender: str, grad_year: int, salt: str) -> int:
    """Replace the Jefferson recruits in an already-generated national class with the
    JHSAA seniors who actually just graduated. Returns how many were swapped.

    Identity swap only — the class SIZE, the Jefferson slot count and the RNG stream
    are all untouched, so `US_JUNIOR_TENNIS_ORIGIN_WEIGHTS["JF"]` still decides HOW MANY
    Jefferson kids reach the board and this decides WHICH ones and what they have done.
    pids are preserved too, so `world_signing` / `world_roster` lookups keyed on the
    slot still resolve.

    Ability comes across, but nothing here touches a recruit's hidden ceiling, so a
    four-year high-school record still tells you who is good TODAY and not who grows.
    """
    slots = [p for p in klass.recruits if getattr(p, "region", "") == "Jefferson"]
    if not slots:
        return 0
    grads = graduating_class(_GENDER[gender], grad_year, salt=salt, limit=len(slots))
    # Rank-match: the best Jefferson senior becomes the best Jefferson recruit, and so
    # on down. IDENTITY and RECORD transfer; ABILITY does not.
    #
    # Copying the graduate's grades across looked obvious and was wrong: the national
    # class has already decided how many Jefferson recruits there are and how they
    # spread across the talent range, and overwriting that re-calibrated the whole
    # board — Jefferson's median recruit jumped to #278 of 2500 and the state swamped
    # the national top 10%. The high-school bands only have to make high-school tennis
    # look right; they are not a second opinion on the recruit curve.
    slots.sort(key=lambda p: -p.current_overall())
    for slot, grad in zip(slots, grads):
        slot.name = grad.name
        slot.hometown = grad.hometown
        slot.high_school = grad.high_school
        slot.jhsaa = grad.jhsaa          # a real Prospect field, so it survives signing
    return min(len(slots), len(grads))


_GENDER = {"men": "boys", "male": "boys", "boys": "boys",
           "women": "girls", "female": "girls", "girls": "girls"}


def mark(school: School, size: int = 72) -> str:
    """The school's athletic crest as inline SVG (see app/jhsaa_marks.py). The ported
    generator takes prep-network's raw record shape, so adapt rather than fork it."""
    from .jhsaa_marks import school_mark
    return school_mark({"name": school.name, "mascot": school.mascot,
                        "colors": school.colors}, size)


def career(school_name: str, gender: str, name: str, grad_year: int,
           salt: str = "") -> list[dict]:
    """A player's four high-school seasons, grade 9 through 12.

    Rebuilt on demand rather than stored: a career is deterministic from (school,
    gender, entry year, seat), so replaying it costs a roster build per year — no duals,
    no persistence, milliseconds. Returns [] if the player can't be resolved (the school
    no longer sponsors, or the name isn't on those rosters).
    """
    g = _GENDER.get(gender, gender)
    school = next((s for s in load_schools(g) if s.name == school_name), None)
    if school is None:
        return []
    out = []
    for grade in GRADES:
        year = grad_year - (12 - grade)
        roster = build_roster(school, year, salt)
        for i, p in enumerate(roster, 1):
            if p.name == name:
                out.append({"year": year, "grade": grade, "ladder": i,
                            "ovr": round(p.current_overall(), 1),
                            "str": p.str_value(), "school": school_name,
                            "classification": school.classification,
                            "district": school.district})
                break
    return out
