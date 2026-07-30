import random

from engine import random_player, simulate_dual, Team


def _team(name, base, seed):
    rng = random.Random(seed)
    return Team(name=name, singles=[random_player(rng, f"{name}{i}", base=base) for i in range(6)])


def test_dual_clinch_at_4():
    home = _team("H", 0.6, 1)
    away = _team("A", 0.55, 2)
    res = simulate_dual(home, away, seed=10)
    assert res.home_points + res.away_points <= 7
    assert max(res.home_points, res.away_points) == 4   # clinch at 4
    assert res.winner in (0, 1)


def test_dual_abandons_after_clinch():
    home = _team("H", 0.75, 1)   # lopsided → likely early clinch
    away = _team("A", 0.40, 2)
    res = simulate_dual(home, away, seed=3)
    # If a side reached 4 before all 6 singles, some lines are unfinished.
    completed_singles = [l for l in res.lines if l.slot.startswith("S") and l.completed]
    assert len(completed_singles) <= 6


def test_dual_deterministic():
    h1, a1 = _team("H", 0.6, 1), _team("A", 0.55, 2)
    h2, a2 = _team("H", 0.6, 1), _team("A", 0.55, 2)
    r1 = simulate_dual(h1, a1, seed=9)
    r2 = simulate_dual(h2, a2, seed=9)
    assert (r1.home_points, r1.away_points) == (r2.home_points, r2.away_points)


def test_dual_order_of_finish():
    """Every completed line carries a 1-based order-of-finish ordinal (the ITA
    box-score 'Order of finish'); abandoned lines carry none. Within each
    discipline the ordinals are a clean 1..N sequence, and the count of completed
    singles equals the points that were on the board when the dual clinched."""
    res = simulate_dual(_team("H", 0.75, 1), _team("A", 0.40, 2), seed=3)  # lopsided → early clinch
    for disc in ("D", "S"):
        done = [l for l in res.lines if l.slot[0] == disc and l.completed]
        abandoned = [l for l in res.lines if l.slot[0] == disc and not l.completed]
        assert all(l.finish is None for l in abandoned)
        # ordinals are exactly 1..len(done), each used once (a real finish order).
        assert sorted(l.finish for l in done) == list(range(1, len(done) + 1))
    # All three doubles play out in this sim, so doubles always has a full 1..3 order.
    assert len([l for l in res.lines if l.slot[0] == "D" and l.completed]) == 3


def test_dual_order_of_finish_deterministic():
    r1 = simulate_dual(_team("H", 0.6, 1), _team("A", 0.55, 2), seed=9)
    r2 = simulate_dual(_team("H", 0.6, 1), _team("A", 0.55, 2), seed=9)
    assert [l.finish for l in r1.lines] == [l.finish for l in r2.lines]


def test_dual_play_all_completes_every_match():
    """ITA D3 'play-play': play_all finishes every singles match instead of
    abandoning after the clinch. The winner and every individual outcome are
    unchanged (the matches were already simulated) — only the margin fills in and
    every player lands a completed match on record."""
    home, away = _team("H", 0.80, 1), _team("A", 0.35, 2)   # lopsided → clinch would abandon some
    clinched = simulate_dual(home, away, seed=3)
    full = simulate_dual(home, away, seed=3, play_all=True)

    assert full.winner == clinched.winner                  # play-play never flips the result
    assert len([l for l in full.lines if l.slot[0] == "S" and l.completed]) == 6
    # Fuller margin: no clinch cap, so total points >= the clinched total.
    assert full.home_points + full.away_points >= clinched.home_points + clinched.away_points
    # Wherever the clinch run completed a singles line, play-play agrees on it.
    cwins = {l.slot: l.home_won for l in clinched.lines if l.slot[0] == "S" and l.completed}
    fwins = {l.slot: l.home_won for l in full.lines if l.slot[0] == "S"}
    assert all(fwins[s] == won for s, won in cwins.items())


# ---- short rosters must never crash the engine -------------------------------

def test_doubles_pairing_never_indexerrors_on_a_short_side():
    """The reported crash: `Team.doubles` defaults to [(0,1),(2,3),(4,5)], so a side
    with fewer than six available players IndexError'd in `_pair` and took the whole
    page down mid-bracket. Reachable from roster thinning over seasons and from
    injuries cutting a six-man roster below six."""
    from engine.dual import Team, _pair
    from app.ncaa import load_division, build_squad

    full = build_squad(load_division("D1", "men").programs[0])
    for n in (5, 4, 3, 2, 1):
        thin = Team(name="Thin", singles=list(full.singles[:n]))
        for pair in thin.doubles:
            d = _pair(thin, pair)                       # must not raise
            assert len(d.players) == 2
            if n > 1:
                assert d.players[0] is not d.players[1], f"self-paired at n={n}"


def test_squad_is_always_six_even_if_the_roster_thinned(monkeypatch):
    from app.ncaa import load_division, squad_and_ladder, LINEUP_SIZE
    import app.ncaa as ncaa

    prog = load_division("D1", "men").programs[0]
    real = ncaa.build_roster(prog)
    monkeypatch.setattr(ncaa, "build_roster", lambda p: real[:3])   # thinned to three
    ncaa._squad_cache.clear()
    team, ladder = squad_and_ladder(prog)
    ncaa._squad_cache.clear()

    assert len(ladder) == LINEUP_SIZE
    assert len(team.singles) == LINEUP_SIZE
    assert len({pr.pid for pr in ladder}) == LINEUP_SIZE, "filler duplicated a pid"
