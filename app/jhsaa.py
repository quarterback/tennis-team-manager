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


def lineup_need(phase: str) -> int:
    """Players a program must dress for `phase` with nobody doubling up."""
    f = dual_format(phase)
    return f.n_singles + 2 * f.n_doubles          # 5+4 = 9 regular, 1+8 = 9 state


ROSTER_SIZE = 12          # 9 is the hard floor; carry depth for injuries and rotation

# JHSAA regular-season dual limit (owner rule 2027-08), closer to baseball's than to a
# college tennis schedule. The POSTSEASON IS EXEMT from it.
# A district of 9-12 plays 16-22 duals in its double round-robin, which fits inside the
# limit and leaves room for non-district crossover to top a team up. An earlier draft of
# the design doc said "~14 duals", which no district size could satisfy.
SEASON_MIN, SEASON_MAX = 28, 33

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


def _squad(ts: TeamSeason, phase: str) -> Team:
    """Dress a lineup for `phase`. Singles take the top of the ladder; doubles is its
    OWN roster below them (`Team.doubles_players`), so the state format's four doubles
    pairs are eight different players rather than the singles six re-permuted."""
    f = dual_format(phase)
    r = ts.roster
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


def _line_players(ts: TeamSeason, phase: str, slot: str) -> list:
    """The players who played `slot` ("S3", "D2") for `ts`, by the SAME indexing
    `_squad` dressed them with — never a second opinion on who was on court."""
    m = _SLOT.match(slot or "")
    if not m:
        return []
    kind, i = m.group(1), int(m.group(2))
    f, r = dual_format(phase), ts.roster
    if not r:
        return []
    at = lambda k: r[k % len(r)]                                  # noqa: E731
    if kind == "S":
        return [at(i - 1)]
    base = f.n_singles + 2 * (i - 1)
    return [at(base), at(base + 1)]


def _credit(ts: TeamSeason, phase: str, slot: str, won: bool) -> None:
    for p in _line_players(ts, phase, slot):
        rec = ts.records.setdefault(p.pid, [0, 0])
        rec[0 if won else 1] += 1
        ts.by_pid.setdefault(p.pid, p)


def play_dual(a: TeamSeason, b: TeamSeason, *, seed: int, phase: str = "regular",
              district: bool = False):
    """One dual. Always to completion — high school has no clinch. `district` marks it
    as counting toward district place as well as the overall record."""
    res = simulate_dual(_squad(a, phase), _squad(b, phase), seed=seed,
                        play_all=True, dual_fmt=dual_format(phase))
    for ln in res.lines:                       # individual records, for awards
        hw = getattr(ln, "home_won", None)
        if hw is None:
            continue
        _credit(a, phase, getattr(ln, "slot", ""), bool(hw))
        _credit(b, phase, getattr(ln, "slot", ""), not hw)
    a.points_for += res.home_points
    a.points_against += res.away_points
    b.points_for += res.away_points
    b.points_against += res.home_points
    # DualResult.winner is an INT — 0 home, 1 away. Comparing it to "home" silently
    # credits the away team every dual, which in a home-and-home round-robin leaves
    # every side at exactly .500 with correct-looking point differentials. Cost an hour.
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
    """A district's regular season: double round-robin, 5S/2D, every match completed.
    Returns its teams ordered by finish (win %, then point differential)."""
    teams = [TeamSeason(school=s, roster=build_roster(s, year, salt)) for s in schools]
    rng = random.Random(f"{salt}|dist|{year}|{schools[0].district if schools else ''}")
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
    """The dual-team state tournament: 1S/4D, single elimination. A field that isn't a
    power of two seeds into the next one up and the top seeds take first-round byes —
    a 24-team field is a 32 draw with 8 byes."""
    rng = random.Random(seed)
    size = 1
    while size < len(field):
        size *= 2
    slots: list[TeamSeason | None] = list(field) + [None] * (size - len(field))
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


def _crossover(teams: list[TeamSeason], rng: random.Random) -> None:
    """Non-district duals, to bring every team up to the season limit.

    A district double round-robin is 16-22 duals depending on its size, and the limit is
    28-33, so the balance is played against schools from OTHER districts in the same
    classification — which is what a real high-school schedule looks like. These count
    toward the overall record and toward at-large selection, but NOT toward district
    place: that is decided on district duals alone."""
    target = SEASON_MIN + rng.randrange(SEASON_MAX - SEASON_MIN + 1)
    need = [t for t in teams if t.wins + t.losses < target]
    guard = 0
    while len(need) > 1 and guard < 20000:
        guard += 1
        a = need[rng.randrange(len(need))]
        pool = [t for t in need if t.school.district != a.school.district and t is not a]
        if not pool:
            break
        b = pool[rng.randrange(len(pool))]
        play_dual(a, b, seed=rng.randrange(1 << 30), phase="regular", district=False)
        need = [t for t in teams if t.wins + t.losses < target]


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


def run_season(gender: str, year: int, *, seed: int = 0, salt: str = "") -> dict:
    """One full JHSAA season for `gender`: every district's regular season, then the
    five state tournaments. Returns results plus the graduating seniors."""
    out = {"year": year, "gender": gender, "groups": {}, "teams": {}, "awards": {}}
    for group in GROUPS:
        standings = {}
        for dname, schools in sorted(districts(gender, group).items()):
            standings[dname] = run_district(schools, year, seed=seed, salt=salt)
        all_teams = [t for ts in standings.values() for t in ts]
        _crossover(all_teams, random.Random(f"{salt}|xover|{gender}|{group}|{year}"))
        out["awards"][group] = season_awards(all_teams)
        field = qualifiers(group, standings)
        state = run_state(field, seed=seed + hash(group) % 9973)
        out["groups"][group] = {
            "standings": {d: [{"school": t.school.name, "record": t.record,
                               "pf": t.points_for, "pa": t.points_against}
                              for t in ts] for d, ts in standings.items()},
            "state": state,
        }
        for ts in standings.values():
            for t in ts:
                out["teams"][t.school.name] = t
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
