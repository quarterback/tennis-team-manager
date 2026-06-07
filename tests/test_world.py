"""Unified-world engine: serialization, the development drip, and the pure
post-season rollover steps (graduate / portal / signings intake).

These run on small real-school rosters with synthetic STR + signings, so they
exercise the logic without simulating full seasons. The full week-by-week DB
driver (advance_week / finalize) is covered by the manual smoke in the PR.
"""
import copy
import random

from app import world
from app.ncaa import load_division, build_roster, ROSTER_SIZE
from app.development import generate_prospect, RICH_ATTRS


def _mini(gender="men", n=10):
    """A small world slice: a few real D1 + D3 programs, full deep-copied rosters."""
    rosters = {}
    for div in ("D1", "D3"):
        prog = {p.school: p for p in load_division(div, gender).programs}
        schools = list(prog)[:n]
        rosters[(div, gender)] = {s: [copy.deepcopy(q) for q in build_roster(prog[s])]
                                  for s in schools}
    return rosters


def test_prospect_roundtrip_preserves_model():
    p = generate_prospect(random.Random(1), "Test Player", "US", gender="male", talent=55)
    p.class_year = "Jr"; p.walk_on = True; p.history = [{"year": 0, "school": "X"}]
    q = world.prospect_from_dict(world.prospect_to_dict(p))
    assert q.pid == p.pid and q.class_year == "Jr" and q.walk_on
    assert q.current_overall() == p.current_overall()
    assert q.ceiling_overall() == p.ceiling_overall()
    assert q.traits == p.traits and q.history == p.history


def test_development_drip_sums_to_about_a_year():
    p = generate_prospect(random.Random(2), "Drip", "US", gender="male", talent=40)
    drip = copy.deepcopy(p); whole = copy.deepcopy(p)
    for _ in range(world.DEV_WEEKS):
        drip.develop(1.0 / world.DEV_WEEKS)
    whole.develop_year()
    # the weekly drip closes nearly the same gap as one whole-year develop
    assert drip.current_overall() >= p.current_overall()          # never regresses
    assert abs(drip.current_overall() - whole.current_overall()) <= 1


def test_graduate_promotes_classes_and_removes_seniors():
    r = _mini()
    before = sum(len(ros) for sc in r.values() for ros in sc.values())
    senior_pids = {p.pid for sc in r.values() for ros in sc.values() for p in ros
                   if p.class_year == "Sr"}
    grads = world.graduate(r)
    assert grads == len(senior_pids) > 0
    after_pids = {p.pid for sc in r.values() for ros in sc.values() for p in ros}
    assert senior_pids.isdisjoint(after_pids)                     # all seniors gone
    assert before - sum(len(ros) for sc in r.values() for ros in sc.values()) == grads


def test_national_class_is_ranked_and_pooled():
    klass = world.national_class(2026, 0, "men")
    assert len(klass) == world.RECRUIT_POOL
    assert [p.recruit_rank for p in klass] == list(range(1, len(klass) + 1))   # ranked 1..N
    stars = [p.recruit_stars for p in klass]
    assert stars == sorted(stars, reverse=True)                   # tiers descend with rank


def test_finalize_rollover_deterministic_full_and_brings_in_class():
    a, b = _mini(), _mini()
    # one signed freshman per program (real schools present in the mini world)
    def signings_for(r):
        out = {"men": {}}
        for (div, g), schools in r.items():
            for s in schools:
                fr = generate_prospect(random.Random(hash(s) & 0xffff), f"Recruit {s}", "US",
                                       gender="male", talent=48)
                out["men"][s] = [fr]
        return out
    sa = world.finalize_rollover(a, signings_for(a), {}, seed=2026, year=0)
    sb = world.finalize_rollover(b, signings_for(b), {}, seed=2026, year=0)
    assert sa == sb                                               # deterministic summary
    assert sa["graduated"] > 0 and sa["committed"] > 0
    for sc in a.values():
        for roster in sc.values():
            assert len(roster) == ROSTER_SIZE                    # topped back up
    assert any(p.committed and p.class_year == "Fr"
               for sc in a.values() for ros in sc.values() for p in ros)


def test_cross_schedule_respects_caps_and_hosting():
    sched = world.cross_schedule(2026, 0)
    assert sched, "expected a cross-division slate"
    from collections import Counter
    for gender in ("men", "women"):
        games = [m for m in sched if m["gender"] == gender]
        cnt = Counter()
        for m in games:
            cnt[m["home"]] += 1; cnt[m["away"]] += 1
        assert max(cnt.values()) <= world.MAX_CROSS               # ≤ 3 cross duals / team
    for m in sched:
        assert m["home_div"] != m["away_div"]                    # genuinely cross-division
        assert world.DIV_RANK[m["home_div"]] < world.DIV_RANK[m["away_div"]]  # higher hosts


def test_homecooking_is_one_way_and_intl_zero():
    from app.recruiting import program_appeal, School
    s_home = School("Home U", 0.5, "D3", prestige=0.4, academics=0.6, region="W")
    s_away = School("Away U", 0.5, "D3", prestige=0.4, academics=0.6, region="NE")
    # a homebody from the West prefers the West school; a no-homecooking kid is indifferent
    assert program_appeal(0.5, 0.5, s_home, "W", 0.9) > program_appeal(0.5, 0.5, s_away, "W", 0.9)
    assert program_appeal(0.5, 0.5, s_home, "W", 0.0) == program_appeal(0.5, 0.5, s_away, "W", 0.0)
    # international (no home region) is unmoved regardless
    assert program_appeal(0.5, 0.5, s_home, "", 0.0) == program_appeal(0.5, 0.5, s_away, "", 0.0)


def test_cross_division_portal_moves_by_prestige():
    r = _mini(n=14)
    star = next(iter(r[("D3", "men")].values()))[0]
    ps = {star.pid: (56.0, 0.9)}                                  # a reliable D3 star
    summary = world.transfer_portal(r, ps, random.Random(0), "men")
    assert summary["movers"] >= 1
    pres = {p.school: p.prestige for d in ("D1", "D2", "D3")
            for p in load_division(d, "men").programs}
    for kind, name, frm, to, s in summary["sample"]:
        if kind == "up":
            assert pres[to] > pres[frm]
        if kind == "down":
            assert pres[to] < pres[frm]
