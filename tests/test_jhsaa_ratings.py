"""The computer-ratings layer (owner spec 2026-09) — each system on a
hand-checkable fixture, the disconnected-schedule report, the retirement guard,
and the composite's disagreement measure."""
import math
import statistics

from app import jhsaa_ratings as jr


def _row(home, away, hp, ap, scores=None, idx=0):
    lines = [{"score": s} for s in (scores or [])]
    return {"home": home, "away": away, "hp": hp, "ap": ap,
            "order": (idx, home, away), "lines": lines}


# A beats B, B beats C, A beats C — every system must agree on A > B > C.
CHAIN = [_row("A", "B", 5, 2, idx=0), _row("B", "C", 6, 1, idx=1),
         _row("A", "C", 7, 0, idx=2)]


def test_every_system_orders_the_unambiguous_chain():
    systems = {
        "colley": jr.colley(CHAIN), "bt": jr.bradley_terry(CHAIN),
        "win_pct": jr.win_pct(CHAIN), "massey_dual": jr.massey_dual(CHAIN),
        "srs": jr.srs(CHAIN), "elo": jr.elo(CHAIN),
    }
    systems["sor"] = jr.sor(CHAIN, systems["bt"])
    for name, vals in systems.items():
        assert vals["A"] > vals["B"] > vals["C"], (name, vals)


def test_colley_two_team_known_answer():
    """One dual, A beats B: the standard Colley 2x2 solves to 0.625 / 0.375."""
    vals = jr.colley([_row("A", "B", 4, 3)])
    assert abs(vals["A"] - 0.625) < 1e-9
    assert abs(vals["B"] - 0.375) < 1e-9


def test_massey_and_srs_two_team_known_answer():
    """A beats B 6-1: NORMALISED margin 5/7 (owner rule — a 5-0, 7-0 and 9-0
    are all +1.0), so the relative ratings are +-(5/7)/2, centred at zero."""
    m = jr.massey_dual([_row("A", "B", 6, 1)])
    assert abs(m["A"] - 5 / 14) < 1e-6 and abs(m["B"] + 5 / 14) < 1e-6
    s = jr.srs([_row("A", "B", 6, 1)])
    assert abs(s["A"] - 5 / 14) < 1e-6 and abs(s["B"] + 5 / 14) < 1e-6


def test_margins_are_format_normalised():
    """A 5-0 in a five-flight dual and a 9-0 in a nine-flight dual are the SAME
    observation — format length is never a rating input."""
    assert jr._flight_margin(_row("A", "B", 5, 0)) == 1.0
    assert jr._flight_margin(_row("A", "B", 9, 0)) == 1.0
    assert abs(jr._flight_margin(_row("A", "B", 4, 3)) - 1 / 7) < 1e-9


def test_win_pct_is_raw_and_unadjusted():
    rows = [_row("A", "B", 4, 3), _row("A", "C", 3, 4), _row("B", "C", 4, 3)]
    vals = jr.win_pct(rows)
    assert vals == {"A": 0.5, "B": 0.5, "C": 0.5}


def test_set_and_game_share_read_the_lines():
    # A wins the dual 4-3 but B wins the games heavily on every line played.
    rows = [_row("A", "B", 4, 3, scores=["1-6, 2-6", "0-6, 1-6"]),
            _row("A", "C", 4, 3, scores=["6-0, 6-1", "6-2, 6-1"]),
            _row("B", "C", 7, 0, scores=["6-0, 6-0", "6-0, 6-0"])]
    g = jr.massey_game(rows)
    assert g["B"] > g["A"], g          # games say B, whatever the dual said
    s = jr.set_share(rows)
    assert s["B"] > s["A"], s


def test_the_retirement_guard_drops_single_set_lines():
    """A single-set line is a retirement/default and must not reach the
    set/game currencies (spec 1.2)."""
    healthy = _row("A", "B", 4, 3, scores=["6-0, 6-0"])
    retired = _row("A", "B", 4, 3, scores=["6-0"])
    assert jr.dual_shares(healthy) == (2, 0, 12, 0)
    assert jr.dual_shares(retired) is None
    mixed = _row("A", "B", 4, 3, scores=["6-0, 6-0", "6-0"])
    assert jr.dual_shares(mixed) == (2, 0, 12, 0)


def test_sor_is_an_exact_probability_and_rewards_the_harder_record():
    bt = {"A": 4.0, "B": 1.0, "C": 1.0, "D": 0.5}
    # Same 1-0 record: D beat the strong A, C beat the ordinary B.
    rows = [_row("D", "A", 4, 3, idx=0), _row("C", "B", 4, 3, idx=1)]
    out = jr.sor(rows, bt)
    assert 0.0 <= min(out.values()) and max(out.values()) <= 1.0
    assert out["D"] > out["C"]         # beating A is the more improbable record


def test_the_sor_benchmark_is_the_published_9_16_median():
    bt = {f"T{i}": float(20 - i) for i in range(20)}     # ratings 20..1
    # ranks 9-16 hold ratings 12..5 — median 8.5
    assert jr.sor_benchmark(bt) == 8.5
    assert jr.sor_benchmark({"A": 3.0, "B": 1.0}) == 2.0   # short-field fallback


def test_elo_moves_with_late_results():
    early = [_row("A", "B", 7, 0, idx=0)]
    late = early + [_row("B", "A", 7, 0, idx=1)]
    assert jr.elo(early)["A"] > jr.elo(early)["B"]
    # the rematch, later, swings B past the earlier result's residue
    after = jr.elo(late)
    assert after["B"] > jr.elo(early)["B"]


class _School:
    def __init__(self, name):
        self.name, self.district, self.group = name, "Test League", "7A"


class _Team:
    def __init__(self, name, rows):
        self.school = _School(name)
        self.schedule = rows
        w = sum(1 for r in rows if r.get("home") and r["pf"] > r["pa"]) + \
            sum(1 for r in rows if not r.get("home") and r["pf"] > r["pa"])
        self.record = f"{w}-{len(rows) - w}"


def _sched(home, away, hp, ap, scores=None):
    lines = [{"score": s} for s in (scores or [])]
    return ({"opp": away, "home": True, "phase": "regular", "pf": hp, "pa": ap,
             "won": hp > ap, "level": "v", "lines": lines},
            {"opp": home, "home": False, "phase": "regular", "pf": ap, "pa": hp,
             "won": ap > hp, "level": "v", "lines": lines})


def _teams(duals):
    rows: dict[str, list] = {}
    for home, away, hp, ap, scores in duals:
        h, a = _sched(home, away, hp, ap, scores)
        rows.setdefault(home, []).append(h)
        rows.setdefault(away, []).append(a)
    return [_Team(n, r) for n, r in sorted(rows.items())]


def test_disconnected_schedule_is_reported_not_fit():
    """Two disjoint pairs: Massey/SRS are withheld and the report says so
    (spec 1.1 / Part 5)."""
    teams = _teams([("A", "B", 4, 3, None), ("C", "D", 4, 3, None)])
    out = jr.group_ratings(teams)
    assert out["disconnected"] is True
    for t in out["teams"].values():
        assert "massey_dual" not in t["ranks"]
        assert "srs" not in t["ranks"]
        assert "massey_game" not in t["ranks"]
        assert "colley" in t["ranks"]           # the record family still rates


def test_composite_sigma_measures_engineered_disagreement():
    """A team built to split the systems — wins its duals 4-3 while losing the
    games badly — must carry a real sigma, computed exactly as the pstdev of
    its own ranks."""
    blow = ["6-0, 6-0"] * 7
    lose = ["0-6, 0-6"] * 4 + ["6-0, 6-0"] * 3       # wins 3 lines, loses games
    duals = [("A", "B", 4, 3, lose), ("A", "C", 4, 3, lose),
             ("B", "C", 7, 0, blow), ("C", "B", 0, 7, blow),
             ("B", "A", 3, 4, ["0-6, 0-6"] * 3 + ["6-0, 6-0"] * 4)]
    out = jr.group_ratings(_teams(duals))
    a = out["teams"]["A"]
    ranks = list(a["ranks"].values())
    assert abs(a["sigma"] - statistics.pstdev(ranks)) < 1e-9
    assert abs(a["mean"] - sum(ranks) / len(ranks)) < 1e-9
    assert a["ranks"]["win_pct"] == 1                # undefeated on record
    assert a["ranks"]["massey_game"] > 1             # the games disagree
    assert a["sigma"] > 0.5


def test_state_and_toc_never_reach_the_ratings_input():
    teams = _teams([("A", "B", 4, 3, None)])
    teams[0].schedule.append({"opp": "B", "home": True, "phase": "state",
                              "pf": 9, "pa": 0, "won": True, "level": "v",
                              "lines": []})
    rows = jr.dual_rows(teams)
    assert len(rows) == 1 and rows[0]["hp"] == 4


def test_a_pod_showcase_pro_set_is_a_complete_match_not_a_retirement():
    """`showcase_pod` scores every court as ONE 8-game pro set, so its
    single-set lines must reach the set/game currencies (Codex finding,
    2026-09) — while an ordinary phase's single-set line stays excluded."""
    pod = {**_row("A", "B", 3, 0, scores=["8-3", "8-6", "8-2"]),
           "phase": "showcase_pod"}
    assert jr.dual_shares(pod) == (3, 0, 24, 11)
    league = {**_row("A", "B", 4, 3, scores=["8-3"]), "phase": "regular"}
    assert jr.dual_shares(league) is None


def test_elo_walks_phase_major_play_order():
    """A road dual sorts after every regular-season dual whatever the two
    teams' schedule lengths — the phase is the calendar, the index only the
    within-phase clock (Codex finding, 2026-09)."""
    duals = [("A", "B", 4, 3, None), ("C", "D", 4, 3, None),
             ("A", "C", 4, 3, None)]
    teams = _teams(duals)
    a = next(t for t in teams if t.school.name == "A")
    # A's THIRD schedule entry is a road dual; C is on only two duals, so a
    # bare index sort would slot it before C's second regular dual.
    h, aw = _sched("A", "D", 5, 4)
    h["phase"] = "sectional"
    a.schedule.append(h)
    next(t for t in teams if t.school.name == "D").schedule.append(aw)
    rows = jr.dual_rows(teams)
    assert rows[-1]["phase"] == "sectional"
    assert [r["phase"] for r in rows[:-1]] == ["regular"] * (len(rows) - 1)
    assert jr._phase_rank("early") < jr._phase_rank("regular") \
        < jr._phase_rank("sectional") < jr._phase_rank("conference")
