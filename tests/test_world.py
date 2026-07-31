"""Unified-world engine: serialization, the development drip, and the pure
post-season rollover steps (graduate / portal / signings intake).

These run on small real-school rosters with synthetic STR + signings, so they
exercise the logic without simulating full seasons. The full week-by-week DB
driver (advance_week / finalize) is covered by the manual smoke in the PR.
"""
import copy
import random

from app import world
from app.ncaa import load_division, build_roster, ROSTER_SIZE, roster_cap
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
    for (division, gender), sc in a.items():
        for roster in sc.values():
            assert len(roster) <= roster_cap(division)           # never over the per-division cap
            if division in ("D3", "D4"):                         # auto-gen walk-ons top these to cap
                assert len(roster) == roster_cap(division)
            # D1/D2 fill up to cap from the recruit pool only (no auto-gen), so with the
            # test's one-signing-per-program they top up partially — that's by design.
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


def test_decision_week_skews_late_for_top_recruits():
    """Signing timing drips across the whole regular season and is rank-skewed:
    top recruits hold out (commit late, never in the opening weeks); the back of
    the class commits early. Locks the recruiting-pace fix in place."""
    import statistics as st
    window = 18

    def mean_week(rank_frac):
        return st.mean(world._decision_week(type("P", (), {"pid": f"p{rank_frac}_{k}"})(),
                                            "salt", rank_frac, window) for k in range(3000))

    top, mid, low = mean_week(0.0), mean_week(0.5), mean_week(1.0)
    # monotonic: better recruits commit later
    assert top > mid > low
    # blue-chips can't commit in the opening stretch; the back of the class can go week 0
    top_min = min(world._decision_week(type("P", (), {"pid": f"t{k}"})(), "s", 0.0, window)
                  for k in range(3000))
    low_min = min(world._decision_week(type("P", (), {"pid": f"b{k}"})(), "s", 1.0, window)
                  for k in range(3000))
    assert top_min >= window * world.SIGNING_FLOOR_TOP - 1 and low_min == 0
    # everything lands inside the regular-season window
    assert all(0 <= world._decision_week(type("P", (), {"pid": f"x{k}"})(), "s", k / 50, window) < window
               for k in range(51))


def test_transfers_respect_division_and_one_per_career():
    """Engine transfers stay in-division or move at most one level (no D1->D3
    skips), and a player who has already transferred isn't moved again."""
    import random
    from app import world
    from app.ncaa import load_division, build_roster

    rank = {"D1": 0, "D2": 1, "D3": 2}
    rosters, div_of = {}, {}
    for d in ("D1", "D2", "D3"):
        prog = {p.school: p for p in load_division(d, "women").programs}
        picks = list(prog)[:12]
        rosters[(d, "women")] = {s: [copy.deepcopy(q) for q in build_roster(prog[s])] for s in picks}
        for s in picks:
            div_of[s] = d
    # a player who already transferred once — clear prior school-change history
    orig_school = list(rosters[("D1", "women")])[0]
    flagged = rosters[("D1", "women")][orig_school][0]
    flagged.class_year = "So"                      # survives graduation
    flagged.history = [{"year": 0, "school": "Somewhere Else"}, {"year": 1, "school": orig_school}]
    flagged_pid = flagged.pid
    assert world._career_transfers(flagged) == 1

    world.graduate(rosters)                       # open seats, as at a real rollover
    out = world.transfer_portal(rosters, {}, random.Random(3), "women")

    for _tag, _name, src, dest, _s in out["sample"]:
        if div_of.get(src) and div_of.get(dest):
            assert abs(rank[div_of[src]] - rank[div_of[dest]]) <= 1   # never skip a division
    # the already-transferred player was not moved again — still on their old roster
    assert any(getattr(q, "pid", None) == flagged_pid
               for q in rosters[("D1", "women")][orig_school])


def test_past_individual_champions_reads_snapshots(tmp_path):
    """The past-winners record: year-by-year singles/doubles champions come straight
    from the world_championship snapshots, newest first, keyed by calendar year."""
    import json
    prev_db, prev_ready = world.WORLD_DB, world._schema_ready_for
    world.WORLD_DB = str(tmp_path / "w.db")
    world._schema_ready_for = None
    try:
        conn = world._db()
        conn.execute("INSERT INTO world (seed, year, week) VALUES (?,?,?)", (2026, 2, 0))
        wid = conn.execute("SELECT id FROM world WHERE seed=2026").fetchone()["id"]

        def blob(event, label):
            return json.dumps({"event": event, "n_seeds": 16, "entries": [], "rounds": [],
                               "champion": {"label": label, "school": "Stanford",
                                            "conf_abbr": "ACC", "pid": "p1", "seed": 1},
                               "runner_up": {"label": "R Up", "school": "UCLA",
                                             "conf_abbr": "B1G", "pid": "p2", "seed": 2}})
        for yr, name in ((0, "Alice Ace"), (1, "Beth Baseline")):
            for event in ("Singles", "Doubles"):
                conn.execute("INSERT INTO world_championship VALUES (?,?,?,?,?,?)",
                             (wid, yr, "D1", "women", event, blob(event, name)))
        conn.commit()
        conn.close()

        out = world.past_individual_champions(2026, "D1", "women")
        # newest first, calendar-year keyed
        assert [e["year"] for e in out] == [world.BASE_YEAR + 1, world.BASE_YEAR]
        assert out[0]["singles"]["champion"]["label"] == "Beth Baseline"
        assert out[0]["doubles"]["champion"]["label"] == "Beth Baseline"
        assert out[0]["singles"]["runner_up"]["school"] == "UCLA"
        assert out[1]["singles"]["champion"]["label"] == "Alice Ace"
        # a universe with no snapshots (and an unknown world) return empty
        assert world.past_individual_champions(2026, "D1", "men") == []
        assert world.past_individual_champions(9999, "D1", "women") == []
    finally:
        world.WORLD_DB = prev_db
        world._schema_ready_for = prev_ready


def test_refill_enforces_a_six_player_floor_in_every_division():
    """Rosters thin over seasons by design, but below six there is no lineup at all —
    Team.doubles indexes 0..5 and the engine crashed mid-bracket. D1/D2 still get no
    walk-on DEPTH; they just never drop under the six a dual needs."""
    import copy
    from app.ncaa import load_division, build_roster, roster_cap
    from app import world

    rosters = {}
    for div in ("D1", "D3"):
        prog = {p.school: p for p in load_division(div, "men").programs}
        school = list(prog)[0]
        rosters[(div, "men")] = {
            school: [copy.deepcopy(q) for q in build_roster(prog[school])][:2]}

    world.refill_walkons(rosters, 1, 2026)

    d1 = list(rosters[("D1", "men")].values())[0]
    d3 = list(rosters[("D3", "men")].values())[0]
    from app.ncaa import lineup_size
    assert len(d1) == lineup_size("D1"), "D1 must reach the lineup floor, and stop there"
    assert len(d3) == roster_cap("D3"), "D3 still fills its whole cap"
    assert len({p.pid for p in d1}) == len(d1), "floor filler duplicated a pid"


def test_refill_leaves_healthy_rosters_alone():
    import copy
    from app.ncaa import load_division, build_roster
    from app import world

    prog = {p.school: p for p in load_division("D1", "men").programs}
    school = list(prog)[0]
    full = [copy.deepcopy(q) for q in build_roster(prog[school])]
    rosters = {("D1", "men"): {school: list(full)}}
    assert world.refill_walkons(rosters, 1, 2026) == 0
    assert len(rosters[("D1", "men")][school]) == len(full)


def test_walkon_personas_sit_below_their_division_core():
    """A walk-on is a KNOWN quantity, drawn from an explicit division x gender band —
    never a phantom blue-chip, and a D1 walk-on is a different animal from a D3 one."""
    import random
    from app.ncaa import WALKON_BAND, walkon_talent

    rng = random.Random(3)
    for (div, gender), (lo, hi) in WALKON_BAND.items():
        vals = [walkon_talent(div, gender, rng) for _ in range(200)]
        assert lo <= min(vals) and max(vals) <= hi
    # ordering: D1 > D2 > D4 > D3 within a gender, and men's bands sit above women's
    for g in ("men", "women"):
        d1, d2, d3, d4 = (WALKON_BAND[(d, g)][0] for d in ("D1", "D2", "D3", "D4"))
        assert d1 > d2 > d4 > d3, f"{g} walk-on bands are not tier-ordered"
    for d in ("D1", "D2", "D3", "D4"):
        assert WALKON_BAND[(d, "men")][0] > WALKON_BAND[(d, "women")][0]


def test_floor_filler_is_a_walkon_not_a_star():
    """The roster floor must never hand a thin program a player who decides matches."""
    import copy
    from app.ncaa import load_division, build_roster
    from app import world

    prog = {p.school: p for p in load_division("D1", "men").programs}
    school = list(prog)[0]
    full = [copy.deepcopy(q) for q in build_roster(prog[school])]
    rosters = {("D1", "men"): {school: full[:2]}}
    world.refill_walkons(rosters, 1, 2026)

    roster = rosters[("D1", "men")][school]
    added = [p for p in roster if getattr(p, "walk_on", False) and p not in full[:2]]
    assert added, "no filler was added"
    best_real = max(p.current_overall() for p in full[:2])
    assert all(p.current_overall() <= best_real for p in added), \
        "a floor filler outrated the real roster"
