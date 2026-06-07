"""Scholarship limits are editable per division AND per gender; the economy
equivalency cap reads through those (override-aware) limits."""
from app import scholarships as sch
from app import economy


def test_default_caps_differ_by_gender_like_real_life():
    # Women's tennis is a headcount sport (8); men's an equivalency sport (4.5).
    assert sch.cap("D1", "men") == 4.5
    assert sch.cap("D1", "women") == 8.0
    assert sch.cap("D2", "men") == 4.5
    assert sch.cap("D2", "women") == 6.0
    assert sch.cap("D3", "men") == sch.cap("D3", "women") == 0.0


def test_economy_cap_reads_through_scholarships():
    assert economy.cap_for("D1", "women") == sch.cap("D1", "women") == 8.0
    assert economy.cap_for("D1", "men") == 4.5


def test_override_one_gender_only():
    try:
        sch.set_limit("D1", "women", cap=10.0, count=10)
        assert sch.cap("D1", "women") == 10.0
        assert economy.cap_for("D1", "women") == 10.0
        assert sch.cap("D1", "men") == 4.5          # men untouched
        assert sch.limits("D1", "women")["count"] == 10
    finally:
        sch.clear_overrides()
    assert sch.cap("D1", "women") == 8.0


def test_division_only_override_hits_both_genders():
    try:
        sch.set_limit("D2", count=2)                 # no gender → both
        assert sch.limits("D2", "men")["count"] == 2
        assert sch.limits("D2", "women")["count"] == 2
    finally:
        sch.clear_overrides()


def test_cap_edit_flows_into_allocation():
    """Editing a gender's cap changes how much equivalency the allocator hands
    out for that gender's rosters."""
    from app.ncaa import Program, build_roster, reset_caches

    def prog(gender):
        return Program(school=f"Cap {gender}", conf="ACC", conf_abbr="ACC",
                       division="D1", gender=gender, abbr="XX", color="#000",
                       strength=0.8)
    try:
        sch.set_limit("D1", "men", cap=2.0)
        reset_caches()
        roster = build_roster(prog("men"))
        summ = economy.budget_summary(roster, "D1", "men")
        assert summ["cap"] == 2.0 and summ["allocated"] <= 2.0 + 1e-9
    finally:
        sch.clear_overrides()
        reset_caches()
