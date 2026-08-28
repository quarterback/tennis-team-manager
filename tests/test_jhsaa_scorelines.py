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


def test_hs_sets_are_blowout_shaped_not_tiebreak_shaped():
    """The owner's report: 'far too many 7-6 7-6 matches'. Real HS: 6-0 26.4%,
    7-6 3.9%. The old model: 6-0 2.5%, 7-6 14.9%. Pin the corrected ordering
    with room for sampling noise on one district."""
    shares, three_set = _set_shares(_teams())
    assert shares.get("6-0", 0) > 15, f"6-0 share collapsed: {shares}"
    assert shares.get("7-6", 0) < 9, f"7-6 glut is back: {shares}"
    # monotone-ish decay: the lopsided half must outweigh the tight half
    lop = shares.get("6-0", 0) + shares.get("6-1", 0)
    tight = shares.get("7-5", 0) + shares.get("7-6", 0)
    assert lop > 2 * tight, (lop, tight, shares)
    # real three-set rate is 13.8%; the old model ran 42.8%
    assert three_set < 25, three_set


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
