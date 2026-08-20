"""Synthetic JHSAA season for sidecar tests — pushed through the GAME's own
export builder (app.research_export.build_jhsaa season=...) so the zip the
sidecar ingests has the real schema, not a hand-rolled imitation of it.

Shape: 2 classifications x 2 districts x 4 teams. District play is a
home-and-away double round robin (6 league duals a team), plus one
cross-district invitational each, plus a two-team State final in the top
class — enough to exercise class ranking, district standings, schedule
sections, card-shape derivation (3S/4D regular vs 1S/4D state) and the
power-vs-record ranking split (one team is deliberately better by TOSS than
by record)."""
from __future__ import annotations

import itertools
from types import SimpleNamespace


def _player(school: str, i: int):
    name = f"{school.split()[0]} Player{i}"
    return SimpleNamespace(pid=f"{school}|p{i}", name=name, grade=9 + (i % 4), year=0,
                           hometown="Northbank", country="US",
                           current_overall=lambda: 40 + i, ceiling_overall=lambda: 50 + i,
                           academic_rating=80, traits={"play_style": "all_court"})


def _school(name: str, group: str, district: str):
    return SimpleNamespace(name=name, key=f"{name}|girls", city="Aurora", locality="",
                           county="Gold", area="North", classification=group, group=group,
                           district=district, enrollment=1500, private=False,
                           mascot="Aces", colors=["#123456"])


def _lines(shape: tuple[int, int], home_team, away_team, home_wins: bool):
    """shape = (n_singles, n_doubles); the favored side takes every line."""
    out = []
    ns, nd = shape
    for i in range(1, ns + 1):
        out.append({"slot": f"S{i}",
                    "home": [home_team.roster[(i - 1) % len(home_team.roster)].name],
                    "away": [away_team.roster[(i - 1) % len(away_team.roster)].name],
                    "score": "6-2, 6-3" if home_wins else "2-6, 3-6",
                    "home_won": home_wins})
    for i in range(1, nd + 1):
        out.append({"slot": f"D{i}",
                    "home": [p.name for p in home_team.roster[2 * (i - 1) % len(home_team.roster):][:2]] or [home_team.roster[0].name],
                    "away": [p.name for p in away_team.roster[2 * (i - 1) % len(away_team.roster):][:2]] or [away_team.roster[0].name],
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


def build_season():
    groups = {"9A": ["Halbrook Basin District", "Ashbury Metro League"],
              "5A": ["Gold Valley League", "Sebastian Cape District"]}
    teams = {}
    rank = itertools.count()   # global strength order: earlier-created = stronger
    for group, districts in groups.items():
        for district in districts:
            for i in range(1, 5):
                name = f"{district.split()[0]} {group} Team{i}"
                school = _school(name, group, district)
                t = SimpleNamespace(school=school,
                                    roster=[_player(name, j) for j in range(1, 7)],
                                    wins=0, losses=0, dwins=0, dlosses=0,
                                    district_place=None, points_for=0, points_against=0,
                                    power=0.0, schedule=[], rank=next(rank))
                teams[school.key] = t

    by_district: dict[str, list] = {}
    for t in teams.values():
        by_district.setdefault(t.school.district, []).append(t)

    day = itertools.count(1)

    def next_date():
        d = next(day)
        return f"2028-{3 + d // 28:02d}-{d % 28 + 1:02d}"

    # district double round robin: every pairing home-and-away
    for district_teams in by_district.values():
        for a, b in itertools.combinations(district_teams, 2):
            _dual(a, b, phase="regular", district=True, date=next_date())
            _dual(b, a, phase="regular", district=True, date=next_date())

    # one cross-district invitational per top-class pairing (non-district)
    halbrook = by_district["Halbrook Basin District"]
    ashbury = by_district["Ashbury Metro League"]
    for a, b in zip(halbrook, ashbury):
        _dual(a, b, phase="regular", district=False, date=next_date())

    # a 9A State final on the 1S/4D card between the two district winners
    _dual(halbrook[0], ashbury[0], phase="state", district=False,
          date=next_date(), shape=(1, 4))

    # standings: place from district record; power deliberately DISAGREES with
    # record for Team2/Team3 of Halbrook so rankings must follow power, not pct
    for district_teams in by_district.values():
        placed = sorted(district_teams, key=lambda t: (-t.dwins, t.rank))
        for place, t in enumerate(placed, 1):
            t.district_place = place
            total = t.wins + t.losses
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
