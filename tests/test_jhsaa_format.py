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
