"""HS scoreline realism (engine.fast.HS_PROFILE) — see
docs/AAR-jhsaa-scoreline-realism.md and scripts/jhsaa_scoreline_benchmark.py.

Real HS tennis (five seasons of Oregon results) is blowout-shaped: 6-0 is the
most common set (26.4%) and 7-6 the rarest (3.9%). The college-calibrated fast
model produced the near-inverse (7-6 at 14.9%, 6-0 at 2.5%). These tests pin
the corrected shape loosely — the benchmark script is the precision
instrument — and pin exactly the null-profile guarantee the college game
depends on."""
import random

import pytest
from collections import Counter
from itertools import combinations

from app import jhsaa
from engine.dual import simulate_dual
from engine.fast import HS_PROFILE
from engine.match import simulate_match
from engine.doubles import simulate_doubles


def _teams(n=8):
    schools = jhsaa.load_schools("girls")
    byd = {}
    for s in schools:
        byd.setdefault((s.group, s.district), []).append(s)
    district = next(v for v in byd.values() if len(v) >= n)[:n]
    return [jhsaa.TeamSeason(school=s, roster=jhsaa.build_roster(s, 0, ""))
            for s in district]


def _set_shares(teams, trials=2, seed=20260828):
    rng = random.Random(seed)
    dist, matches, three = Counter(), 0, 0
    for a, b in combinations(teams, 2):
        for _ in range(trials):
            ds = rng.getrandbits(32)
            lrng = random.Random(f"lineup|{ds}")
            res = simulate_dual(
                jhsaa._squad(a, "regular", jhsaa._lineup(a, "regular", lrng)),
                jhsaa._squad(b, "regular", jhsaa._lineup(b, "regular", lrng)),
                seed=ds, play_all=True, fidelity=jhsaa.FIDELITY,
                dual_fmt=jhsaa.dual_format("regular"),
                singles_fmt=jhsaa.MATCH_FORMAT, doubles_fmt=jhsaa.MATCH_FORMAT,
                profile=HS_PROFILE)
            for line in res.lines:
                m = line.result
                matches += 1
                three += len(m.set_scores) == 3
                for x, y in m.set_scores:
                    dist[f"{max(x, y)}-{min(x, y)}"] += 1
    total = sum(v for k, v in dist.items() if k[0] in "67")
    return ({k: 100 * v / total for k, v in dist.items()},
            100 * three / matches)


# ‼️ `test_hs_sets_are_blowout_shaped_not_tiebreak_shaped` USED TO LIVE HERE and
# was RETIRED, not fixed (owner ruling 2026-08). It pinned the Oregon set-score
# fit — 6-0 above 15% of sets, 7-6 under 9%, three-setters under 25% — which the
# banded matchup curve deliberately no longer produces (at a 6-OVR gap, 6-0 goes
# ~27.6% -> ~3% and three-setters ~1% -> ~50%). The owner ruled the band spec is
# what is wanted and the scoreline fit is not a constraint on it, so the test was
# asserting a superseded decision.
#
# It should COME BACK, re-measured, once the HS talent scale is freed
# (docs/PROPOSAL-development-model-redesign.md §24): the steep curve produced
# blowouts because matched-line gaps on the COMPRESSED distribution are small
# (median 3.5 OVR), and wider gaps under a flat curve may land in the same place.
# Re-derive its numbers with scripts/jhsaa_scoreline_benchmark.py AFTER that
# change — restoring the old thresholds before it would re-pin the old curve.
# `_set_shares` is kept for that, and for the benchmark script.


def _flat(ovr, name):
    # A FLAT player (every attribute equal) so the measured gap is exactly the
    # OVR gap — engine.fast's lane weights are chosen to reproduce the overall
    # gap exactly for flat players, which is what makes this a reading of the
    # curve rather than of a play style.
    from app.development import Prospect
    from app.player_attributes import RICH_ATTRS
    grades = {a: float(ovr) for a in RICH_ATTRS}
    return Prospect(name=name, current=grades, potential=dict(grades)).engine_player()


def _favourite_rate(gap, n=3000, base=50):
    """(favourite match-win %, three-set %) at an OVR gap through the shipped
    fast model at the association's format, first serve alternating."""
    from engine.fast import simulate_fast
    fav, dog = _flat(base + gap / 2, "fav"), _flat(base - gap / 2, "dog")
    wins = three = 0
    for i in range(n):
        r = simulate_fast(fav, dog, seed=4_000_000 + i, fmt=jhsaa.MATCH_FORMAT,
                          first_server=i % 2, profile=HS_PROFILE)
        wins += r.winner == 0
        three += len(r.set_scores) == 3
    return 100 * wins / n, 100 * three / n


def test_effective_delta_is_the_cumulative_per_point_array():
    """‼️ THE GAP-RESPONSE CURVE IS A PER-POINT SLOPE ARRAY, CUMULATIVE (owner spec
    2026-09, replacing the 3-wide banded table). The effect at gap g is the SUM of
    the marginal slopes for points 1..g — the owner's checkpoints, verbatim from the
    array (the sheet's 69.38 at 30 is 69.36 by the array: 46.56 at 22 + 8 x 2.85).
    Gap 0 contributes nothing; fractional gaps interpolate linearly (4.5 = four
    points + half the gap-5 slope, never rounded); past the array the RATE holds
    at 2.85 a point while the total keeps growing — and nothing raises."""
    from engine import fast
    S = fast.PER_POINT_SLOPES
    assert len(S) == 35 and S[0] == 1.05 and S[1] == 1.10      # the soft peer band
    assert fast.PLATEAU_SLOPE == 2.85
    f = fast.get_effective_delta
    for gap, want in ((1, 1.05), (3, 3.39), (5, 6.34), (10, 15.74),
                      (15, 27.54), (22, 46.56), (30, 69.36)):
        assert abs(f(gap) - want) < 1e-9, (gap, f(gap), want)
        assert abs(f(gap) - sum(S[:gap])) < 1e-9
    assert f(0) == 0.0 and f(-3) == 0.0
    assert abs(f(4.5) - (sum(S[:4]) + 0.5 * S[4])) < 1e-9
    # past the array: 2.85 a point, total unclamped, no IndexError
    assert abs(f(35) - sum(S)) < 1e-9
    assert abs(f(40) - (sum(S) + 5 * 2.85)) < 1e-9
    assert abs(f(100) - (sum(S) + 65 * 2.85)) < 1e-9
    assert f(36.5) - f(36) == pytest.approx(0.5 * 2.85)
    # `band_gap` is the unit-gap entry point `effective_gap` routes to: the same
    # curve on OVR/60, sign-symmetric, monotone, continuous at every point
    for g in (0.0, 1.0, 4.5, 17.0, 35.0, 50.0):
        assert fast.band_gap(g / fast.GRADE_SPAN) * fast.GRADE_SPAN == pytest.approx(f(g))
    assert fast.band_gap(-0.35) == -fast.band_gap(0.35)
    prev = -1.0
    for step in range(0, 601):                          # 0-60 OVR in 0.1 steps
        v = fast.band_gap(step / 10.0 / fast.GRADE_SPAN)
        assert v > prev or step == 0, step
        prev = v
    for k in range(1, 40):
        below = fast.band_gap((k - 1e-7) / fast.GRADE_SPAN)
        assert abs(fast.band_gap(k / fast.GRADE_SPAN) - below) < 1e-5, k
    # the routing: the HS profile takes the curve, the college hinge does not
    assert HS_PROFILE["gap_bands"] is True
    assert fast.effective_gap(0.25, bands=True) == fast.band_gap(0.25)
    assert fast.effective_gap(0.02, bands=False) == 0.02


def test_simulation_plays_on_the_per_point_curve():
    """The match simulation reads the cumulative delta, not the total gap times
    one band's slope — pinned end to end through the real engine. Measured at
    the time of the change (6000 matches a point, se ~0.6):
        gap 1 51.8% · 2 54.0 · 3 56.2 · 5 60.7 · 10 74.5 · 15 88.0 · 22 97.3 · 30 99.8
        three-set: 49.8% level, 44.0 at 10, 17.3 at 22, 6.0 at 30
    Ranges carry sampling headroom at this n (se ~0.9). The owner's target column
    (5 -> 64.5, 10 -> 80.0) sits ABOVE the measured middle: the array does not set
    the win rate, `skill_slope` (0.9) and the compounding do — moving it is a
    separate decision, not a test failure. THE PEER BAND STAYS SOFT: gaps 1-2 are
    a near coin flip by design."""
    rates = {g: _favourite_rate(g) for g in (0, 1, 2, 5, 10, 15, 22, 30)}
    fav = {g: r[0] for g, r in rates.items()}
    three = {g: r[1] for g, r in rates.items()}
    assert 47 <= fav[0] <= 53
    assert fav[1] <= 55 and fav[2] <= 57.5                # soft peer band
    assert 57 <= fav[5] <= 64
    assert 71 <= fav[10] <= 78
    assert 85 <= fav[15] <= 91
    assert 95 <= fav[22] <= 99.3
    assert fav[30] >= 98.5
    # monotone in the gap
    assert fav[1] < fav[5] < fav[10] < fav[15] < fav[22]
    # the three-set collapse: close at the bottom, straight sets at the top
    assert three[0] >= 44 and three[10] >= 39
    assert three[22] <= 23 and three[30] <= 10


def test_null_profile_is_byte_identical_for_college():
    """Every college/cup/pro call passes no profile and must be untouched:
    profile=None and an empty overlay produce the same result stream — the
    profile machinery consumes no rng and changes no dial unless a key is
    actually overridden."""
    teams = _teams(2)
    ps = [p.engine_player() for p in teams[0].roster[:4]]
    qs = [p.engine_player() for p in teams[1].roster[:4]]
    for seed in (7, 42, 99):
        a = simulate_match(ps[0], qs[0], seed=seed, fidelity="fast")
        b = simulate_match(ps[0], qs[0], seed=seed, fidelity="fast", profile={})
        assert (a.winner, a.set_scores) == (b.winner, b.set_scores)
        da = simulate_doubles((ps[0], ps[1]), (qs[0], qs[1]), seed=seed,
                              fidelity="fast")
        db = simulate_doubles((ps[0], ps[1]), (qs[0], qs[1]), seed=seed,
                              fidelity="fast", profile={})
        assert (da.winner, da.set_scores) == (db.winner, db.set_scores)


def test_profile_reaches_the_shipped_jhsaa_path():
    """play_dual passes HS_PROFILE — a dual simulated through jhsaa's own
    play path must produce a different score stream than the college dials
    (guards against the profile silently falling off a call site)."""
    teams = _teams(2)
    a, b = teams
    seed = 1234
    lrng = random.Random(f"lineup|{seed}")
    la, lb = jhsaa._lineup(a, "regular", lrng), jhsaa._lineup(b, "regular", lrng)
    kw = dict(seed=seed, play_all=True, fidelity=jhsaa.FIDELITY,
              dual_fmt=jhsaa.dual_format("regular"),
              singles_fmt=jhsaa.MATCH_FORMAT, doubles_fmt=jhsaa.MATCH_FORMAT)
    with_p = simulate_dual(jhsaa._squad(a, "regular", la),
                           jhsaa._squad(b, "regular", lb),
                           profile=HS_PROFILE, **kw)
    without = simulate_dual(jhsaa._squad(a, "regular", la),
                            jhsaa._squad(b, "regular", lb), **kw)
    def scores(res):
        return [tuple(line.result.set_scores) for line in res.lines]
    assert scores(with_p) != scores(without)


def test_realism_fold_reads_the_archive_varsity_only():
    """/jhsaa/realism is a FOLD over world_jhsaa_dual: one side of each dual,
    varsity only (COALESCE(level,'v')='v' — pre-JV archives read back NULL),
    standard sets only (a showcase pod's 8-x pro set never enters the
    histogram), three-set rate over best-of-3 matches."""
    import json as _json
    import app.world as world
    w = world.get_or_create(4242)
    conn = world._db()
    try:
        rows = [
            # varsity league dual, home side: one straight-set + one three-set line
            (w["id"], 7, "girls", "A", "B", 1, "regular", 5, 2, 1, 1,
             _json.dumps([{"score": "6-0, 6-1"}, {"score": "6-4, 3-6, 7-5"}]),
             "v", 0, "", "[]"),
            # the SAME dual from the away side — must not double-count
            (w["id"], 7, "girls", "B", "A", 0, "regular", 2, 5, 0, 1,
             _json.dumps([{"score": "6-0, 6-1"}, {"score": "6-4, 3-6, 7-5"}]),
             "v", 0, "", "[]"),
            # a JV dual — excluded
            (w["id"], 7, "girls", "A", "C", 1, "regular", 2, 1, 1, 0,
             _json.dumps([{"score": "6-0, 6-0"}]), "jv", 0, "1S/2D", "[]"),
            # a pre-JV archive row (level NULL) — varsity, included
            (w["id"], 7, "girls", "C", "D", 1, "state", 3, 2, 1, 0,
             _json.dumps([{"score": "7-6, 6-2"}]), None, 0, "", "[]"),
            # a showcase pod pro set — no standard set, nothing enters
            (w["id"], 7, "girls", "A", "D", 1, "showcase_pod", 1, 0, 1, 0,
             _json.dumps([{"score": "8-3"}]), "v", 0, "", "[]"),
        ]
        conn.executemany(
            "INSERT INTO world_jhsaa_dual (world_id, year, gender, school, opp,"
            " home, phase, pf, pa, won, district, lines, level, tied, shape,"
            " played) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        conn.commit()
    finally:
        conn.close()

    world._scoreline_cache.clear()
    d = world.jhsaa_scoreline_realism(w["id"], 7, "girls")
    o = d["overall"]
    got = {r["key"]: round(r["sim"], 1) for r in o["rows"] if r["sim"]}
    # 7 standard sets total: 6-0, 6-1, 6-4, 6-3(3-6), 7-5, 7-6, 6-2
    assert o["sets"] == 7, o
    assert got == {"6-0": round(100 / 7, 1), "6-1": round(100 / 7, 1),
                   "6-2": round(100 / 7, 1), "6-3": round(100 / 7, 1),
                   "6-4": round(100 / 7, 1), "7-5": round(100 / 7, 1),
                   "7-6": round(100 / 7, 1)}, got
    assert o["matches"] == 3 and round(o["three_set"], 1) == round(100 / 3, 1)
    fams = {f["key"]: f for f in d["families"]}
    assert fams["regular"]["sets"] == 5
    assert fams["postseason"]["sets"] == 2       # the level-NULL state dual
    assert fams["showcase"]["sets"] == 0         # the pro set fell out


def _archive_season(world, w, year, gender, scores, phase="regular"):
    """Archive one synthetic varsity season: `scores` is a list of set-score
    strings, one line each, written as home-side rows so the fold sees each
    exactly once. Also writes the `world_jhsaa` summary row `jhsaa_years`
    reads, since that is what makes a year exist to the pages."""
    import json as _json
    conn = world._db()
    try:
        conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data)"
                     " VALUES (?,?,?,?)", (w["id"], year, gender, "{}"))
        conn.executemany(
            "INSERT INTO world_jhsaa_dual (world_id, year, gender, school, opp,"
            " home, phase, pf, pa, won, district, lines, level, tied, shape,"
            " played) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(w["id"], year, gender, "A", "B", 1, phase, 1, 0, 1, 1,
              _json.dumps([{"score": s}]), "v", 0, "", "[]") for s in scores])
        conn.commit()
    finally:
        conn.close()


def _drop_seasons(world, w, gender):
    conn = world._db()
    try:
        conn.execute("DELETE FROM world_jhsaa WHERE world_id=? AND gender=?",
                     (w["id"], gender))
        conn.execute("DELETE FROM world_jhsaa_dual WHERE world_id=? AND gender=?",
                     (w["id"], gender))
        conn.commit()
    finally:
        conn.close()
    world._scoreline_cache.clear()
    world._gapband_cache.clear()


def _archive_lines(world, w, year, gender, school, opp, lines, phase="regular"):
    """Archive one home-side varsity dual with fully-specified `lines`
    (slot / home names / away names / score / home_won)."""
    import json as _json
    conn = world._db()
    try:
        if not conn.execute("SELECT 1 FROM world_jhsaa WHERE world_id=? AND year=?"
                            " AND gender=?", (w["id"], year, gender)).fetchone():
            conn.execute("INSERT INTO world_jhsaa (world_id, year, gender, data)"
                         " VALUES (?,?,?,?)", (w["id"], year, gender, "{}"))
        conn.execute(
            "INSERT INTO world_jhsaa_dual (world_id, year, gender, school, opp,"
            " home, phase, pf, pa, won, district, lines, level, tied, shape,"
            " played) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (w["id"], year, gender, school, opp, 1, phase, 1, 0, 1, 1,
             _json.dumps(lines), "v", 0, "", "[]"))
        conn.commit()
    finally:
        conn.close()


def _two_schools(gender, season_year):
    """Two real programs and their rebuilt rosters for `season_year`, sorted by
    OVR (best first) — the fold resolves archived NAMES against exactly this."""
    schools = jhsaa.load_schools(gender)[:2]
    rosters = [sorted(jhsaa.build_roster(s, season_year, ""),
                      key=lambda p: -p.current_overall()) for s in schools]
    return schools, rosters


def test_gap_band_fold_buckets_lines_by_resolved_ovr_gap():
    """‼️ THE CHECK THAT SEES A MATCHUP-CURVE CHANGE (owner, 2026-09): lines
    bucketed by the OVR gap between the two sides, favourite win rate and set
    decisiveness per band. The archive holds NAMES, so the fold rebuilds the
    season's rosters and resolves them — pinned here against real programs'
    rebuilt rosters: a line's band is the band its two players' OVR gap falls
    in, a doubles pair averages its two, an unresolvable name is counted and
    skipped, and a pro-set line (no best-of-3) never enters."""
    import app.world as world
    w = world.get_or_create(4444)
    _drop_seasons(world, w, "boys")
    year = 2
    season_year = world.BASE_YEAR + year + 1
    (sa, sb), (ra, rb) = _two_schools("boys", season_year)
    best_a, worst_b = ra[0], rb[-1]
    gap_s = abs(best_a.current_overall() - worst_b.current_overall())
    pair_a, pair_b = ra[:2], rb[-2:]
    gap_d = abs(sum(p.current_overall() for p in pair_a) / 2
                - sum(p.current_overall() for p in pair_b) / 2)
    try:
        _archive_lines(world, w, year, "boys", sa.name, sb.name, [
            # singles: the favourite (home, best of A) wins in lopsided straight sets
            {"slot": "S1", "home": [best_a.name], "away": [worst_b.name],
             "score": "6-0, 6-1", "home_won": True},
            # doubles: the favourite (home pair) LOSES in three sets
            {"slot": "D1", "home": [p.name for p in pair_a],
             "away": [p.name for p in pair_b],
             "score": "6-4, 3-6, 4-6", "home_won": False},
            # a name the rebuilt roster does not carry: counted, skipped
            {"slot": "S2", "home": ["Nobody Atall"], "away": [worst_b.name],
             "score": "6-2, 6-2", "home_won": True},
            # a showcase pro set: not a best-of-3, never enters
            {"slot": "S3", "home": [best_a.name], "away": [worst_b.name],
             "score": "8-3", "home_won": True},
        ])
        d = world.jhsaa_gap_bands(w["id"], year, "boys", "")
        assert d["year"] == year and d["season_year"] == season_year
        assert d["lines"] == 3 and d["unresolved"] == 1
        groups = {g["key"]: {r["band"]: r for r in g["rows"]} for g in d["groups"]}
        bs, bd = world._gap_band(gap_s), world._gap_band(gap_d)
        s = groups["singles"][bs]
        assert s["n"] == 1 and s["fav_win"] == 100.0
        assert s["three_set"] == 0.0 and s["lopsided"] == 100.0
        dd = groups["doubles"][bd]
        assert dd["n"] == 1 and dd["fav_win"] == 0.0
        assert dd["three_set"] == 100.0 and dd["lopsided"] == 0.0
        # every other band in each discipline is empty and reports no rate
        for key, rows in (("singles", groups["singles"]), ("doubles", groups["doubles"])):
            for band, r in rows.items():
                if band != (bs if key == "singles" else bd):
                    assert r["n"] == 0 and r["fav_win"] is None, (key, band, r)
        assert sum(r["n"] for r in groups["all"].values()) == 2
        # memoised per season (and never another's)
        assert world.jhsaa_gap_bands(w["id"], year, "boys", "") is d
    finally:
        _drop_seasons(world, w, "boys")


def test_gap_bands_compare_is_a_pure_fold():
    import app.world as world

    def season(year, n, fav, three, lop, lines=10, unresolved=0):
        rows = [{"band": b[0], "label": b[1], "n": n, "fav_win": fav,
                 "three_set": three, "lopsided": lop} for b in world.OVR_GAP_BANDS]
        return {"year": year, "season_year": 2000 + year, "lines": lines,
                "unresolved": unresolved,
                "groups": [{"key": k, "label": k, "rows": [dict(r) for r in rows]}
                           for k in ("all", "singles", "doubles")]}

    cur = season(9, 10, 80.0, 20.0, 40.0)
    prev = season(8, 12, 70.0, 30.0, 30.0)
    both = world.gap_bands_compare(cur, prev)
    r = both["groups"][0]["rows"][0]
    assert both["year"] == 9 and both["prev_year"] == 8
    assert r["n"] == 10 and r["prev_n"] == 12
    assert r["d_fav_win"] == 10.0 and r["d_three_set"] == -10.0
    assert r["d_lopsided"] == 10.0
    # oldest season: no previous, every prev_/d_ figure None
    solo = world.gap_bands_compare(cur, None)
    r0 = solo["groups"][0]["rows"][0]
    assert solo["prev_year"] is None and r0["prev_n"] is None
    assert r0["prev_fav_win"] is None and r0["d_fav_win"] is None
    # an empty band on either side has no shift (a rate over zero is not a number)
    empty = season(8, 0, None, None, None)
    d = world.gap_bands_compare(cur, empty)["groups"][0]["rows"][0]
    assert d["prev_n"] == 0 and d["d_fav_win"] is None


def test_realism_fold_is_per_season():
    """‼️ THE REPORT: "the realism page reports the same numbers every season
    regardless of what is in the sim." The fold WAS folding the right season —
    the shape is a property of the engine and prints identically at ~200k sets
    — so this pins the property the report doubted: two seasons archived with
    different shapes fold to different histograms, each equal to its own rows,
    and the memo never serves one season's fold for another."""
    import app.world as world
    w = world.get_or_create(4343)
    _drop_seasons(world, w, "boys")
    try:
        # year 3: blowout-shaped (three 6-0s, one 7-6); year 4: the inverse
        _archive_season(world, w, 3, "boys", ["6-0, 6-0", "6-0, 7-6"])
        _archive_season(world, w, 4, "boys", ["7-6, 7-6", "7-6, 6-0"])
        d3 = world.jhsaa_scoreline_realism(w["id"], 3, "boys")
        d4 = world.jhsaa_scoreline_realism(w["id"], 4, "boys")
        s3 = {r["key"]: r["sim"] for r in d3["overall"]["rows"]}
        s4 = {r["key"]: r["sim"] for r in d4["overall"]["rows"]}
        assert s3["6-0"] == 75.0 and s3["7-6"] == 25.0
        assert s4["6-0"] == 25.0 and s4["7-6"] == 75.0
        assert d3["year"] == 3 and d4["year"] == 4
        # memoised per season: the same object comes back, and never the other's
        assert world.jhsaa_scoreline_realism(w["id"], 3, "boys") is d3
        assert world.jhsaa_scoreline_realism(w["id"], 4, "boys") is d4

        # and the season-over-season composition reads the two as this/last
        cmp = world.scoreline_compare(d4, d3)
        row = {r["key"]: r for r in cmp["overall"]["rows"]}
        assert cmp["year"] == 4 and cmp["prev_year"] == 3
        assert row["6-0"]["sim"] == 25.0 and row["6-0"]["prev"] == 75.0
        assert row["6-0"]["delta"] == -50.0
        assert row["7-6"]["delta"] == 50.0
        assert cmp["overall"]["shift"] == 50.0       # TV: half of |−50|+|50|
        # the Oregon baseline rides along untouched, as a reference, per row
        assert row["6-0"]["real"] == 26.4
        assert round(row["6-0"]["vs_real"], 1) == -1.4
    finally:
        _drop_seasons(world, w, "boys")


def test_scoreline_compare_handles_the_oldest_season():
    """On the oldest archived season there is no previous one: every last-season
    figure is None (a dash on the page), never a zero — a zero would claim "no
    sets last year", which is a different statement. And a family the previous
    season did not play (no sets) has no shift, rather than a perfect 0.0."""
    import app.world as world
    keys = ["6-0", "6-1", "6-2", "6-3", "6-4", "7-5", "7-6"]

    def table(shares, sets, three=10.0, **extra):
        return {"rows": [{"key": k, "sim": shares.get(k, 0.0), "real": 1.0,
                          "diff": 0.0} for k in keys],
                "sets": sets, "matches": sets // 2, "three_set": three,
                "tv": 0.0, **extra}

    cur = {"year": 9,
           "overall": table({"6-0": 50.0, "7-6": 50.0}, 10),
           "families": [table({"6-0": 50.0, "7-6": 50.0}, 10, key="regular",
                              label="League season"),
                        table({}, 0, key="showcase", label="Showcases")],
           "real_three_set": 13.8}
    solo = world.scoreline_compare(cur, None)
    assert solo["prev_year"] is None
    assert all(r["prev"] is None and r["delta"] is None
               for r in solo["overall"]["rows"])
    assert solo["overall"]["shift"] is None
    assert solo["overall"]["prev_sets"] is None
    assert solo["overall"]["three_set_delta"] is None
    # `sim` and the baseline are still there to read
    assert solo["overall"]["rows"][0]["sim"] == 50.0
    assert solo["overall"]["rows"][0]["real"] == 1.0

    prev = {"year": 8,
            "overall": table({"6-0": 40.0, "7-6": 60.0}, 20, three=30.0),
            "families": [table({"6-0": 40.0, "7-6": 60.0}, 20, three=30.0,
                               key="regular", label="League season"),
                         table({}, 0, key="showcase", label="Showcases")],
            "real_three_set": 13.8}
    both = world.scoreline_compare(cur, prev)
    assert both["overall"]["shift"] == 10.0
    assert both["overall"]["three_set_delta"] == -20.0
    fams = {f["key"]: f for f in both["families"]}
    assert fams["regular"]["shift"] == 10.0
    # neither season played a showcase: nothing to compare, not a match of 0.0 —
    # and the rows say so too, never a 0.0 share beside a shift
    assert fams["showcase"]["shift"] is None
    assert fams["showcase"]["three_set_delta"] is None
    assert all(r["prev"] is None and r["delta"] is None
               for r in fams["showcase"]["rows"])


def test_realism_page_renders_this_season_against_last():
    """The page dereferences the comparison by attribute, and a template is the
    one place where a wrong shape renders instead of raising — so render it with
    two archived seasons under the app's own world and read the numbers back
    off the HTML: both season labels, this season's share, last season's, and
    the shift between them."""
    import re
    import app.world as world
    from app.web.server import create_app
    from app.web.state import DEFAULT_SEED
    import os
    os.environ.setdefault("PTC_NO_BOOT_WARM", "1")
    w = world.get_or_create(DEFAULT_SEED)
    _drop_seasons(world, w, "girls")
    # Once a world row exists a cold request gets the WARMING SHELL, not the page
    # (`_prime_world`); no JHSAA surface reads a college program, so reporting
    # warm is honest here — the stub `tests/test_jhsaa_routes.py::warm_client` uses.
    real_primed, real_prime = world.is_primed, world.prime
    world.is_primed = lambda *a, **k: True
    world.prime = lambda *a, **k: None
    try:
        _archive_season(world, w, 5, "girls", ["6-0, 6-0", "6-0, 7-6"])
        _archive_season(world, w, 6, "girls", ["7-6, 7-6", "7-6, 6-0"])
        client = create_app().test_client()
        html = client.get("/jhsaa/realism?g=girls").get_data(as_text=True)
        # newest season (6 -> 2033) against the one before it (5 -> 2032)
        y6, y5 = world.BASE_YEAR + 6 + 1, world.BASE_YEAR + 5 + 1
        assert f"{y6} vs {y5}" in html
        # the 6-0 row: this season 25.0, last season 75.0, shift -50.0, Oregon 26.4
        row = re.search(r"<tr>\s*<td class=\"pl\"><b>6-0</b>.*?</tr>", html, re.S).group(0)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        text = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        assert text[1] == "25.0" and text[2] == "75.0" and text[3] == "-50.0"
        assert text[-1] == "26.4"
        assert "shift from last season <b>50.0</b>" in html
        # the oldest season has nothing before it and says so
        html5 = client.get(f"/jhsaa/realism?g=girls&year=5").get_data(as_text=True)
        assert "nothing earlier to compare against" in html5
        row5 = re.search(r"<tr>\s*<td class=\"pl\"><b>6-0</b>.*?</tr>", html5, re.S).group(0)
        text5 = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row5, re.S)]
        assert text5[1] == "75.0" and text5[2] == "—" and text5[3] == "—"
        # the gap-band panel is ON DEMAND: the plain page offers the button and
        # does not rebuild a roster
        assert "Compare by gap band" in html and "Favourite won %" not in html
    finally:
        world.is_primed, world.prime = real_primed, real_prime
        _drop_seasons(world, w, "girls")


def test_realism_page_renders_the_gap_band_comparison(monkeypatch):
    """`?bands=1` runs the two-season roster rebuild through the deferred job and
    renders the by-band table: both seasons' rates and the shift, per band. The
    association is patched down to the two programs the archived lines name (the
    `test_jhsaa_toc` idiom), so the rebuild is two rosters rather than ~900 and
    the deferred job finishes inside its first wait."""
    import re
    import app.world as world
    import app.jhsaa as jh
    from app.web.server import create_app
    from app.web.state import DEFAULT_SEED
    import os
    os.environ.setdefault("PTC_NO_BOOT_WARM", "1")
    w = world.get_or_create(DEFAULT_SEED)
    _drop_seasons(world, w, "girls")
    real_primed, real_prime = world.is_primed, world.prime
    world.is_primed = lambda *a, **k: True
    world.prime = lambda *a, **k: None
    salt = world.active_salt(DEFAULT_SEED)
    schools = jh.load_schools("girls")[:2]
    real_load = jh.load_schools
    monkeypatch.setattr(jh, "load_schools", lambda g: schools)
    try:
        for year, fav_wins in ((5, True), (6, False)):
            sy = world.BASE_YEAR + year + 1
            ra, rb = (sorted(jh.build_roster(s, sy, salt),
                             key=lambda p: -p.current_overall()) for s in schools)
            _archive_lines(world, w, year, "girls", schools[0].name, schools[1].name, [
                {"slot": "S1", "home": [ra[0].name], "away": [rb[-1].name],
                 "score": "6-0, 6-0" if fav_wins else "4-6, 6-7",
                 "home_won": fav_wins}])
        client = create_app().test_client()
        html = None
        for _ in range(20):                      # the deferred job's interstitial
            html = client.get("/jhsaa/realism?g=girls&bands=1").get_data(as_text=True)
            if "Building" not in html:
                break
        assert "Favourite won %" in html
        # the singles line's band: favourite lost this season (0.0), won last (100.0)
        rows = re.findall(r"<tr>\s*<td class=\"pl\"><b>(\d+-\d+|29\+)</b>.*?</tr>", html, re.S)
        assert rows, html[:2000]
        # find the first band row carrying a match count of 1 in the All courts table
        m = re.search(r"<td class=\"pl\"><b>[^<]+</b>[^<]*<span[^>]*>[^<]*</span></td>\s*"
                      r"<td class=\"num\">1 <span class=\"jh-rl-base\">/ 1</span></td>\s*"
                      r"<td class=\"num\"><b>0\.0</b></td>\s*"
                      r"<td class=\"num jh-rl-base\">100\.0</td>\s*"
                      r"<td class=\"num\">-100\.0</td>", html, re.S)
        assert m, "expected a band row reading fav 0.0 / 100.0 / -100.0"
    finally:
        monkeypatch.setattr(jh, "load_schools", real_load)
        world.is_primed, world.prime = real_primed, real_prime
        _drop_seasons(world, w, "girls")
