from app.league import new_league, advance_year
from app.ncaa import ROSTER_SIZE, roster_cap


def test_league_deterministic_and_invariants():
    a = new_league("D1", "women", seed=3)
    b = new_league("D1", "women", seed=3)
    ra = advance_year(a)
    rb = advance_year(b)

    assert ra == rb                                        # fully deterministic year summary
    assert ra["graduated"] > 0
    assert ra["intake"] == ra["graduated"] + ra["depart"]  # openings = grads + division-leavers
    assert all(len(r) == roster_cap("D1") for r in a.rosters.values())  # rosters stay full (D1 cap)
    assert any(p.class_year == "Fr" for r in a.rosters.values() for p in r)  # freshmen intake
    assert ra["movers"] > ra["up"]                         # most moves are NOT up (down/out dominate)
    # up-transfers go to stronger programs; down-transfers to weaker ones
    strength = {p.school: p.strength for p in a.programs}
    for kind, name, frm, to, s in ra["sample"]:
        if kind == "up":
            assert strength[to] > strength[frm]
        elif kind == "down":
            assert strength[to] < strength[frm]


def test_player_identity_and_development_persist():
    lg = new_league("D1", "women", seed=8)
    # remember underclassmen (they'll return next year) by pid + ability
    before = {p.pid: p.current_overall() for r in lg.rosters.values() for p in r
              if p.class_year in ("Fr", "So", "Jr")}
    advance_year(lg)
    after = {p.pid: p.current_overall() for r in lg.rosters.values() for p in r}
    # at least some pre-existing players are still present (same pid) and did not regress
    survivors = [pid for pid in before if pid in after]
    assert survivors
    assert all(after[pid] >= before[pid] for pid in survivors)   # development never regresses
