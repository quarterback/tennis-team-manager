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

GROUPS = ("7A", "6A", "5A", "4A", "3A-1A")
GENDERS = ("girls", "boys")

# --- formats ----------------------------------------------------------------
FORMATS = {
    "regular": DualFormat(n_singles=5, n_doubles=2, doubles_team_point=False),
    "state":   DualFormat(n_singles=1, n_doubles=4, doubles_team_point=False),
}


def dual_format(phase: str) -> DualFormat:
    """The dual shape for `phase` ("regular" | "district" | "state"). District
    tournaments play the regular-season shape; only the state event switches."""
    return FORMATS["state"] if phase == "state" else FORMATS["regular"]


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

# High school runs at "fast" fidelity, deliberately. `full` resolves every POINT, which
# is 6.7x the cost and is meant for the college season you actually watch; a season here
# is ~5,100 duals per gender and at full fidelity it added ~100s to the first recruit
# class build — on the request thread, which is the outage class CLAUDE.md warns about.
# Winners, scores and individual records are all unaffected; only per-point box detail is.
FIDELITY = "fast"

# --- state tournament (owner-decided) ---------------------------------------
# field size, and how many per district qualify automatically. 7A is deliberately the
# most district-driven classification: two from every district get in on the court.
FIELD = {"7A": 32, "6A": 24, "5A": 24, "4A": 16, "3A-1A": 8}
AUTO_PER_DISTRICT = {"7A": 2, "6A": 1, "5A": 1, "4A": 1, "3A-1A": 1}

# --- talent ------------------------------------------------------------------
# (mean, spread) of the 20-80 grade per classification. Well beneath the college bands
# (D1 men 60/16, D3 men 39/27) and far wider — a 7A roster and a 1A roster barely
# belong to the same sport. Girls sit a little under boys, mirroring the college split.
# NOTE these are CEILING targets, not current ability: `generate_prospect` treats
# `talent` as the potential and derives a much lower current from maturity, so a 7A
# number one with a ceiling of 46 still plays at a current ~30 while in school. That is
# the whole reason the bands look high for high schoolers — do not "fix" them downward
# by comparing them to the college _TALENT means, which ARE current.
# Calibrated so the top-190 graduating seniors slot into the national recruit class
# sensibly: best ~#25 of 2500, median near the national median. See `graduating_class`.
_TALENT = {
    ("7A", "boys"):   (58.0, 15.0), ("7A", "girls"):   (53.0, 14.0),
    ("6A", "boys"):   (53.0, 14.0), ("6A", "girls"):   (48.0, 13.0),
    ("5A", "boys"):   (48.0, 13.0), ("5A", "girls"):   (44.0, 12.0),
    ("4A", "boys"):   (44.0, 12.0), ("4A", "girls"):   (40.0, 11.0),
    ("3A-1A", "boys"): (39.0, 11.0), ("3A-1A", "girls"): (36.0, 10.0),
}
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

def _ceiling(rng: random.Random, group: str, gender: str) -> float:
    """A player's CEILING, drawn independently per player. The ladder is not assigned —
    it emerges from who is actually best, so a great freshman can play number one over a
    senior, which is how high school works."""
    mean, spread = _TALENT[(group, gender)]
    return max(GRADE_FLOOR, min(80.0, rng.gauss(mean, spread)))


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
    out = []
    for grade in GRADES:
        entry = year - (grade - 9)
        for seat in range(PER_CLASS):
            rng = random.Random(f"{salt}|jhsaa|{school.key}|{entry}|{seat}")
            nm, _ = make_name_picker(random.Random(rng.randrange(1 << 30)), gender=sex,
                                     region_weights={"us": 1.0})()
            p = generate_prospect(rng, nm, "US", gender=sex,
                                  talent=_ceiling(rng, school.group, school.gender),
                                  maturity_range=_MATURITY[grade],
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
    return Team(name=ts.school.name, singles=singles,
                doubles=[(2 * i, 2 * i + 1) for i in range(f.n_doubles)],
                doubles_players=dbl)


_SLOT = re.compile(r"^([SD])(\d+)$")

# Bench rotation (owner rule 2027-08): the lineup is re-set match to match on the BEST
# PERFORMING nine — results first, then OVR, STR last — so a hot bench player earns his
# way in. On top of that, coaches USE the bench in the regular season: most duals a
# reserve or two rotates into the bottom of the lineup, so nobody persisted plays zero
# times across a ~26-dual year (which would be absurd). The POSTSEASON is strict:
# your best nine, no rotation. (No injuries here — the JHSAA has no injury system.)
_ROTATE_ONE = 0.45          # chance the 9th seat goes to a bench player, per dual
_ROTATE_TWO = 0.15          # chance the 8th seat does too


def _order(ts: TeamSeason) -> list:
    """The ladder as the coach reads it: results, then ability, then STR."""
    def key(p):
        w, l = ts.records.get(p.pid, [0, 0])
        pct = w / (w + l) if (w + l) else 0.0
        return (-w, -pct, -p.current_overall(), -p.str_value())
    return sorted(ts.roster, key=key)


def _lineup(ts: TeamSeason, phase: str, rng: random.Random) -> list:
    """The nine who dress for THIS dual."""
    order = _order(ts)
    need = lineup_need(phase)
    nine, bench = order[:need], order[need:]
    if phase != "state" and bench:                 # playoffs: strict best nine
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
              district: bool = False):
    """One dual. Always to completion — high school has no clinch. `district` marks it
    as counting toward district place as well as the overall record."""
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
                       "won": res.winner == 0, "district": district, "lines": lines})
    b.schedule.append({"opp": a.school.name, "home": False, "phase": phase,
                       "pf": res.away_points, "pa": res.home_points,
                       "won": res.winner == 1, "district": district, "lines": lines})
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


def play_district(teams: list[TeamSeason], year: int, salt: str = "") -> list[TeamSeason]:
    """Play the double round-robin and settle district place. Returns `teams`, sorted
    by finish (district win %, then point differential)."""
    dname = teams[0].school.district if teams else ""
    rng = random.Random(f"{salt}|dist|{year}|{dname}")
    for i, a in enumerate(teams):
        for b in teams[i + 1:]:
            for leg in (0, 1):                      # home and away
                h, w = (a, b) if leg == 0 else (b, a)
                play_dual(h, w, seed=rng.randrange(1 << 30), phase="regular",
                          district=True)
    teams.sort(key=lambda t: (-t.district_pct, -(t.points_for - t.points_against),
                              t.school.name))
    for i, t in enumerate(teams, 1):
        t.district_place = i
    return teams


def qualifiers(group: str, standings: dict[str, list[TeamSeason]]) -> list[TeamSeason]:
    """The state field: automatic bids first (7A takes the top TWO from each district,
    everyone else the champion), then at-large by record until the bracket is full."""
    auto_n, field_n = AUTO_PER_DISTRICT[group], FIELD[group]
    auto, rest = [], []
    for teams in standings.values():
        auto.extend(teams[:auto_n])
        rest.extend(teams[auto_n:])
    rest.sort(key=lambda t: (-t.win_pct, -(t.points_for - t.points_against), t.school.name))
    field = auto + rest[:max(0, field_n - len(auto))]
    field.sort(key=lambda t: (-t.win_pct, -(t.points_for - t.points_against), t.school.name))
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


def _crossover(teams: list[TeamSeason], rng: random.Random) -> None:
    """The non-district half of the schedule. Run over the WHOLE gender at once.

    The district double round-robin is 10-22 duals by district size; each team then adds
    NONDISTRICT_MIN..MAX more against schools from OTHER districts. These count toward
    the overall record and toward at-large selection, but NOT toward district place:
    that is decided on district duals alone.

    Opponents are drawn on the three things that actually decide a real non-league card:
      1. GEOGRAPHY  — same county, then same area, then anywhere (`GEO_WEIGHT`).
      2. TALENT     — nearest team strength, so the draw is competitive both ways.
      3. AVAILABILITY — both schools still owe non-district duals, and haven't met.
    Classification is a gate on top: same level or ONE level apart, never further, so a
    7A card mixes 7A and 6A and never lands on 1A."""
    owed = {id(t): NONDISTRICT_MIN + rng.randrange(NONDISTRICT_MAX - NONDISTRICT_MIN + 1)
            for t in teams}
    strength = {id(t): _strength(t) for t in teams}
    # Who each team has already faced, so a non-district draw can't quietly recreate the
    # home-and-home that only the district round-robin is supposed to have.
    played: dict[int, set[str]] = {id(t): {s["opp"] for s in t.schedule} for t in teams}
    short = lambda: [t for t in teams if owed[id(t)] > 0]          # noqa: E731
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
        play_dual(a, b, seed=rng.randrange(1 << 30), phase="regular", district=False)
        for x, y in ((a, b), (b, a)):
            owed[id(x)] -= 1
            played[id(x)].add(y.school.name)
        need = short()


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
    ck = (salt, gender, year, seed)
    hit = _season_cache.get(ck)
    if hit is not None:
        return hit
    out = {"year": year, "gender": gender, "groups": {}, "teams": {}, "awards": {}}
    # Order of play, and it matters: NON-DISTRICT FIRST, then league (owner rule
    # 2027-08) — the front-loaded non-conference schedule of real life and of the college
    # sim, where `season.place()` gates a team's conference duals behind its own last
    # non-conf week. So: build every roster, play ONE crossover across the whole gender
    # (it crosses classifications, so it can't run a classification at a time), then the
    # district round-robins. Crossover can lead because it seeds on roster strength, not
    # on results. Awards and state selection read the finished records and come last.
    by_group = {group: {dname: district_teams(schools, year, salt)
                        for dname, schools in sorted(districts(gender, group).items())}
                for group in GROUPS}
    _crossover([t for st in by_group.values() for ts in st.values() for t in ts],
               random.Random(f"{salt}|xover|{gender}|{year}"))
    for st in by_group.values():
        for teams in st.values():
            play_district(teams, year, salt)
    for group in GROUPS:
        standings = by_group[group]
        all_teams = [t for ts in standings.values() for t in ts]
        out["awards"][group] = season_awards(all_teams)
        field = qualifiers(group, standings)
        state = run_state(field, seed=seed + hash(group) % 9973)
        out["groups"][group] = {
            # `drecord`/`place` are archived alongside the overall record so a program's
            # year-by-year history reads like a college team's, without re-simulating.
            "standings": {d: [{"school": t.school.name, "record": t.record,
                               "drecord": t.district_record, "place": t.district_place,
                               "pf": t.points_for, "pa": t.points_against}
                              for t in ts] for d, ts in standings.items()},
            "state": state,
        }
        for ts in standings.values():
            for t in ts:
                out["teams"][t.school.name] = t
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
