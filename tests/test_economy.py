"""Scholarship-equivalency economy: caps, fractional allocation, ledger."""
from app import economy
from app.ncaa import Program, build_roster, reset_caches, ROSTER_SIZE, SCHOLARSHIP_SLOTS


def _prog(school, strength, division="D1", gender="men"):
    return Program(school=school, conf="ACC", conf_abbr="ACC", division=division,
                   gender=gender, abbr="XX", color="#000", strength=strength)


def test_caps_are_real_ncaa_numbers():
    assert economy.cap_for("D1", "men") == 4.5
    assert economy.cap_for("D1", "women") == 8.0
    assert economy.cap_for("D2", "men") == 4.5
    assert economy.cap_for("D2", "women") == 6.0
    assert economy.cap_for("D3", "men") == 0.0
    assert economy.cap_for("D3", "women") == 0.0


def test_cap_normalizes_loose_inputs():
    assert economy.cap_for("d1", "MEN") == 4.5
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
    portal/league logic relies on: top SCHOLARSHIP_SLOTS are the core."""
    reset_caches()
    roster = build_roster(_prog("Walk U", 0.7))
    assert sum(p.walk_on for p in roster) == ROSTER_SIZE - SCHOLARSHIP_SLOTS
    # walk-ons never carry aid
    assert all(p.scholarship == 0.0 for p in roster if p.walk_on)


def test_d1_men_split_is_partials_not_eight_full_rides():
    reset_caches()
    roster = build_roster(_prog("Split U", 0.8, "D1", "men"))
    summ = economy.budget_summary(roster, "D1", "men")
    # 4.5 cap → 4 full + 1 half, exactly the cap committed.
    assert summ["allocated"] == 4.5
    assert summ["full_rides"] == 4 and summ["partials"] == 1


def test_d3_offers_no_athletic_aid_but_has_recruited_core():
    reset_caches()
    roster = build_roster(_prog("Liberal Arts C", 0.6, "D3", "men"))
    summ = economy.budget_summary(roster, "D3", "men")
    assert summ["cap"] == 0.0 and summ["allocated"] == 0.0
    assert not summ["offers_aid"]
    assert all(p.scholarship == 0.0 for p in roster)
    # the core are still recruited (not all walk-ons)
    assert sum(not p.walk_on for p in roster) == SCHOLARSHIP_SLOTS


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
