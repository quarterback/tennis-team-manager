"""Scholarship-equivalency economy: caps, fractional allocation, ledger."""
from app import economy
from app.ncaa import Program, build_roster, reset_caches, ROSTER_SIZE, SCHOLARSHIP_SLOTS


def _prog(school, strength, division="D1", gender="men"):
    return Program(school=school, conf="ACC", conf_abbr="ACC", division=division,
                   gender=gender, abbr="XX", color="#000", strength=strength)


def test_caps_match_full_funding_rule():
    # Game rule: men are FULLY FUNDED to match women (not real-NCAA men's 4.5
    # equivalency) — so D1 men = D1 women = 8.0, D2 men = D2 women = 6.0.
    assert economy.cap_for("D1", "men") == 8.0
    assert economy.cap_for("D1", "women") == 8.0
    assert economy.cap_for("D2", "men") == 6.0
    assert economy.cap_for("D2", "women") == 6.0
    assert economy.cap_for("D3", "men") == 0.0
    assert economy.cap_for("D3", "women") == 0.0


def test_cap_normalizes_loose_inputs():
    assert economy.cap_for("d1", "MEN") == 8.0
    assert economy.cap_for("Division I", "female") == 8.0
    assert economy.offers_aid("D1", "men") and not economy.offers_aid("D3", "men")


def test_allocation_never_exceeds_cap():
    for division, gender in (("D1", "men"), ("D1", "women"),
                             ("D2", "men"), ("D2", "women"), ("D3", "men")):
        reset_caches()
        roster = build_roster(_prog("Cap U", 0.7, division, gender))
        summ = economy.budget_summary(roster, division, gender)
        assert summ["allocated"] <= summ["cap"] + 1e-9
        assert summ["remaining"] == round(max(0.0, summ["cap"] - summ["allocated"]), 4)
        # Every fraction is a legal offer size (or zero).
        for p in roster:
            assert p.scholarship == 0.0 or p.scholarship in economy.OFFER_FRACTIONS


def test_walk_on_count_preserved():
    """The fractional layer must NOT change the binary walk-on model the
    portal/league logic relies on: the top `funded` slots are the core, the rest
    walk-ons. Funded headcount is per-division (D1 men fully funds all 8)."""
    from app import scholarships
    from app.ncaa import roster_cap
    reset_caches()
    prog = _prog("Walk U", 0.7)
    roster = build_roster(prog)
    assert sum(p.walk_on for p in roster) == roster_cap(prog.division) - scholarships.slots(prog)
    # walk-ons never carry aid
    assert all(p.scholarship == 0.0 for p in roster if p.walk_on)


def test_d1_men_fully_funded_eight_full_rides():
    # Rule change: men are fully funded to match women, so D1 men commit the whole
    # 8.0 cap as eight full rides (NOT the old 4.5-equivalency partial split).
    reset_caches()
    roster = build_roster(_prog("Split U", 0.8, "D1", "men"))
    summ = economy.budget_summary(roster, "D1", "men")
    assert summ["allocated"] == 8.0
    assert summ["full_rides"] == 8 and summ["partials"] == 0


def test_d3_offers_no_athletic_aid_but_has_recruited_core():
    from app import scholarships
    reset_caches()
    prog = _prog("Liberal Arts C", 0.6, "D3", "men")
    roster = build_roster(prog)
    summ = economy.budget_summary(roster, "D3", "men")
    assert summ["cap"] == 0.0 and summ["allocated"] == 0.0
    assert not summ["offers_aid"]
    assert all(p.scholarship == 0.0 for p in roster)
    # the core are still recruited (not all walk-ons) — funded headcount comes
    # from app.scholarships (D3 funds fewer slots than D1/D2).
    assert sum(not p.walk_on for p in roster) == scholarships.slots(prog)


def test_allocation_deterministic():
    reset_caches()
    a = [p.scholarship for p in build_roster(_prog("Det U", 0.65))]
    reset_caches()
    b = [p.scholarship for p in build_roster(_prog("Det U", 0.65))]
    assert a == b


def test_fraction_labels():
    assert economy.fraction_label(1.0) == "Full"
    assert economy.fraction_label(0.5) == "½"
    assert economy.fraction_label(0.25) == "¼"
    assert economy.fraction_label(economy.SIXTH) == "⅙"
    assert economy.fraction_label(0.0) == "—"


def test_offered_fraction_scales_with_caliber_and_division():
    assert economy.offered_fraction("D1", "men", 0.9) == economy.FULL
    assert economy.offered_fraction("D1", "men", 0.6) == economy.HALF
    assert economy.offered_fraction("D1", "men", 0.1) == economy.SIXTH
    assert economy.offered_fraction("D3", "men", 0.9) == 0.0
