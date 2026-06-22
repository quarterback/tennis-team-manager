from app import scholarships as sch
from app.ncaa import Program, build_roster, reset_caches, ROSTER_SIZE


def _prog(division, academics=0.5, conf="ACC"):
    return Program(school=f"Test {division}", conf=conf, conf_abbr=conf, division=division,
                   gender="men", abbr="XX", color="#000", strength=0.6, academics=academics)


def test_exchange_rate_diminishes_by_level():
    d1 = sch.limits("D1"); d2 = sch.limits("D2"); d3 = sch.limits("D3")
    assert d1["rate"] > d2["rate"] > d3["rate"]
    assert d1["effective_value"] > d2["effective_value"] > d3["effective_value"]
    assert d1["fractional"] and d2["fractional"] and not d3["fractional"]


def test_elite_d3_worth_d1_but_fewer():
    elite = sch.limits("D3", academics=0.95)
    plain = sch.limits("D3", academics=0.5)
    assert elite["elite_d3"] and elite["rate"] == sch.limits("D1")["rate"]   # D1-worth aid
    assert elite["count"] < sch.limits("D1")["count"]                        # but fewer
    assert elite["effective_value"] > plain["effective_value"]


def test_slots_track_classification_in_rosters():
    reset_caches()
    d1 = build_roster(_prog("D1"))
    reset_caches()
    d3 = build_roster(_prog("D3"))
    assert sum(not p.walk_on for p in d1) == sch.slots(_prog("D1"))
    assert sum(not p.walk_on for p in d3) == sch.slots(_prog("D3"))
    assert sum(p.walk_on for p in d3) > sum(p.walk_on for p in d1)           # D3 funds fewer


def test_editor_overrides_round_trip():
    try:
        sch.set_limit("D1", count=3)
        assert sch.slots(_prog("D1")) == 3
        assert sch.any_overrides()
    finally:
        sch.clear_overrides()
    assert not sch.any_overrides() and sch.slots(_prog("D1")) == 8   # D1 fully funds all 8
