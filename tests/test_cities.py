"""Program home-city generation: deterministic, stable, real (city, state)."""
from generators.cities import program_city, program_location, _COLLEGE_TOWNS
from app.ncaa import load_division


def test_program_city_deterministic_and_stable():
    a = program_city("Texas")
    b = program_city("Texas")
    assert a == b
    assert a in _COLLEGE_TOWNS


def test_distinct_schools_can_differ():
    cities = {program_city(s) for s in
              ("Texas", "Stanford", "Ohio State", "Florida", "Duke", "Oregon")}
    assert len(cities) >= 3            # not collapsing everything to one town


def test_location_string_shape():
    loc = program_location("Stanford")
    assert "," in loc and loc.split(", ")[1].isupper() and len(loc.split(", ")[1]) == 2


def test_empty_school():
    assert program_city("") == ("", "")
    assert program_location("") == ""


def test_loaded_programs_carry_a_city():
    div = load_division("D1", "men")
    sample = div.programs[:20]
    assert all(p.city and p.state for p in sample)
    # men's and women's share the same campus city
    men = {p.school: p.location for p in load_division("D1", "men").programs}
    women = {p.school: p.location for p in load_division("D1", "women").programs}
    shared = set(men) & set(women)
    assert shared and all(men[s] == women[s] for s in shared)
