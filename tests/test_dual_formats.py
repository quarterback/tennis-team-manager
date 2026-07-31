"""Per-division dual formats (owner rule 2027-07 — docs/AAR-division-dual-formats.md).

D1 plays 10 singles + 5 doubles consolidated to one doubles point (11 points,
clinch 6); D2/D3 play 8 + 3 with every doubles line its own point (11, clinch 6);
D4 plays 10 + 3 per-line (13, clinch 7). The engine takes the shape as data and
the classic 6+3 stays the default for bare calls (cups, engine tests)."""
import random

import pytest

from engine import random_player, simulate_dual, Team, DualFormat, CLASSIC


def _team(name, base, seed, n=12):
    rng = random.Random(seed)
    return Team(name=name, singles=[random_player(rng, f"{name}{i}", base=base) for i in range(n)])


def test_classic_default_is_unchanged():
    f = CLASSIC
    assert (f.n_singles, f.n_doubles, f.doubles_team_point) == (6, 3, True)
    assert f.total_points == 7 and f.clinch == 4
    res = simulate_dual(_team("H", .6, 1, 6), _team("A", .55, 2, 6), seed=9)
    assert max(res.home_points, res.away_points) == 4
    assert [l.slot for l in res.lines] == [f"D{i}" for i in (1, 2, 3)] + [f"S{i}" for i in range(1, 7)]


@pytest.mark.parametrize("fmt,slots,doubles_pt", [
    (DualFormat(10, 5, True), 15, True),     # D1
    (DualFormat(8, 3, False), 11, False),    # D2/D3
    (DualFormat(10, 3, False), 13, False),   # D4
])
def test_expanded_shapes_resolve_and_clinch(fmt, slots, doubles_pt):
    res = simulate_dual(_team("H", .6, 1), _team("A", .55, 2), seed=9, dual_fmt=fmt)
    assert len(res.lines) == slots
    assert res.winner in (0, 1)
    assert max(res.home_points, res.away_points) == fmt.clinch
    assert res.home_points + res.away_points <= fmt.total_points
    # Consolidated formats attribute THE doubles point; per-line formats have none.
    assert (res.doubles_point is not None) == doubles_pt


def test_per_line_doubles_each_count():
    """Under per-line scoring the doubles wins land directly in the team score:
    points after doubles = 3 split between the sides (no consolidation)."""
    fmt = DualFormat(8, 3, False)
    res = simulate_dual(_team("H", .6, 1), _team("A", .55, 2), seed=11, dual_fmt=fmt)
    d_home = sum(1 for l in res.lines if l.slot.startswith("D") and l.home_won)
    d_away = 3 - d_home
    s_home = sum(1 for l in res.lines if l.slot.startswith("S") and l.completed and l.home_won)
    s_away = sum(1 for l in res.lines if l.slot.startswith("S") and l.completed and not l.home_won)
    assert (res.home_points, res.away_points) == (d_home + s_home, d_away + s_away)


def test_division_formats_are_the_owner_spec():
    from app.ncaa import DUAL_FORMATS, dual_format, lineup_size
    assert dual_format("D1").n_singles == 10 and dual_format("D1").n_doubles == 5
    assert dual_format("D1").doubles_team_point and dual_format("D1").total_points == 11
    for d in ("D2", "D3"):
        f = dual_format(d)
        assert (f.n_singles, f.n_doubles, f.doubles_team_point) == (8, 3, False)
        assert f.total_points == 11 and f.clinch == 6
    f4 = dual_format("D4")
    assert (f4.n_singles, f4.n_doubles, f4.doubles_team_point) == (10, 3, False)
    assert f4.total_points == 13 and f4.clinch == 7
    assert {lineup_size(d) for d in DUAL_FORMATS} == {8, 10}
    assert dual_format("GTT") is CLASSIC          # unknown divisions fall back


def test_season_dual_plays_the_division_shape():
    """dual_between simulates the division's format end to end: a D1 record carries
    D1..D5 + S1..S10 with identities on every completed line; a D2 record carries
    D1..D3 + S1..S8 and its doubles wins count per line."""
    from app.ncaa import load_division
    from app.season import dual_between

    div = load_division("D1", "men")
    rec = dual_between(div.programs[0], div.programs[1], seed=5, conf=False)
    slots = [ln["slot"] for ln in rec["lines"]]
    assert slots == [f"D{i}" for i in range(1, 6)] + [f"S{i}" for i in range(1, 11)]
    assert max(rec["home_points"], rec["away_points"]) == 6
    for ln in rec["lines"]:
        if ln["completed"] and ln["slot"].startswith("S"):
            assert ln.get("home_pid") and ln.get("away_pid"), f"{ln['slot']} lost identity"

    div2 = load_division("D2", "men")
    rec2 = dual_between(div2.programs[0], div2.programs[1], seed=5, conf=False)
    slots2 = [ln["slot"] for ln in rec2["lines"]]
    assert slots2 == [f"D{i}" for i in range(1, 4)] + [f"S{i}" for i in range(1, 9)]
    assert max(rec2["home_points"], rec2["away_points"]) == 6
