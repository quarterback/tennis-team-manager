import app.ncaa as ncaa
import app.overrides as ov
from app.web.server import create_app


def test_prestige_override_applies_and_clears():
    create_app()
    div = ncaa.load_division("D3", "men")
    school = div.programs[0].school
    default = div.by_school(school).prestige

    ov.set_prestige(school, 0.95)
    ncaa.reset_caches()
    assert abs(ncaa.load_division("D3", "men").by_school(school).prestige - 0.95) < 1e-6

    ov.clear_prestige(school)
    ncaa.reset_caches()
    assert abs(ncaa.load_division("D3", "men").by_school(school).prestige - default) < 1e-6


def test_prestige_override_feeds_recruiting_appeal():
    from app.recruiting import schools_from_programs
    create_app()
    school = ncaa.load_division("D2", "men").programs[0].school
    ov.clear_prestige(school)
    ncaa.reset_caches()
    ov.set_prestige(school, 0.99)
    ncaa.reset_caches()
    progs = ncaa.load_division("D2", "men").programs
    sc = next(s for s in schools_from_programs(progs) if s.name == school)
    assert abs(sc.prestige - 0.99) < 1e-6
    ov.clear_prestige(school)
    ncaa.reset_caches()
