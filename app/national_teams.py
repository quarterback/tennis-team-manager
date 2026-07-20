"""
National-team cups — the Davis Cup (men) and Billie Jean King Cup (women).

The existing college player universe regrouped BY COUNTRY into national squads
that play knockout TIES (4 singles + 1 doubles, first to 3 rubbers). Two
single-sex events run separately each off-season — this is the V1 of the
"Tennis World Cup" plan (docs/PLAN-tennis-world-cup.md): a **derived,
seed-deterministic** computation over the live rosters, snapshotted at the year
rollover exactly like the individual championships. ~90% glue over existing
engine parts:

  * squads     — every division's rosters pooled, grouped by `Prospect.country`,
                 top `SQUAD_SIZE` by current ability per nation
  * field      — AUTO-SIZED: every nation clearing the `DEPTH_FLOOR` enters,
                 trimmed to the largest power of two (≤ `FIELD_CAP`) by squad
                 strength, then seeded into `engine.run_tournament`
  * a tie      — `play_tie`: singles 1-4 in rank order then the doubles
                 (each side's top-2 pair), stopping at 3 rubbers won; every
                 rubber is a real `simulate_match` / `simulate_doubles`
  * identity   — every rubber carries the player's REAL pid, so cup titles are
                 stamped through `app.honors` onto the same career page as
                 college and GTT honors, and the snapshot keeps a per-player
                 index (caps + rubber W-L) for the International panel.

Territories (`secondary_country`) do NOT field separate teams in V1 — players
group under their primary `country` only.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine import simulate_match, simulate_doubles, DoublesTeam, run_tournament
from engine.format import MatchFormat
from generators.flavor import country_name, flag_emoji

SQUAD_SIZE = 4              # players per national squad (a tie needs 4)
DEPTH_FLOOR = 4             # nation must have this many players to field a team
FIELD_CAP = 32              # never more than a 32-nation finals
TIE_CLINCH = 3              # rubbers to win the tie (of 5)

EVENT_BY_GENDER = {"men": "Davis Cup", "women": "Billie Jean King Cup"}

# Rubbers score like the NCAA individual championships: best-of-3, no-ad,
# set tiebreaks, 10-point match tiebreak for the deciding set.
TIE_FMT = MatchFormat(best_of=3, no_ad=True, set_tiebreak=True,
                      final_set_tiebreak=True, final_set_tiebreak_target=10)


@dataclass
class NationEntry:
    """One nation's squad in the draw. Mirrors individuals.SinglesEntry so the
    shared tournament framework can seed and play it."""
    country: str                       # ISO2
    players: list                      # Prospects, ability order (squad)
    engines: list = field(default_factory=list)   # engine.Player, aligned
    schools: list = field(default_factory=list)   # school per player (flavor)
    divisions: list = field(default_factory=list)
    rating: float = 0.0                # squad strength = mean top-4 ability

    @property
    def label(self) -> str:
        return country_name(self.country)

    @property
    def key(self):
        return self.country


@dataclass
class Rubber:
    slot: str                          # "S1".."S4", "D1"
    home_pids: list
    away_pids: list
    home_names: list
    away_names: list
    scoreline: str                     # winner-perspective
    home_won: bool


@dataclass
class TieResult:
    home: NationEntry
    away: NationEntry
    home_won: bool
    home_rubbers: int
    away_rubbers: int
    rubbers: list                      # [Rubber] in play order (dead rubbers skipped)

    @property
    def scoreline(self) -> str:
        hi, lo = ((self.home_rubbers, self.away_rubbers) if self.home_won
                  else (self.away_rubbers, self.home_rubbers))
        return f"{hi}-{lo}"


# --------------------------------------------------------------------- squads

def _pool(gender: str, *, seed: int | None = None, rosters: dict | None = None):
    """Every rostered player of `gender` across ALL divisions, as
    (prospect, school, division) tuples. `rosters` (a
    ``{(division, gender): {school: [Prospect]}}`` map, e.g. from
    `world.developed_rosters`) takes precedence; otherwise the live world is
    scanned (`world.scan_rosters`). ⚠ `seed` here is the BASE world seed (the
    save's world), NEVER a derived year seed — scan_rosters primes/creates a
    world for whatever seed it's given, so a wrong seed silently builds a
    parallel universe of players not in the save."""
    if rosters is None:
        from app.world import scan_rosters, DEFAULT_SEED
        rosters = scan_rosters(seed if seed is not None else DEFAULT_SEED)
    out = []
    for (division, g), schools in rosters.items():
        if g != gender:
            continue
        for school, roster in schools.items():
            for p in roster:
                out.append((p, school, division))
    return out


def national_squads(gender: str, *, seed: int | None = None,
                    rosters: dict | None = None,
                    squad_size: int = SQUAD_SIZE,
                    floor: int = DEPTH_FLOOR) -> list[NationEntry]:
    """All nations able to field a squad, strongest first. Each squad is the
    nation's top `squad_size` players by current ability, pooled across every
    division (a D3 star can make a thin nation's team). Deterministic: ability
    ties break on pid."""
    by_country: dict[str, list] = {}
    for p, school, division in _pool(gender, seed=seed, rosters=rosters):
        c = (p.country or "").upper()
        if not c:
            continue
        by_country.setdefault(c, []).append((p, school, division))
    entries = []
    for c, players in by_country.items():
        if len(players) < floor:
            continue
        players.sort(key=lambda t: (-t[0].current_overall(), t[0].pid))
        squad = players[:squad_size]
        entries.append(NationEntry(
            country=c,
            players=[t[0] for t in squad],
            engines=[t[0].engine_player() for t in squad],
            schools=[t[1] for t in squad],
            divisions=[t[2] for t in squad],
            rating=sum(t[0].current_overall() for t in squad) / len(squad)))
    entries.sort(key=lambda e: (-e.rating, e.country))
    return entries


def auto_field(n_nations: int, cap: int = FIELD_CAP) -> int:
    """Auto-sized field: the largest power of two ≤ min(n_nations, cap)."""
    n = min(n_nations, cap)
    f = 1
    while f * 2 <= n:
        f *= 2
    return f


# ------------------------------------------------------------------------ tie

def play_tie(a: NationEntry, b: NationEntry, *, seed: int) -> TieResult:
    """One knockout tie: singles 1-4 in rank order, then the doubles (each
    side's top-2 pair), first to 3 rubbers. Rubbers after the clinch are dead
    and not played (real cups play them as exhibitions; the sim skips them).
    Deterministic from `seed`."""
    wins = [0, 0]
    rubbers: list[Rubber] = []
    for i in range(4):
        if max(wins) >= TIE_CLINCH:
            break
        pa, pb = a.players[i], b.players[i]
        res = simulate_match(a.engines[i], b.engines[i], seed=seed + 10 + i,
                             fmt=TIE_FMT, fidelity="fast")
        home_won = res.winner == 0
        wins[0 if home_won else 1] += 1
        rubbers.append(Rubber(slot=f"S{i+1}", home_pids=[pa.pid], away_pids=[pb.pid],
                              home_names=[pa.name], away_names=[pb.name],
                              scoreline=res.scoreline, home_won=home_won))
    if max(wins) < TIE_CLINCH:
        ta = DoublesTeam(players=(a.engines[0], a.engines[1]))
        tb = DoublesTeam(players=(b.engines[0], b.engines[1]))
        res = simulate_doubles(ta, tb, seed=seed + 50, fmt=TIE_FMT, fidelity="fast")
        home_won = res.winner == 0
        wins[0 if home_won else 1] += 1
        rubbers.append(Rubber(
            slot="D1",
            home_pids=[a.players[0].pid, a.players[1].pid],
            away_pids=[b.players[0].pid, b.players[1].pid],
            home_names=[a.players[0].name, a.players[1].name],
            away_names=[b.players[0].name, b.players[1].name],
            scoreline=res.scoreline, home_won=home_won))
    return TieResult(home=a, away=b, home_won=wins[0] > wins[1],
                     home_rubbers=wins[0], away_rubbers=wins[1], rubbers=rubbers)


# ------------------------------------------------------------------------ cup

def run_world_cup(gender: str, *, seed: int, rosters: dict | None = None,
                  cap: int = FIELD_CAP) -> dict:
    """Select, seed and play a full cup; returns the JSON-safe snapshot dict.
    Deterministic: the same (gender, seed, rosters) reproduces the whole draw."""
    squads = national_squads(gender, seed=seed, rosters=rosters)
    size = auto_field(len(squads), cap)
    entries = squads[:size]
    if len(entries) < 2:
        return {"event": EVENT_BY_GENDER.get(gender, "World Cup"), "gender": gender,
                "field": len(entries), "nations": [], "rounds": [],
                "champion": None, "runner_up": None, "players": {}}
    rng = random.Random(seed ^ 0xDA715)
    played: dict = {}

    def play(ea: NationEntry, eb: NationEntry, *, seed: int) -> NationEntry:
        tie = play_tie(ea, eb, seed=seed)
        played[frozenset((ea.key, eb.key))] = tie
        return ea if tie.home_won else eb

    result = run_tournament(entries, seed=rng.randint(1, 10 ** 9), play=play,
                            key=lambda e: e.rating)

    # ---- serialize (self-contained snapshot; survives the year rollover) ----
    def nd(e: NationEntry | None):
        if e is None:
            return None
        rank = result.entrants.index(e)
        return {"country": e.country, "name": e.label, "flag": flag_emoji(e.country),
                "seed": rank + 1 if rank < result.n_seeds else None,
                "rating": round(e.rating, 1),
                "squad": [{"pid": p.pid, "name": p.name, "school": e.schools[i],
                           "division": e.divisions[i], "ovr": p.current_overall()}
                          for i, p in enumerate(e.players)]}

    players: dict[str, dict] = {}          # pid -> caps / rubber records

    def bump(pid, name, country, slot, won):
        rec = players.setdefault(pid, {"name": name, "country": country,
                                       "ties": 0, "singles_w": 0, "singles_l": 0,
                                       "doubles_w": 0, "doubles_l": 0})
        kind = "singles" if slot.startswith("S") else "doubles"
        rec[f"{kind}_{'w' if won else 'l'}"] += 1

    rounds = []
    for rnd in result.rounds:
        out_r = []
        for m in rnd:
            hi, lo = result.entrants[m.hi], result.entrants[m.lo]
            tie = played[frozenset((hi.key, lo.key))]
            # tie.home is the entry passed first (the better seed)
            win_hi = (tie.home_won == (tie.home is hi))
            tie_pids: dict[str, set] = {}
            rub_out = []
            for rb in tie.rubbers:
                for pid, nm in zip(rb.home_pids, rb.home_names):
                    bump(pid, nm, tie.home.country, rb.slot, rb.home_won)
                    tie_pids.setdefault(pid, set())
                for pid, nm in zip(rb.away_pids, rb.away_names):
                    bump(pid, nm, tie.away.country, rb.slot, not rb.home_won)
                    tie_pids.setdefault(pid, set())
                rub_out.append({"slot": rb.slot, "home": rb.home_names,
                                "away": rb.away_names, "scoreline": rb.scoreline,
                                "home_won": rb.home_won,
                                "home_pids": rb.home_pids, "away_pids": rb.away_pids})
            for pid in tie_pids:
                players[pid]["ties"] += 1
            out_r.append({"rnd": m.rnd, "hi": nd(hi), "lo": nd(lo),
                          "winner_is_hi": win_hi, "upset": m.upset,
                          "score": tie.scoreline,
                          "home_is_hi": tie.home is hi,
                          "rubbers": rub_out})
        rounds.append(out_r)

    return {"event": EVENT_BY_GENDER.get(gender, "World Cup"), "gender": gender,
            "field": len(entries), "n_seeds": result.n_seeds,
            "nations": [nd(e) for e in result.entrants],
            "rounds": rounds,
            "champion": nd(result.champion), "runner_up": nd(result.runner_up),
            "players": players}


# -------------------------------------------------------------------- honors

def honor_records(cup: dict, *, year: int, season_no: int) -> list[dict]:
    """Stampable honor rows (app.honors.stamp) for a completed cup: every
    champion-squad member gets the title; every runner-up squad member the
    final. Keyed to the players' REAL pids so the honor lands on the same
    career page as their college/GTT honors."""
    recs = []
    ev = cup["event"]
    for side, award, label, sort in (("champion", "intl_title", f"{ev} Champion", 95),
                                     ("runner_up", "intl_final", f"{ev} Finalist", 70)):
        nation = cup.get(side)
        if not nation:
            continue
        for pl in nation["squad"]:
            recs.append({"subject_type": "player", "subject_id": pl["pid"],
                         "name": pl["name"], "year": year, "season_no": season_no,
                         "division": "INTL", "gender": cup["gender"],
                         "school": nation["name"], "award": award,
                         "label": label, "sort": sort})
    return recs
