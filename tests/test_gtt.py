import random

from engine import random_player
from engine.gtt import GTTTeam, simulate_gtt_dual, LINES_TO_CLINCH

SLOTS = ["MS1", "MS2", "MS3", "WS1", "WS2", "WS3", "XD1", "XD2", "XD3"]


def _gtt_team(name, base, seed):
    rng = random.Random(seed)
    men = [random_player(rng, f"{name}M{i}", base=base) for i in range(3)]
    women = [random_player(rng, f"{name}W{i}", base=base) for i in range(3)]
    return GTTTeam(name=name, men=men, women=women)


def test_gtt_clinch_at_5():
    home = _gtt_team("H", 0.60, 1)
    away = _gtt_team("A", 0.55, 2)
    res = simulate_gtt_dual(home, away, seed=10)
    assert res.home_points + res.away_points <= 9
    assert max(res.home_points, res.away_points) == LINES_TO_CLINCH   # clinch at 5
    assert res.winner in (0, 1)
    # winner is the side that reached the clinch
    assert (res.winner == 0) == (res.home_points > res.away_points)


def test_gtt_nine_lines_three_disciplines():
    res = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=4)
    assert [l.slot for l in res.lines] == SLOTS


def test_gtt_completed_lines_equal_points():
    # Lopsided -> likely early clinch; completed lines == points actually played.
    res = simulate_gtt_dual(_gtt_team("H", 0.80, 1), _gtt_team("A", 0.40, 2), seed=3)
    completed = sum(1 for l in res.lines if l.completed)
    assert completed == res.home_points + res.away_points
    # every unfinished line carries no result
    assert all(l.result is None for l in res.lines if not l.completed)
    assert all(l.result is not None for l in res.lines if l.completed)


def test_gtt_deterministic():
    r1 = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    r2 = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    assert (r1.home_points, r1.away_points) == (r2.home_points, r2.away_points)
    assert [l.slot for l in r1.lines] == [l.slot for l in r2.lines]
    assert [l.home_won for l in r1.lines] == [l.home_won for l in r2.lines]


def test_gtt_fast_fidelity_runs_and_clinches():
    res = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2),
                            seed=7, fidelity="fast")
    assert max(res.home_points, res.away_points) == LINES_TO_CLINCH
    assert res.winner in (0, 1)


def test_lines_are_fast4_sets():
    """Every GTT line is a single Fast4 set: first to 4 games, tiebreak at 3-3,
    so no completed line exceeds 4 games and the only one-game margin is 4-3."""
    res = simulate_gtt_dual(_gtt_team("H", 0.62, 1), _gtt_team("A", 0.55, 2), seed=4)
    for ln in res.lines:
        if not ln.completed:
            continue
        sets = ln.result.set_scores
        assert len(sets) == 1, "a GTT line is a single set"
        hi, lo = max(sets[0]), min(sets[0])
        assert hi == 4, f"Fast4 set won at 4 games, got {sets[0]}"
        assert lo <= 3 and (hi - lo >= 2 or (hi, lo) == (4, 3))


def test_form_keeps_determinism():
    a = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    b = simulate_gtt_dual(_gtt_team("H", 0.6, 1), _gtt_team("A", 0.55, 2), seed=9)
    assert [l.home_won for l in a.lines] == [l.home_won for l in b.lines]


def test_pros_develop_toward_their_peak():
    """A pro used to be FROZEN at their college exit level from 22 until 29, then
    only decline — no prime years at all. They now develop toward the ceiling they
    graduated with, tapering to zero at PEAK_AGE, mirroring decline past it."""
    import copy
    import random
    from app.development import generate_prospect, RICH_ATTRS
    import app.gtt_seasonmode as gs

    def raw(x):
        return sum(x.current[a] for a in RICH_ATTRS)

    grad = generate_prospect(random.Random(9), "Riser", "US", gender="male", talent=62)
    for _ in range(4):                       # four college years -> a real graduate
        grad.develop_year()
    assert grad.ceiling_overall() > grad.current_overall(), "fixture needs headroom"

    def prime(p):
        c = copy.deepcopy(p)
        for age in range(gs.ENTRY_AGE + 1, gs.PEAK_AGE + 1):
            taper = max(0.0, min(1.0, (gs.PEAK_AGE - age) / (gs.PEAK_AGE - gs.ENTRY_AGE)))
            c.develop(scale=gs.PRO_GROWTH * taper)
        return c

    peaked = prime(grad)
    assert raw(peaked) > raw(grad), "a pro must improve across their twenties"
    assert peaked.current_overall() > grad.current_overall(), "growth must be visible in OVR"
    assert peaked.current_overall() <= grad.ceiling_overall(), "never past the ceiling"

    # growth is spent by the peak: the last step before PEAK_AGE adds nothing
    at_peak = copy.deepcopy(peaked)
    at_peak.develop(scale=gs.PRO_GROWTH * 0.0)
    assert raw(at_peak) == raw(peaked)


def test_club_coaching_shapes_players_by_style():
    """Clubs have a staff with a playing style, and it builds exactly the
    attributes it teaches. Two clubs turn the same free agent into different
    players — that is how a roster acquires an identity."""
    import copy, random
    from app.development import generate_prospect
    from app import coaches
    import app.gtt_seasonmode as gs

    grad = generate_prospect(random.Random(9), "P", "US", gender="male", talent=62)
    for _ in range(4):
        grad.develop_year()

    serve_fid = next(f for f in range(1, 40)
                     if gs.club_style(1, f) == "serve-first")
    base_fid = next(f for f in range(1, 40)
                    if gs.club_style(1, f) == "baseline")

    def career(fid, years=6):
        p = copy.deepcopy(grad)
        for _ in range(years):
            assert gs.apply_club_coaching(p, 1, fid)
        return p

    server, baseliner = career(serve_fid), career(base_fid)
    assert server.current["first_serve_power"] > grad.current["first_serve_power"]
    assert baseliner.current["first_serve_power"] == grad.current["first_serve_power"]
    assert baseliner.current["forehand_power"] > grad.current["forehand_power"]
    assert server.current["forehand_power"] == grad.current["forehand_power"]

    # the shaping reaches the ENGINE, not just the sheet
    rich_before, rich_after = grad.engine_player().rich, server.engine_player().rich
    assert rich_after["first_serve_power"] > rich_before["first_serve_power"]


def test_club_coaching_scales_with_staff_quality_and_coachability():
    import copy, random
    from app.development import generate_prospect
    from app import coaches
    import app.gtt_seasonmode as gs

    grad = generate_prospect(random.Random(9), "P", "US", gender="male", talent=62)
    for _ in range(4):
        grad.develop_year()

    # same style, different staff quality -> different gain
    same_style = [f for f in range(1, 60) if gs.club_style(1, f) == "serve-first"]
    by_q = sorted(same_style, key=lambda f: coaches.coaching_strength(gs.franchise_coach(1, f)))
    weak, strong = by_q[0], by_q[-1]
    assert coaches.coaching_strength(gs.franchise_coach(1, strong)) > \
        coaches.coaching_strength(gs.franchise_coach(1, weak))

    def gain(fid, p):
        q = copy.deepcopy(p)
        gs.apply_club_coaching(q, 1, fid)
        return q.current["first_serve_power"] - p.current["first_serve_power"]

    assert gain(strong, grad) > gain(weak, grad), "a better staff must teach more"

    # a more coachable player takes more from the SAME staff
    dull, keen = copy.deepcopy(grad), copy.deepcopy(grad)
    dull.current["coachability"] = 20.0
    keen.current["coachability"] = 80.0
    assert gain(strong, keen) > gain(strong, dull)


def test_club_coaching_is_additive_not_capped_by_potential():
    """The boost is additive to CURRENT ability, not gated on remaining potential —
    a finished veteran can still be reshaped by the right club."""
    import copy, random
    from app.development import generate_prospect
    import app.gtt_seasonmode as gs

    p = generate_prospect(random.Random(9), "P", "US", gender="male", talent=62)
    for _ in range(12):                       # run growth right out
        p.develop_year()
    fid = next(f for f in range(1, 40) if gs.club_style(1, f) == "serve-first")
    before = p.current["first_serve_power"]
    q = copy.deepcopy(p)
    gs.apply_club_coaching(q, 1, fid)
    assert q.current["first_serve_power"] > before
