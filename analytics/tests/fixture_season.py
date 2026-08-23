"""Synthetic JHSAA seasons for sidecar tests — pushed through the GAME's own
export builder (app.research_export.build_jhsaa season=...) so the zip the
sidecar ingests has the real schema, not a hand-rolled imitation of it.

Shape: 2 classifications x 2 districts x 4 teams. District play is a
home-and-away double round robin (6 league duals a team), plus one
cross-district invitational each, plus a two-team State final in the top
class — enough to exercise class ranking, district standings, schedule
sections, card-shape derivation (3S/4D regular vs 1S/4D state) and the
power-vs-record ranking split (one team is deliberately better by TOSS than
by record).

‼️ Three properties exist for the ability/market layers and must survive any
edit to this file, because without them those features have nothing to see and
their tests pass vacuously:

  OVR VARIES BY TEAM.   Every school used to generate the same six players
                        (`40 + i`), so every flight was contested at a gap of
                        exactly zero. A win curve fitted on that is undefined
                        and every expected-share number is .500.
  OVR MOVES YEAR ON YEAR, with headroom that differs per player, so the
                        growth curve has more than one bucket to fit.
  A PLAYER MOVES.       `TRANSFERS` relocates one player between the two
                        seasons keeping their player_id, which is the only
                        thing the movement join reads.
"""
from __future__ import annotations

import itertools
from types import SimpleNamespace

# Player moved between the two fixture seasons: {player_id: destination school}.
# The pid is stable across the move — that is the whole mechanism, and a test
# asserts the sidecar reports it from both ends.
TRANSFERS = {"Halbrook 9A Team4|p1": "Halbrook 9A Team1"}

ROSTER = 12          # players a program carries by default
DEPTH_DECAY = 2.5    # OVR lost per rung down an ordinary ladder

# ‼️ Each finder needs a program shaped so it can find something, or the test
# for it passes on an empty list. A fixture where every roster is the same
# depth and every team's best player is as good as its rank says produces
# ZERO buried players, ZERO reservoir and ZERO stranded stars — which is what
# the first version of this file did, and all three finder tests went green.
#
#   DEEP     a big roster with a shallow decay, so its 12th-16th players are
#            still better than a median starter elsewhere in the class: the
#            buried case, and the reservoir cascade under it.
#   STARS    an elite player at the bottom of the class table: the stranded
#            case, which by construction cannot exist while ability and team
#            strength are the same variable.
DEEP = {"Halbrook 9A Team1": (16, 1.0), "Gold 5A Team1": (16, 1.0)}
STARS = {"Ashbury 9A Team4": 76.0, "Sebastian 5A Team4": 64.0}


def _player(school: str, i: int, base: float, bump: float, decay: float, star: float | None):
    """Player i of a school, best first. Current ability comes off the team's
    own base so a stronger team really is stronger on court; headroom widens
    down the ladder so the fitted growth curve sees several buckets."""
    name = f"{school.split()[0]} Player{i}"
    current = star if (star is not None and i == 1) else base - decay * i + bump
    # Headroom cycles 4/10/16/22 rather than growing without bound down the
    # ladder: the growth curve needs several buckets to fit, and the reservoir
    # finder needs a bench player whose CEILING is still below their class's
    # starting line — an unbounded ceiling makes every bench player a prospect.
    ceiling = current + 4 + (i % 4) * 6
    return SimpleNamespace(pid=f"{school}|p{i}", name=name, grade=9 + (i % 4), year=0,
                           hometown="Northbank", country="US",
                           current_overall=lambda: current, ceiling_overall=lambda: ceiling,
                           academic_rating=80, traits={"play_style": "all_court"})


def _school(name: str, group: str, district: str, county: str, area: str, city: str):
    return SimpleNamespace(name=name, key=f"{name}|girls", city=city, locality="",
                           county=county, area=area, classification=group, group=group,
                           district=district, enrollment=1500, private=False,
                           mascot="Aces", colors=["#123456"])


def _lines(shape: tuple[int, int], home_team, away_team, home_wins: bool):
    """shape = (n_singles, n_doubles); the favored side takes every line.

    Players are DISTINCT across the lineup — the top `ns` play singles and the
    next `2 * nd` fill the doubles flights, so a dual dresses ns + 2·nd people
    and everyone below that is genuinely on the bench. The old version wrapped
    with a modulo, which put the same player on two flights of one dual and
    left no bench at all for the market to look at."""
    out = []
    ns, nd = shape

    def dress(team, k):
        return team.roster[k % len(team.roster)]

    for i in range(1, ns + 1):
        out.append({"slot": f"S{i}",
                    "home": [dress(home_team, i - 1).name],
                    "away": [dress(away_team, i - 1).name],
                    "score": "6-2, 6-3" if home_wins else "2-6, 3-6",
                    "home_won": home_wins})
    for i in range(1, nd + 1):
        base = ns + 2 * (i - 1)
        out.append({"slot": f"D{i}",
                    "home": [dress(home_team, base).name, dress(home_team, base + 1).name],
                    "away": [dress(away_team, base).name, dress(away_team, base + 1).name],
                    "score": "6-4, 6-4" if home_wins else "4-6, 4-6",
                    "home_won": home_wins})
    return out


def _dual(home, away, *, phase: str, district: bool, date: str, shape=(3, 4)):
    """Play one dual: the alphabetically-earlier STRENGTH RANK (roster index
    order encoded by team.rank) wins every line. Appends the home-card entry
    (the only copy the exporter reads) and updates both records."""
    home_wins = home.rank < away.rank
    pf = float(sum(shape)) if home_wins else 0.0
    pa = float(sum(shape)) - pf
    home.schedule.append({"opp": away.school.name, "home": True, "phase": phase,
                          "pf": pf, "pa": pa, "won": home_wins,
                          "district": district, "date": date,
                          "lines": _lines(shape, home, away, home_wins)})
    winner, loser = (home, away) if home_wins else (away, home)
    winner.wins += 1
    loser.losses += 1
    if district:
        winner.dwins += 1
        loser.dlosses += 1


# (district, county, area, city) — geography is real data in the export and
# the scouting search is built on it, so the fixture has to carry more than one
# of each or an area filter has nothing to distinguish.
_PLACES = {
    "Halbrook Basin District": ("Halbrook", "North", "Aurora"),
    "Ashbury Metro League": ("Ashbury", "North", "Telfair"),
    "Gold Valley League": ("Gold", "South", "Orellana"),
    "Sebastian Cape District": ("Sebastian", "South", "Port Veles"),
}


def build_season(year: int = 2028, *, bump: float = 0.0, moves: dict | None = None):
    """One synthetic season. `bump` lifts every player's current ability (the
    second season passes one, so development is measurable); `moves` relocates
    players by pid before anything is played, so the whole season is internally
    consistent with the move having happened."""
    groups = {"9A": ["Halbrook Basin District", "Ashbury Metro League"],
              "5A": ["Gold Valley League", "Sebastian Cape District"]}
    teams = {}
    rank = itertools.count()   # global strength order: earlier-created = stronger
    for group, districts in groups.items():
        for district in districts:
            county, area, city = _PLACES[district]
            for i in range(1, 5):
                name = f"{district.split()[0]} {group} Team{i}"
                school = _school(name, group, district, county, area, city)
                r = next(rank)
                size, decay = DEEP.get(name, (ROSTER, DEPTH_DECAY))
                t = SimpleNamespace(school=school,
                                    roster=[_player(name, j, 72 - 1.5 * r, bump, decay,
                                                    STARS.get(name))
                                            for j in range(1, size + 1)],
                                    wins=0, losses=0, dwins=0, dlosses=0,
                                    district_place=None, points_for=0, points_against=0,
                                    power=0.0, schedule=[], rank=r)
                teams[school.key] = t

    for pid, dest in (moves or {}).items():
        src = next((t for t in teams.values()
                    if any(p.pid == pid for p in t.roster)), None)
        target = teams.get(f"{dest}|girls")
        if src is None or target is None:
            raise ValueError(f"fixture move {pid} -> {dest} does not resolve")
        player = next(p for p in src.roster if p.pid == pid)
        src.roster.remove(player)
        target.roster.append(player)

    by_district: dict[str, list] = {}
    for t in teams.values():
        by_district.setdefault(t.school.district, []).append(t)

    day = itertools.count(1)

    def next_date():
        d = next(day)
        return f"{year}-{3 + d // 28:02d}-{d % 28 + 1:02d}"

    # district double round robin: every pairing home-and-away
    for district_teams in by_district.values():
        for a, b in itertools.combinations(district_teams, 2):
            _dual(a, b, phase="regular", district=True, date=next_date())
            _dual(b, a, phase="regular", district=True, date=next_date())

    # Cross-class invitationals: 9A vs 5A. League play is inside a class, so
    # these are the ONLY duals the classification report can compare classes
    # on — without them its whole first tab is empty by construction.
    halbrook = by_district["Halbrook Basin District"]
    ashbury = by_district["Ashbury Metro League"]
    gold = by_district["Gold Valley League"]
    sebastian = by_district["Sebastian Cape District"]
    for a, b in zip(halbrook, ashbury):
        _dual(a, b, phase="regular", district=False, date=next_date())
    for a, b in zip(halbrook, gold):
        _dual(a, b, phase="regular", district=False, date=next_date())
    for a, b in zip(ashbury, sebastian):
        _dual(b, a, phase="regular", district=False, date=next_date())

    # a 9A State final on the 1S/4D card between the two district winners
    _dual(halbrook[0], ashbury[0], phase="state", district=False,
          date=next_date(), shape=(1, 4))

    # standings: place from district record; power deliberately DISAGREES with
    # record for Team2/Team3 of Halbrook so rankings must follow power, not pct
    for district_teams in by_district.values():
        placed = sorted(district_teams, key=lambda t: (-t.dwins, t.rank))
        for place, t in enumerate(placed, 1):
            t.district_place = place
            t.points_for = 4 * t.wins
            t.points_against = 4 * t.losses
            t.power = round(1.0 - 0.05 * t.rank, 3)
    strong_underdog = halbrook[2]           # worse record...
    strong_underdog.power = halbrook[1].power + 0.02   # ...better TOSS than #2

    awards = {"9A": {"poy": {"name": "Halbrook Player1", "school": halbrook[0].school.name,
                             "wins": 9, "losses": 0, "flight": "#1 Singles"}}}
    groups_out = {g: {"state": {"champion": halbrook[0].school.name if g == "9A" else "",
                                "rounds": []}}
                  for g in ("9A", "8A", "7A", "6A", "5A", "4A", "3A", "2A", "1A")}
    return {"teams": teams, "groups": groups_out, "awards": awards}
