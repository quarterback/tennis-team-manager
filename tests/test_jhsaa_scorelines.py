"""HS scoreline realism (engine.fast.HS_PROFILE) — see
docs/AAR-jhsaa-scoreline-realism.md and scripts/jhsaa_scoreline_benchmark.py.

Real HS tennis (five seasons of Oregon results) is blowout-shaped: 6-0 is the
most common set (26.4%) and 7-6 the rarest (3.9%). The college-calibrated fast
model produced the near-inverse (7-6 at 14.9%, 6-0 at 2.5%). These tests pin
the corrected shape loosely — the benchmark script is the precision
instrument — and pin exactly the null-profile guarantee the college game
depends on."""
import random
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


def test_matchup_curve_follows_the_competitive_bands():
    """‼️ THE OWNER'S BAND SPEC (2026-08), pinned end to end through the real
    engine: an OVR difference is read as five competitive bands and the
    favourite's win rate rises progressively across them.

        0-6 peers · 7-14 modest · 15-21 clear · 22-28 strong · 29+ major

    Measured at each band's TOP edge, where the curve is most likely to drift.
    Ranges are the spec's, widened for sampling noise at this n (se ~1.8pt).
    This supersedes the scoreline test above: it pins the decision that replaced
    it, and it is the closer guard on the thing that actually went wrong — at
    the old dials a three-point gap already won 94.7% of matches.
    """
    from engine.fast import simulate_fast
    from app.development import Prospect
    from app.player_attributes import RICH_ATTRS

    def flat(ovr, name):
        # A FLAT player (every attribute equal) so the measured gap is exactly
        # the OVR gap — engine.fast's lane weights are chosen to reproduce the
        # overall gap exactly for flat players, which is what makes this a
        # reading of the curve rather than of a play style.
        grades = {a: float(ovr) for a in RICH_ATTRS}
        return Prospect(name=name, current=grades,
                        potential=dict(grades)).engine_player()

    def favourite_rate(gap, n=800):
        fav, dog = flat(45 + gap, "fav"), flat(45, "dog")
        wins = sum(simulate_fast(fav, dog, seed=4_000_000 + i,
                                 fmt=jhsaa.MATCH_FORMAT, first_server=i % 2,
                                 profile=HS_PROFILE).winner == 0
                   for i in range(n))
        return 100 * wins / n

    # (gap, low, high) — the band's own range, with noise headroom.
    for gap, lo, hi in ((0, 46, 56),      # dead level: a coin flip
                        (6, 55, 68),      # peers, top edge
                        (14, 66, 80),     # modest, top edge
                        (21, 79, 91),     # clear, top edge
                        (28, 89, 98)):    # strong, top edge
        rate = favourite_rate(gap)
        assert lo <= rate <= hi, f"{gap} OVR gap -> {rate:.1f}% (want {lo}-{hi}%)"

    # major mismatches are decisive but never certain
    assert 93 <= favourite_rate(40) <= 100


def test_peer_band_is_identity_and_the_curve_is_monotone():
    """The peer band must not touch the gap at all — that is what preserves
    volatility between near-equals — and the curve must rise without a step at
    any band edge (a discontinuity would make one OVR point worth a jump)."""
    from engine.fast import band_gap, BAND_EDGES_OVR, GRADE_SPAN

    # ‼️ DERIVED FROM THE TABLE, never a typed 6.0 — the peer band's WIDTH is a
    # tuning decision that has moved twice (6 -> 7 -> 3), and a literal here
    # fails the day it moves again while saying nothing about the property.
    peer = BAND_EDGES_OVR[0]
    for frac in (0.0, 0.2, 0.5, 0.9, 1.0):
        ovr = peer * frac
        assert band_gap(ovr / GRADE_SPAN) == ovr / GRADE_SPAN

    assert band_gap(-0.35) == -band_gap(0.35)          # sign-symmetric

    prev = -1.0
    for step in range(0, 601):                          # 0-60 OVR in 0.1 steps
        v = band_gap(step / 10.0 / GRADE_SPAN)
        assert v > prev or step == 0, step
        prev = v
    # continuous at every edge: approaching from below lands on the edge value
    for edge in BAND_EDGES_OVR:
        below = band_gap((edge - 1e-6) / GRADE_SPAN)
        at = band_gap(edge / GRADE_SPAN)
        assert abs(at - below) < 1e-6, edge


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
    finally:
        world.is_primed, world.prime = real_primed, real_prime
        _drop_seasons(world, w, "girls")
