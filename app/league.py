"""
Multi-season League — in-memory dynasty state that makes development and the
transfer pathway real.

`new_league()` sims an opening season (persistent rosters + live STR).
`advance_year()` then, deterministically:
  1. graduates seniors (Fr→So→Jr→Sr),
  2. develops every returning player one year (`Prospect.develop_year`),
  3. runs the TRANSFER PORTAL: reliable players whose live STR has climbed well
     above their program's level move UP to a stronger program with an open
     slot (calibration: ~8–10% of players move/yr, ~25–35% of movers up),
  4. intakes a fresh freshman class to refill rosters,
  5. re-sims the season → new live STR.

Single division in v1 (transfer-up = low-strength → higher-strength program
within the division). Deterministic: every draw uses random.Random((seed,year)).
The cross-division portal (D3→D2→D1) is the documented next step.
"""
from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field

import app.ncaa as ncaa
from .ncaa import (Program, load_division, build_roster, _talent_from_strength,
                   _pick_gender, ROSTER_SIZE, SCHOLARSHIP_SLOTS, roster_cap)
from .development import generate_prospect, make_pid, overall_to_str
from .season import run_season
from generators import make_name_picker, region_preset

# College tennis is one of the highest-churn NCAA sports: ~1 in 7 men (~14%) and
# ~1 in 9 women (~11%) transfer each year. Most moves are DOWN/OUT — players
# buried behind international recruits leave for playing time at a lower tier,
# burnout sends others to D3/club/quitting. Moving UP (to a stronger program) is
# rare and hard: coaches prioritize incoming freshmen ("wait and see").
BASE_MOVE = {"men": 0.155, "women": 0.12}   # tuned so weighted churn ≈ 14% / 11%
UP_THRESHOLD = 0.8        # live STR this far above program level ⇒ an up-candidate
UP_SUCCESS = 0.35         # of up-candidates who try, the share who actually land a spot
RELIABILITY_GATE = 0.4    # need a reasonably reliable rating to be judged an up-candidate


def _churn_mult(s: float, level: float) -> float:
    """Relative likelihood a SCHOLARSHIP player enters the portal (walk-ons are
    handled separately — they always seek a scholarship). Buried players churn
    most; established starters least; stars a touch above settled."""
    if s < level - 1.0:
        return 1.5                      # not earning their lineup spot → wants playing time
    if s > level + UP_THRESHOLD:
        return 1.0                      # a star — may look up
    return 0.6                          # established starter, mostly stays
_NEXT_CLASS = {"Fr": "So", "So": "Jr", "Jr": "Sr"}


@dataclass
class League:
    division: str
    gender: str
    seed: int
    year: int
    programs: list[Program]
    rosters: dict[str, list]               # school -> list[Prospect]
    player_str: dict[str, tuple]           # pid -> (STR, reliability)
    history: list[dict] = field(default_factory=list)

    def program(self, school: str) -> Program:
        return self._by_school[school]

    def __post_init__(self):
        self._by_school = {p.school: p for p in self.programs}


def _record_history(league: League, sr) -> None:
    """Append each rostered player's season line (where they played, class, STR,
    record). A school change between a player's entries = a transfer."""
    for school, roster in league.rosters.items():
        for p in roster:
            s, rel = sr.player_str.get(p.pid, (p.str_value(), 0.0))
            w, l = sr.player_record.get(p.pid, (0, 0))
            p.history.append({"year": league.year, "school": school, "class": p.class_year,
                              "str": round(s, 1), "rel": round(rel, 2), "w": w, "l": l})


def new_league(division: str = "D1", gender: str = "men", *, seed: int = 2026) -> League:
    sr = run_season(division, gender, seed=seed)
    # Own deep copies so each League's mutations are isolated from the global
    # roster cache (and from other Leagues built off the same seed).
    rosters = {s: [copy.deepcopy(p) for p in r] for s, r in sr.rosters.items()}
    lg = League(division, gender, seed, year=0, programs=sr.programs,
                rosters=rosters, player_str=sr.player_str)
    _record_history(lg, sr)
    return lg


def _normalize(roster: list, cap: int = ROSTER_SIZE) -> None:
    """Sort the ladder (lineup order) and cap size. Walk-on STATUS is persistent
    (set at intake / changed only by retention), so it is NOT reassigned here."""
    roster.sort(key=lambda p: p.current_overall(), reverse=True)
    del roster[cap:]


def _scholarship_count(roster: list) -> int:
    return sum(1 for p in roster if not p.walk_on)


def _program_level(prog: Program) -> float:
    """The STR a program 'expects' to field — used as the transfer-up bar."""
    return overall_to_str(_talent_from_strength(prog.strength, prog.division, prog.gender))


def _pstr(league: League, p) -> float:
    return league.player_str.get(p.pid, (p.str_value(), 0.0))[0]


def _relocate(league: League, p, src: str, dest: str, *, walk_on: bool) -> None:
    league.rosters[src].remove(p)
    p.walk_on = walk_on
    league.rosters[dest].append(p)


def _portal(league: League, rng: random.Random, base: float) -> dict:
    """STR-and-success-driven transfer portal, both directions:
      • walk-ons not retained always seek a SCHOLARSHIP (a program where they'd be
        a top-6 line); if none, they leave the division (to a lower tier).
      • a lineup star at a weaker program moves UP to ride lines 3–6 at a
        powerhouse (hard — gated by UP_SUCCESS; coaches favor freshmen).
      • a buried starter moves DOWN to a weaker program to play lines 1–3
        (playing time); if no fit, leaves the division.
    Destinations need an open roster slot AND an open scholarship slot."""
    rosters, programs = league.rosters, league.programs
    by_school = {pr.school: pr for pr in programs}

    def open_slot(school, p=None):
        # A service academy has no seat for an international mover (US citizens only).
        if p is not None and not ncaa.admits_nationality(school, p):
            return False
        return (len(rosters[school]) < roster_cap(league.division)
                and _scholarship_count(rosters[school]) < SCHOLARSHIP_SLOTS)

    def fit_line(school, s):
        return 1 + sum(1 for q in rosters[school] if _pstr(league, q) > s)

    # Decide movers in deterministic program order.
    movers = []
    for prog in programs:
        level = _program_level(prog)
        for p in list(rosters[prog.school]):
            s = _pstr(league, p)
            if p.walk_on:
                movers.append((p, prog.school, "schol"))           # always seeks a scholarship
            elif rng.random() < base * _churn_mult(s, level):
                movers.append((p, prog.school, "churn"))
    movers.sort(key=lambda m: -_pstr(league, m[0]))                 # best move first

    out = {"movers": len(movers), "up": 0, "down": 0, "schol": 0, "depart": 0, "sample": []}
    for p, src, reason in movers:
        s = _pstr(league, p)
        src_prog = by_school[src]
        cl = 1 + sum(1 for q in rosters[src] if _pstr(league, q) > s)   # current line at src

        if reason == "schol":
            cand = sorted((d for d in programs if d.school != src and open_slot(d.school, p)
                           and fit_line(d.school, s) <= SCHOLARSHIP_SLOTS),
                          key=lambda d: -d.strength)
            if cand:
                _relocate(league, p, src, cand[0].school, walk_on=False)
                out["schol"] += 1
                out["sample"].append(("schol", p.name, src, cand[0].school, round(s, 1)))
            else:
                rosters[src].remove(p); out["depart"] += 1
            continue

        ups = sorted((d for d in programs if open_slot(d.school, p) and d.strength > src_prog.strength
                      and fit_line(d.school, s) <= 6), key=lambda d: -d.strength)
        downs = sorted((d for d in programs if open_slot(d.school, p) and d.strength < src_prog.strength
                        and fit_line(d.school, s) < cl), key=lambda d: fit_line(d.school, s))
        rel = league.player_str.get(p.pid, (0, 0))[1]
        order = (["up", "down"] if cl <= 2 else ["down", "up"] if cl >= 4
                 else (["up", "down"] if rng.random() < 0.5 else ["down", "up"]))
        moved = False
        for d in order:
            if d == "up" and ups and rel >= RELIABILITY_GATE \
                    and (s - _program_level(src_prog)) >= UP_THRESHOLD and rng.random() < UP_SUCCESS:
                _relocate(league, p, src, ups[0].school, walk_on=False)
                out["up"] += 1
                out["sample"].append(("up", p.name, src, ups[0].school, round(s, 1)))
                moved = True; break
            if d == "down" and downs:
                _relocate(league, p, src, downs[0].school, walk_on=False)
                out["down"] += 1
                out["sample"].append(("down", p.name, src, downs[0].school, round(s, 1)))
                moved = True; break
        if not moved:
            rosters[src].remove(p); out["depart"] += 1                 # left the division
    return out


def _refill(league: League, rng: random.Random) -> int:
    intake = 0
    for prog in league.programs:
        roster = league.rosters[prog.school]
        need = roster_cap(league.division) - len(roster)
        if need <= 0:
            continue
        prng = random.Random(f"{prog.key}|intake|{league.year}")
        # A service academy's intake is American only (ncaa.SERVICE_ACADEMIES).
        _rw = ({"us": 1.0} if ncaa.us_only_program(prog.school)
               else region_preset("tennis_global"))
        name_fn = make_name_picker(random.Random(f"{prog.key}|names|{league.year}"),
                                   gender=_pick_gender(prog.gender),
                                   region_weights=_rw)
        tmean = _talent_from_strength(prog.strength, prog.division, prog.gender)
        for k in range(need):
            name, country = name_fn()
            talent = max(24.0, min(80.0, prng.gauss(tmean, 5.0)))
            fr = generate_prospect(prng, name, country, gender=_pick_gender(prog.gender),
                                   talent=talent, pid=make_pid(prog.key, "fr", league.year, k))
            fr.class_year = "Fr"
            fr.walk_on = _scholarship_count(roster) >= SCHOLARSHIP_SLOTS   # scholarships fill first
            roster.append(fr)
            intake += 1
    return intake


def advance_year(league: League) -> dict:
    rng = random.Random(f"{league.seed}|advance|{league.year}")

    # 1. Graduate seniors; bump everyone else up a class.
    grads = 0
    for school, roster in league.rosters.items():
        kept = []
        for p in roster:
            if p.class_year == "Sr":
                grads += 1
            else:
                p.class_year = _NEXT_CLASS.get(p.class_year, "So")
                kept.append(p)
        league.rosters[school] = kept

    # 2. Develop returning players one year.
    for roster in league.rosters.values():
        for p in roster:
            p.develop_year()

    # 3. Retention: a school keeps deserving walk-ons by promoting them into
    #    scholarship slots vacated by graduation (best performers first).
    retained = 0
    for roster in league.rosters.values():
        openings = SCHOLARSHIP_SLOTS - _scholarship_count(roster)
        if openings > 0:
            for p in sorted((q for q in roster if q.walk_on),
                            key=lambda q: -_pstr(league, q))[:openings]:
                p.walk_on = False
                retained += 1

    # 4. Transfer portal (uses last season's live STR); rate is gender-specific.
    port = _portal(league, rng, BASE_MOVE.get(league.gender, 0.13))

    # 5. Intake a freshman class to refill, then normalize ladders.
    intake = _refill(league, rng)
    for roster in league.rosters.values():
        _normalize(roster, roster_cap(league.division))

    # 6. Re-sim the season with the evolved rosters → fresh live STR.
    league.year += 1
    ncaa.reset_caches()
    for prog in league.programs:                  # prime caches so conf tourneys/bracket agree
        ncaa._roster_cache[prog.key] = league.rosters[prog.school]
    sr = run_season(league.division, league.gender,
                    seed=league.seed + league.year, rosters=league.rosters)
    league.player_str = sr.player_str
    _record_history(league, sr)

    summary = {"year": league.year, "graduated": grads, "intake": intake,
               "retained": retained, "movers": port["movers"], "up": port["up"],
               "down": port["down"], "schol": port["schol"], "depart": port["depart"],
               "sample": port["sample"]}
    league.history.append(summary)
    return summary
