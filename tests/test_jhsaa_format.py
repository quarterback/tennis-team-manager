"""The JHSAA's dual SHAPE and its match SCORING are two independent axes.

Shape was parameterised from the start; scoring was not, so high-school doubles
silently played the college 8-game pro set for a whole season and nothing errored —
a dual still had a winner and the right number of lines. These pin the scoring.
"""
from engine.dual import simulate_dual
from engine.format import PRESETS

from app import jhsaa


def _dual(phase):
    d = jhsaa.districts("girls", "7A")
    pool = d[sorted(d)[0]]
    a = jhsaa.TeamSeason(school=pool[0], roster=jhsaa.build_roster(pool[0], 2030))
    b = jhsaa.TeamSeason(school=pool[1], roster=jhsaa.build_roster(pool[1], 2030))
    jhsaa.play_dual(a, b, seed=99, phase=phase)
    return a.schedule[-1]["lines"]


def _sets(score):
    return [tuple(int(x) for x in s.split("-")) for s in score.split(", ")]


def test_high_school_doubles_is_best_of_three_not_a_pro_set():
    """A pro set is ONE set to 8+; every high-school line goes to 6 games, best-of-3."""
    for phase in ("regular", "state"):
        for ln in _dual(phase):
            if not ln["slot"].startswith("D"):
                continue
            sets = _sets(ln["score"])
            assert 2 <= len(sets) <= 3, (phase, ln)
            assert all(max(s) <= 7 for s in sets), (phase, ln)   # 7-6 is the ceiling


def test_high_school_singles_and_doubles_share_one_format():
    assert jhsaa.MATCH_FORMAT is PRESETS["high_school"]
    assert jhsaa.MATCH_FORMAT.no_ad                    # all high school is no-ad
    assert jhsaa.MATCH_FORMAT.best_of == 3
    assert not jhsaa.MATCH_FORMAT.pro_set
    assert not jhsaa.MATCH_FORMAT.final_set_tiebreak   # a real third set


def test_college_doubles_defaults_are_unchanged():
    """`simulate_dual` gained the format keywords; omitting them must keep college
    on the 8-game pro set and the NCAA singles format."""
    import inspect
    sig = inspect.signature(simulate_dual)
    assert sig.parameters["singles_fmt"].default is None
    assert sig.parameters["doubles_fmt"].default is None
    assert PRESETS["pro_set_8"].pro_set and PRESETS["pro_set_8"].pro_set_games == 8


def test_6a_keeps_its_league_format_through_the_postseason_but_not_the_toc():
    """6A's format-continuity pilot (owner rule 2026-09): the road, State and a
    6A-hosted showcase play the league's 3S/4D; the TOC stays 1S/4D; the league
    season and early window are untouched; no other class moved."""
    f = jhsaa.dual_format
    for phase in ("sectional", "zonal", "semi_state", "state_special", "state"):
        assert (f(phase, "6A").n_singles, f(phase, "6A").n_doubles) == (3, 4), phase
        assert jhsaa.lineup_need(phase, "6A") == 11
    assert (f("toc", "6A").n_singles, f("toc", "6A").n_doubles) == (1, 4)
    assert (f("showcase_pod", "6A").n_singles, f("showcase_pod", "6A").n_doubles) == (3, 4)
    assert (f("regular", "6A").n_singles, f("regular", "6A").n_doubles) == (3, 4)
    assert (f("early", "6A").n_singles, f("early", "6A").n_doubles) == (5, 2)
    for other in ("5A", "7A", "4A"):
        assert f("state", other).n_singles != 3 or f("state", other).n_doubles != 4
    # the postseason arrangement is the anti-stacking wide arranger, not the
    # league's doubles-forward allocation: the three singles seats come from the
    # top five of the frozen order
    from app import jhsaa as jh
    sc = next(s for s in jh.load_schools("boys") if s.group == "6A")
    ts = jh.TeamSeason(school=sc, roster=jh.build_roster(sc, 2029))
    lineup = jh._lineup(ts, "state", __import__("random").Random(1))
    assert len(lineup) == 11
    order = [p.pid for p in jh._order(ts)]
    assert all(order.index(p.pid) < 5 for p in lineup[:3])
