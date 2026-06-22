from app.ncaa import (Program, build_roster, squad_and_ladder, reset_caches,
                      ROSTER_SIZE, SCHOLARSHIP_SLOTS, roster_cap)
from app import scholarships as sch
from app.season import run_season


def _prog(school, strength):
    return Program(school=school, conf="ACC", conf_abbr="ACC", division="D1",
                   gender="men", abbr="XX", color="#000", strength=strength)


def test_build_roster_deterministic_and_shaped():
    reset_caches()
    r1 = build_roster(_prog("Test U", 0.7))
    reset_caches()
    r2 = build_roster(_prog("Test U", 0.7))
    cap = roster_cap("D1")                                           # _prog is D1 → 12
    assert [p.pid for p in r1] == [p.pid for p in r2]                # process-stable ids
    assert [p.current_overall() for p in r1] == [p.current_overall() for p in r2]
    assert len(r1) == cap
    assert len({p.pid for p in r1}) == cap                          # unique ids
    overs = [p.current_overall() for p in r1]
    assert overs == sorted(overs, reverse=True)                     # ladder sorted
    assert all(p.class_year in ("Fr", "So", "Jr", "Sr") for p in r1)
    # Walk-ons = roster cap minus the funded headcount (D1: 12 − 8 = 4 walk-on depth).
    assert sum(p.walk_on for p in r1) == cap - sch.slots(_prog("Test U", 0.7))


def test_roster_talent_tracks_program_strength():
    reset_caches()
    strong = sum(p.current_overall() for p in build_roster(_prog("Strong U", 0.9))) / ROSTER_SIZE
    weak = sum(p.current_overall() for p in build_roster(_prog("Weak U", 0.2))) / ROSTER_SIZE
    assert strong > weak


def test_squad_matches_ladder():
    reset_caches()
    team, ladder = squad_and_ladder(_prog("Ladder U", 0.6))
    assert len(team.singles) == len(ladder) == 6
    for i, pr in enumerate(ladder):
        assert abs(team.singles[i].overall - pr.engine_player().overall) < 1e-9


def test_season_live_str_singles_only_and_in_band():
    sr = run_season("D1", "women", seed=5)
    assert sr.player_str and sr.rosters
    strs = [v[0] for v in sr.player_str.values()]
    assert min(strs) >= 31.0 and max(strs) <= 57.0
    # only singles-ladder players get a results STR (doubles + bench excluded)
    ladder_pids = {pr.pid for r in sr.rosters.values()
                   for pr in sorted(r, key=lambda p: p.current_overall(), reverse=True)[:6]}
    assert set(sr.player_str).issubset(ladder_pids)
