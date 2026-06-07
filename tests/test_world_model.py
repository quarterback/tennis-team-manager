"""World-model port: nation talent, hometowns/flags, dual citizens, and the
recruiting (offers / dreamsheet / timeline) subsystem."""
import random

from generators import (nation_talent, roll_hometown, roll_birthday,
                        roll_secondary_country, country_name, country_abbrev,
                        flag_emoji, region_preset, make_name_picker)
from app.juniors import generate_class, national_rankings
from app.recruiting import build_recruiting, School


# --- nation talent ---------------------------------------------------------
def test_nation_talent_neutral_default():
    # An unlisted nation is neutral 50/50 -> no talent shift, but still a
    # mid-band elite chance so gems can emerge anywhere in the world.
    assert nation_talent.ratings("ZZ") == (50, 50)
    assert nation_talent.talent_shift("ZZ") == 0
    p = nation_talent.elite_probability("ZZ")
    assert nation_talent.ELITE_MIN_P < p < nation_talent.ELITE_MAX_P


def test_nation_talent_majors_lift_and_spike():
    assert nation_talent.talent_shift("ES") > 0           # Spain lifts
    assert nation_talent.talent_shift("US") > 0
    # Elite probability is bounded and ordered by investment.
    for cc in ("ES", "US", "FR"):
        p = nation_talent.elite_probability(cc)
        assert nation_talent.ELITE_MIN_P <= p <= nation_talent.ELITE_MAX_P
    assert nation_talent.elite_probability("ES") > nation_talent.elite_probability("ZZ")


# --- flavor / display ------------------------------------------------------
def test_hometown_and_country_display():
    rng = random.Random(3)
    assert roll_hometown("ES", rng)                       # Spain has a city pool
    assert roll_hometown("ZZ", rng) == ""                 # unknown -> empty
    assert country_name("ES") == "Spain"
    assert country_abbrev("ES") == "ESP"
    assert flag_emoji("ES") and len(flag_emoji("ES")) == 2  # two regional-indicator chars
    assert flag_emoji("") == "" and flag_emoji("Z") == ""


def test_secondary_country_rate_at_least_3pct():
    rng = random.Random(11)
    n = 4000
    dual = sum(1 for _ in range(n) if roll_secondary_country("ES", rng))
    assert dual / n >= 0.03                               # >=3% dual citizens
    # never returns the player's own nation
    rng2 = random.Random(5)
    assert all(roll_secondary_country("US", rng2) != "US" for _ in range(500))


# --- recruiting class wiring ----------------------------------------------
def test_every_recruit_has_country_and_hometown():
    k = generate_class(random.Random(7), n=300, grad_year=2026, gender="male")
    for p in k.recruits:
        assert p.country
        assert "," in p.hometown                          # "City, REGION"


def test_non_major_markets_emerge():
    # >=10% of the world is reserved outside the majors; over a class that
    # surfaces a healthy spread of non-major-market players of various skills.
    k = generate_class(random.Random(2), n=400, grad_year=2026, gender="male")
    majors = {"US", "ES", "FR", "IT", "DE", "RU", "GB", "AU", "AR", "CA",
              "CZ", "CH", "JP", "BE", "NL", "AT", "PL", "SE", "HR", "GR"}
    non_major = [p for p in k.recruits if p.country not in majors]
    assert len(non_major) >= 10
    # they aren't all bottom-feeders: spread of star ratings present
    assert len({p.recruit_stars for p in non_major}) >= 2


# --- recruiting subsystem (offers / dreamsheet / timeline) -----------------
def _schools():
    return [School(name=f"School{i}", strength=1.0 - i * 0.04, tier="P5",
                   abbr=f"S{i}", color="#333") for i in range(24)]


def test_build_recruiting_shapes_and_determinism():
    k = generate_class(random.Random(4), n=120, grad_year=2026, gender="male")
    national_rankings(k)
    top = sorted(k.recruits, key=lambda q: q.recruit_stars, reverse=True)[0]
    a = build_recruiting(top, _schools(), seed_salt="2026")
    b = build_recruiting(top, _schools(), seed_salt="2026")
    assert [o.school for o in a.offers] == [o.school for o in b.offers]   # deterministic
    assert a.n_offers == len(a.offers) >= 1
    assert a.predicted_school == a.offers[0].school
    assert 0 <= a.predicted_pct <= 100
    assert any(o.status == "Finalist" for o in a.offers)
    assert a.dreamsheet and a.timeline
    # higher-rated recruits draw deeper boards than fringe recruits
    fringe = min(k.recruits, key=lambda q: q.recruit_stars)
    assert a.n_offers >= build_recruiting(fringe, _schools(), seed_salt="2026").n_offers


def test_recruiting_handles_no_schools():
    k = generate_class(random.Random(9), n=20, grad_year=2026, gender="male")
    prof = build_recruiting(k.recruits[0], [])
    assert prof.n_offers == 0 and prof.offers == [] and prof.predicted_school == ""


def test_tennis_global_preset_loads():
    w = region_preset("tennis_global")
    assert w and "us" in w
    # picker yields names + ISO country codes
    name_fn = make_name_picker(random.Random(1), gender="male", region_weights=w)
    full, cc = name_fn()
    assert full and isinstance(cc, str)
