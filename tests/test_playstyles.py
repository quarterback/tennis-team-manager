"""Playing-style archetypes: real, distinct, format-weighted, and revolving."""
import random

from app import playstyles
from app.development import RICH_ATTRS


def test_every_archetype_attribute_is_real():
    """A typo here would be a silent no-op boost — the attribute simply wouldn't be
    on the player and nothing would error."""
    for name, attrs in playstyles.ARCHETYPES.items():
        unknown = [a for a in attrs if a not in RICH_ATTRS]
        assert not unknown, f"{name} names attributes that don't exist: {unknown}"


def test_archetypes_are_actually_distinct():
    """The old five-way style lumped most of the pro game into 'baseline'. No two
    archetypes may build the same set of attributes."""
    assert len(playstyles.ARCHETYPES) >= 8
    seen = {}
    for name, attrs in playstyles.ARCHETYPES.items():
        key = frozenset(attrs)
        assert key not in seen, f"{name} is a duplicate of {seen[key]}"
        seen[key] = name


def test_net_skills_are_weighted_up_for_the_pro_format():
    """The GTT tie is 3 of 9 lines in mixed doubles; a college dual is 1 point of 7.
    Net skills must therefore be worth more to a pro club than a college one."""
    gtt = playstyles.emphasis("net-poacher", fmt="gtt")
    college = playstyles.emphasis("net-poacher", fmt="college")
    assert gtt["poaching"] > college["poaching"]
    assert gtt["net_play"] > college["net_play"]
    assert gtt["doubles_chemistry"] > college["doubles_chemistry"]
    # a purely baseline archetype gets no thumb on the scale either way
    assert (playstyles.emphasis("topspin-grinder", fmt="gtt")
            == playstyles.emphasis("topspin-grinder", fmt="college"))


def test_baseline_archetypes_build_no_net_and_vice_versa():
    grind = playstyles.emphasis("topspin-grinder")
    poach = playstyles.emphasis("net-poacher")
    assert "net_play" not in grind and "poaching" not in grind
    assert "shot_tolerance" not in poach and "groundstroke_consistency" not in poach


def test_unknown_archetype_is_never_a_silent_uniform_buff():
    assert playstyles.emphasis("nonsense") == {}


def test_eras_revolve_and_come_back_around():
    first = playstyles.era_for(0)
    assert playstyles.era_for(playstyles.ERA_LENGTH - 1) == first     # holds
    assert playstyles.era_for(playstyles.ERA_LENGTH) != first         # turns over
    full = playstyles.ERA_LENGTH * len(playstyles.ERA_CYCLE)
    assert playstyles.era_for(full) == first                          # cycles
    # every era names real archetypes
    for era in playstyles.ERA_CYCLE:
        for a in era:
            assert a in playstyles.ARCHETYPES


def test_new_staffs_lean_to_the_era_but_leave_counter_trend_clubs():
    """A meta nobody bucks would be a monoculture; one nobody follows isn't a meta."""
    rng = random.Random(7)
    picks = [playstyles.pick_archetype(rng, 0) for _ in range(400)]
    in_era = sum(1 for p in picks if p in playstyles.era_for(0))
    assert 0.45 < in_era / len(picks) < 0.95, "era pull is all-or-nothing"
    assert len(set(picks)) >= 6, "the league collapsed to a monoculture"


def test_uncoached_club_falls_back_to_the_era():
    """Club identity now comes from its COACH (see gtt_seasonmode.club_style), so a
    club without one falls back to the prevailing era — and that fallback still
    turns over as the eras do."""
    import app.gtt_seasonmode as gs
    conn = gs._db()
    conn.execute("DELETE FROM gtt_coaches WHERE league_id=?", (-99,))
    conn.commit(); conn.close()
    across = {gs.club_style(-99, 3, y * playstyles.ERA_LENGTH)
              for y in range(len(playstyles.ERA_CYCLE))}
    assert len(across) > 1, "the era fallback never turns over"
