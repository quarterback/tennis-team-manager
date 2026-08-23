"""A program that stops sponsoring keeps its page.

`load_schools` filters on the sponsorship flag — right for every current-season
surface (the directory, the leagues, the ladder) and it also meant the program page
and every player page 404'd the moment the flag went off. The archive was untouched,
so the school's state title went on standing on the title board and the champions
grid with a dead link under it: the trophies stayed and the pages that explain them
died. Same fault a rename used to cause, same answer — resolve it on READ.
"""
import pytest

from app import jhsaa as jh


@pytest.fixture
def dropped(monkeypatch):
    """One real school, with its girls' sponsorship switched off in the rows the
    module reads — the flag is the only thing that changes when a school drops a
    sport."""
    rows = [dict(r) for r in jh._rows()]
    target = next(r for r in rows if r.get("girls"))
    target["girls"] = False
    # Clear FIRST, then install the doctored rows: `reset_schools` nulls the module
    # global that several readers take directly, so patching before it wipes the
    # patch and leaves them loading the real file mid-test.
    jh.reset_schools()
    monkeypatch.setattr(jh, "_rows", lambda: rows)
    monkeypatch.setattr(jh, "_schools_cache", rows, raising=False)
    yield target["name"]
    jh.reset_schools()


def test_they_drop_off_the_current_season_surfaces(dropped):
    """The filter still does its job: they field no team, so they are in no league,
    no ladder and no directory."""
    assert not any(s.name == dropped for s in jh.load_schools("girls"))
    assert not jh.sponsors_sport(dropped, "girls")


def test_but_the_program_still_resolves(dropped):
    """‼️ THE FALLBACK. Everything the page needs — town, county, class, mascot,
    crest, and the roster identity that regenerates every player who ever played
    there — comes off the data row, which is still right there."""
    sc = jh.former_school(dropped, "girls")
    assert sc is not None and sc.name == dropped
    assert sc.city and sc.classification and sc.mascot


def test_the_other_gender_is_untouched(dropped):
    """Sponsorship is per SPORT: a school that drops the girls' team may still field
    a boys' one, and `former_school` must not report the live program as former."""
    if any(s.name == dropped for s in jh.load_schools("boys")):
        assert jh.sponsors_sport(dropped, "boys")
        assert jh.former_school(dropped, "boys") is not None


def test_a_name_no_row_carries_is_still_a_real_404(dropped):
    """The distinction that keeps the fallback honest: a school that exists and
    fields no team is a former program; a name nothing carries does not exist."""
    assert jh.former_school("Nowhere Consolidated", "girls") is None


def test_a_current_program_is_never_reported_as_former():
    live = jh.load_schools("girls")[0]
    assert jh.sponsors_sport(live.name, "girls")
    assert jh.former_school(live.name, "girls").name == live.name
