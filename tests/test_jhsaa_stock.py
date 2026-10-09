"""The attribute-level development model (owner spec 2026-10, `app/jhsaa_develop.py`).

Pins the contract, not the calibration: pre-era cohorts untouched; an era-on
roster with no archived staff is the scalar path to the bit; coached growth
never passes a trainable cap or overspends the stock; a pinned profile freezes
the player against a constant change; coaching separates staffs in the right
order; every coached attribute reaches the engine; determinism."""
import copy

import pytest

from app import jhsaa as jh
from app import jhsaa_develop as jd
from app.jhsaa_coaches import teaching_portfolio
from app.player_attributes import OVERALL_WEIGHTS, _WEIGHT_TOTAL, RICH_ATTRS

GRADES = ("tactics", "singles", "doubles", "development", "talent_id",
          "adaptability", "builder", "feeder", "clutch", "changeover")


def _coach(cid, slot, profile, q):
    return (cid, slot, {g: q for g in GRADES}, teaching_portfolio(cid, profile))


@pytest.fixture(scope="module")
def sample():
    real = jh.stock_era
    jh._schools_cache = None
    sc = jh.load_schools("girls")[0]
    try:
        jh.stock_era = lambda: 10 ** 6
        pre = {p.pid: p for p in jh.build_roster(sc, 2030, "t")}
        jh.stock_era = lambda: 0
        post = {p.pid: p for p in jh.build_roster(sc, 2030, "t")}
        post2 = {p.pid: p for p in jh.build_roster(sc, 2030, "t")}
    finally:
        jh.stock_era = real
    return sc, pre, post, post2


def test_pre_era_cohorts_carry_no_stock_and_era_on_without_staff_is_the_scalar_path(sample):
    sc, pre, post, _ = sample
    assert pre and set(pre) == set(post)
    for pid, a in pre.items():
        b = post[pid]
        assert "stock" not in a.jhsaa
        assert "stock" in b.jhsaa and "stock_pin" in b.jhsaa
        # No archived staff on a fresh file → nothing coached → CURRENT identical.
        assert all(abs(a.current[x] - b.current[x]) < 1e-9 for x in RICH_ATTRS)
        # The trainable ceiling is never below the natural target.
        assert all(b.potential[x] >= a.potential[x] - 1e-9 for x in RICH_ATTRS)


def test_two_builds_are_identical(sample):
    _, _, post, post2 = sample
    for pid, b in post.items():
        c = post2[pid]
        assert b.current == c.current and b.potential == c.potential
        assert b.jhsaa["stock_pin"] == c.jhsaa["stock_pin"]


def _replay(sc, a, prof, staff, n=3, salt="t"):
    ceiling = sum(OVERALL_WEIGHTS[x] * v for x, v in a.potential.items()) / _WEIGHT_TOTAL
    start, _peak, _ = jh._career_plan(sc.key, a.entry_year, a.jhsaa["seat"], salt, ceiling,
                                     a.jhsaa.get("start", 0.0))
    qq = copy.deepcopy(a)
    res = jd.apply_stock(qq, a.pid, salt, prof, dict(a.current), start / ceiling,
                         [(2027 + i, 1.0, staff, 1.0) for i in range(n)])
    return res, qq


def test_coaching_never_passes_a_cap_or_overspends_and_orders_staffs(sample):
    sc, pre, post, _ = sample
    elite = [_coach("c-h", "head", "practice", 0.95), _coach("c-a1", "asst1", "singles", 0.95),
             _coach("c-a2", "asst2", "doubles", 0.95), _coach("c-a3", "asst3", "tactician", 0.95)]
    average = [_coach("av-h", "head", "generalist", 0.5), _coach("av-a1", "asst1", "generalist", 0.5)]
    weak = [_coach("w-h", "head", "generalist", 0.2)]
    gains = {"elite": [], "average": [], "weak": []}
    for pid, a in pre.items():
        prof = post[pid].jhsaa["stock_pin"]
        for name, staff in (("elite", elite), ("average", average), ("weak", weak)):
            res, qq = _replay(sc, a, prof, staff)
            caps = prof["caps"]
            for x in RICH_ATTRS:
                assert qq.current[x] <= max(caps[x], a.current[x]) + 1e-6
                assert qq.current[x] >= a.current[x] - 1e-9        # never below the natural path
            assert res["stock_left"] >= 0.0
            assert res["coached_ovr"] <= prof["extra_ovr"] + 1e-6
            # OVR is DERIVED from the attributes, never set beside them.
            assert qq.current_overall() == round(jd.weighted(qq.current))
            gains[name].append(res["coached_ovr"])
    mean = lambda v: sum(v) / len(v)
    assert mean(gains["elite"]) > mean(gains["average"]) > 0.0
    assert mean(gains["weak"]) == 0.0           # under the teaching floor: nothing


def test_a_pinned_profile_freezes_the_player_against_a_constant_change(sample):
    sc, pre, post, _ = sample
    pid, a = next(iter(pre.items()))
    prof = post[pid].jhsaa["stock_pin"]
    staff = [_coach("c-h", "head", "practice", 0.95), _coach("c-a1", "asst1", "doubles", 0.95)]
    _, q1 = _replay(sc, a, prof, staff)
    old = jd.TRAIN_SPAN
    try:
        jd.TRAIN_SPAN = old * 2            # a retune reaches NEW entrants only
        _, q2 = _replay(sc, a, prof, staff)
    finally:
        jd.TRAIN_SPAN = old
    assert q1.current == q2.current and q1.potential == q2.potential


def test_every_coached_attribute_reaches_the_engine():
    """A skill that raises only a display number is not development. The nine
    drivers (`player_attributes.derive_driver_grades`) plus the rich baskets the
    rally and doubles engines read."""
    from app.player_attributes import PlayerAttributes
    import glob
    import inspect
    import os
    import engine
    src = inspect.getsource(PlayerAttributes.derive_driver_grades)
    for path in glob.glob(os.path.join(os.path.dirname(engine.__file__), "*.py")):
        with open(path) as f:
            src += f.read()
    for k in jd.COACHED:
        for a in jd.CATEGORIES[k]:
            assert f'"{a}"' in src, (k, a)


def test_portfolios_are_deterministic_and_coached_only():
    p1 = teaching_portfolio("coach-x", "singles")
    p2 = teaching_portfolio("coach-x", "singles")
    assert p1 == p2 and p1 and set(p1) <= set(jd.COACHED)
    assert "baseline" in p1 and p1["baseline"] == 1.0
    g = teaching_portfolio("coach-g", "generalist")
    assert len(g) == 2


def test_head_bond_is_neutral_without_history_and_bounded():
    import sqlite3
    from app import jhsaa_coaches as jc
    conn = sqlite3.connect(":memory:")
    conn.executescript(jc._SCHEMA)
    conn.execute("CREATE TABLE jhsaa_preseason (world_id, year, gender, school, strength)")
    conn.execute("CREATE TABLE world_jhsaa_season_row (world_id, year, gender, school, data, v)")
    assert jc.head_bond(conn, 1, "nobody", 5, "girls") == 1.0
    # a head who beat expectation three years running
    for y in (2, 3, 4):
        conn.execute("INSERT INTO jhsaa_coach_history (world_id, year, ident, gender, slot,"
                     " coach_id, school, classification, grp, wins, losses, ties, eff)"
                     " VALUES (1,?,'s','girls','head','h1','S','4A','4A',20,2,0,NULL)", (y,))
        conn.execute("INSERT INTO jhsaa_preseason VALUES (1,?,'girls','S',40.0)", (y,))
        conn.execute("INSERT INTO jhsaa_preseason VALUES (1,?,'girls','T',50.0)", (y,))
        conn.execute("INSERT INTO jhsaa_preseason VALUES (1,?,'girls','U',60.0)", (y,))
    b = jc.head_bond(conn, 1, "h1", 5, "girls")
    assert jc.BOND_BAND[0] <= b <= jc.BOND_BAND[1] and b > 1.0
