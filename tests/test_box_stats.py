"""Box-stat overlay + persistence (engine.boxstats, season lines_json stats).

The contract under test, in order of importance:
  1. Outcomes are untouched — the fast model still decides every match, and
     recording game_flow / overlaying stats changes NO scoreline.
  2. Overlaid stats are internally consistent AND consistent with the
     scoreline they annotate (every break in the score is a converted break
     point in the stats).
  3. Stats persist through the season layer keyed to pids, and aggregate.
"""
import json
import random

import pytest

from engine import boxstats
from engine.doubles import DoublesTeam, simulate_doubles
from engine.format import PRESETS
from engine.match import simulate_match
from engine.state import PlayerStats, random_player

FMT = PRESETS["ncaa_dual"]
PRO = PRESETS["pro_set_8"]


def _pair(seed, base=0.5):
    r1, r2 = random.Random(seed * 2 + 1), random.Random(seed * 2 + 2)
    return random_player(r1, "A", base=base + 0.03), random_player(r2, "B", base=base - 0.03)


def _overlaid(seed):
    pa, pb = _pair(seed)
    res = simulate_match(pa, pb, seed=seed, fmt=FMT, fidelity="fast")
    return boxstats.overlay(res, seed=seed, fmt=FMT)


# --- 1. outcomes untouched ---------------------------------------------------

def test_overlay_leaves_scoreline_alone():
    for seed in range(25):
        pa, pb = _pair(seed)
        plain = simulate_match(pa, pb, seed=seed, fmt=FMT, fidelity="fast")
        overlaid = boxstats.overlay(
            simulate_match(pa, pb, seed=seed, fmt=FMT, fidelity="fast"),
            seed=seed, fmt=FMT)
        assert overlaid.set_scores == plain.set_scores
        assert overlaid.winner == plain.winner
        assert overlaid.games_won == plain.games_won


def test_overlay_is_deterministic():
    a, b = _overlaid(42), _overlaid(42)
    key = lambda s: (s.aces, s.double_faults, s.winners, s.unforced_errors,
                     s.points_won, s.break_points_converted)
    assert [key(s) for s in a.stats] == [key(s) for s in b.stats]


def test_full_fidelity_is_a_noop():
    pa, pb = _pair(3)
    res = simulate_match(pa, pb, seed=3, fmt=FMT, fidelity="full")
    before = res.stats[0].aces, res.stats[0].points_won
    boxstats.overlay(res, seed=3, fmt=FMT)          # game_flow is None → no-op
    assert (res.stats[0].aces, res.stats[0].points_won) == before


# --- 2. stats consistent with themselves and the scoreline -------------------

def test_singles_stat_identities():
    for seed in range(25):
        res = _overlaid(seed)
        s0, s1 = res.stats
        assert s0.has_data and s1.has_data
        assert s0.serve_points_total == s1.return_points_total
        assert s1.serve_points_total == s0.return_points_total
        for s in (s0, s1):
            assert s.points_won == s.serve_points_won + s.return_points_won
            assert s.first_serves_in <= s.first_serve_points
            assert s.double_faults <= s.second_serve_points
            assert s.aces <= s.serve_points_won
            assert s.break_points_saved <= s.break_points_faced
        assert (s0.points_won + s1.points_won
                == s0.serve_points_total + s1.serve_points_total)


def test_breaks_in_stats_match_breaks_in_score():
    """Every service break in the recorded score is exactly one converted break
    point in the overlaid stats (a game is won by the returner only ON a break
    point; tiebreaks carry no break points)."""
    for seed in range(25):
        res = _overlaid(seed)
        breaks = [0, 0]
        for set_flow in res.game_flow:
            for srv, win in set_flow["games"]:
                if win != srv:
                    breaks[win] += 1
        assert res.stats[0].break_points_converted == breaks[0]
        assert res.stats[1].break_points_converted == breaks[1]
        assert res.stats[0].break_points_faced - res.stats[0].break_points_saved == breaks[1]
        assert res.stats[1].break_points_faced - res.stats[1].break_points_saved == breaks[0]


def test_doubles_overlay_identities():
    for seed in range(15):
        t0 = DoublesTeam(players=_pair(seed * 7 + 1))
        t1 = DoublesTeam(players=_pair(seed * 7 + 2))
        plain = simulate_doubles(t0, t1, seed=seed, fmt=PRO, fidelity="fast")
        res = boxstats.overlay(
            simulate_doubles(t0, t1, seed=seed, fmt=PRO, fidelity="fast"),
            seed=seed, fmt=PRO)
        assert res.set_scores == plain.set_scores and res.winner == plain.winner
        sts = res.stats                              # [t0p0, t0p1, t1p0, t1p1]
        assert (sts[0].serve_points_total + sts[1].serve_points_total
                == sts[2].return_points_total + sts[3].return_points_total)
        assert (sts[2].serve_points_total + sts[3].serve_points_total
                == sts[0].return_points_total + sts[1].return_points_total)
        # every point is credited to both partners on the winning side
        assert sts[0].points_won == sts[1].points_won
        assert sts[2].points_won == sts[3].points_won
        for s in sts:
            assert s.first_serves_in <= s.first_serve_points
            assert s.double_faults <= s.second_serve_points
        # side-level break accounting matches the recorded score
        breaks = [0, 0]
        for set_flow in res.game_flow:
            for srv, win in set_flow["games"]:
                if win != srv:
                    breaks[win] += 1
        assert sts[0].break_points_converted + sts[1].break_points_converted == breaks[0]
        assert sts[2].break_points_converted + sts[3].break_points_converted == breaks[1]


def test_match_tiebreak_decider_overlay():
    """The 10-point match-tiebreak decider (junior/pro formats) replays too."""
    mtb_fmt = PRESETS["best_of_3_mtb"]
    hit = 0
    for seed in range(40):
        pa, pb = _pair(seed)
        plain = simulate_match(pa, pb, seed=seed, fmt=mtb_fmt, fidelity="fast")
        if not plain.game_flow[-1].get("mtb"):
            continue
        hit += 1
        res = boxstats.overlay(
            simulate_match(pa, pb, seed=seed, fmt=mtb_fmt, fidelity="fast"),
            seed=seed, fmt=mtb_fmt)
        assert res.set_scores == plain.set_scores and res.winner == plain.winner
        s0, s1 = res.stats
        assert s0.serve_points_total == s1.return_points_total
        assert (s0.points_won + s1.points_won
                == s0.serve_points_total + s1.serve_points_total)
    assert hit >= 3                                  # the decider actually occurred


def test_playerstats_json_round_trip():
    res = _overlaid(9)
    for s in res.stats:
        again = PlayerStats.from_dict(json.loads(json.dumps(s.to_dict())))
        assert again == s


# --- 3. persistence through the season layer ---------------------------------

def test_dual_lines_carry_stats():
    from app.ncaa import load_division
    from app.season import dual_between

    div = load_division("D1", "women")
    a, b = div.programs[0], div.programs[1]
    rec = dual_between(a, b, seed=99, conf=True)
    completed = [l for l in rec["lines"] if l.get("completed")]
    abandoned = [l for l in rec["lines"] if not l.get("completed")]
    assert completed
    for ln in completed:
        st = ln.get("stats")
        assert st, f"completed line {ln['slot']} missing stats"
        if ln["slot"].startswith("S"):
            assert set(st) == {"home", "away"}
            assert st["home"]["svt"] == st["away"]["rtt"]
        else:                                        # doubles: one dict per pid
            assert len(st["home"]) == len(ln["home_pids"]) == 2
            assert len(st["away"]) == len(ln["away_pids"]) == 2
    for ln in abandoned:                             # excluded from the stat corpus
        assert "stats" not in ln
    # deterministic including stats
    assert json.dumps(rec["lines"]) == json.dumps(dual_between(a, b, seed=99, conf=True)["lines"])


@pytest.fixture
def db(tmp_path):
    import app.seasonmode as sm
    sm.DB_PATH = str(tmp_path / "season.db")
    yield sm


def test_season_aggregation_and_log(db):
    sm = db
    sid = sm.create_season("D2", "women", seed=7)
    guard = 0
    while sm.load_season(sid)["phase"].startswith("ita") and guard < 10:
        sm.advance(sid)
        guard += 1
    sm.advance(sid)                                  # one regular-season week

    conn = sm._db()
    rows = conn.execute("SELECT lines_json FROM duals WHERE season_id=? AND status='final'",
                        (sid,)).fetchall()
    conn.close()
    # manual re-aggregation from raw lines_json == the helper's totals
    manual: dict = {}
    for r in rows:
        for ln in json.loads(r["lines_json"] or "[]"):
            st = ln.get("stats")
            if not ln.get("completed") or not st or not str(ln.get("slot", "")).startswith("S"):
                continue
            for side, pid in (("home", ln.get("home_pid")), ("away", ln.get("away_pid"))):
                if pid is None:
                    continue
                cur = manual.setdefault(pid, {"ace": 0, "svt": 0, "n": 0})
                cur["ace"] += st[side]["ace"]
                cur["svt"] += st[side]["svt"]
                cur["n"] += 1
    assert manual, "no singles stats persisted"

    agg = sm.player_season_stats(sid)
    for pid, m in manual.items():
        blk = agg[pid]["singles"]
        assert blk["aces"] == m["ace"]
        assert blk["serve_points_total"] == m["svt"]
        assert blk["matches"] == m["n"]

    # player_log carries the per-match stat line from the player's POV
    pid = max(manual, key=lambda p: manual[p]["n"])
    log = sm.player_log(sid, pid)
    with_stats = [m for m in log if m.get("stats")]
    assert with_stats
    assert sum(m["stats"]["ace"] for m in with_stats) == manual[pid]["ace"]
