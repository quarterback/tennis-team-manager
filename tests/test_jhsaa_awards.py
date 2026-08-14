"""Postseason awards are RÉSUMÉ selections (owner SOP 2027-08).

The old model sorted on (wins, win%, OVR) and took six for All-State and six per
district. These pin the SOP's shape and its two load-bearing rules: Honorable
Mention is a THRESHOLD rather than a team, and the two-per-school cap applies to
HM and to nothing else.
"""
import pytest

from app import jhsaa as jh
from app import jhsaa_awards as aw


@pytest.fixture(scope="module")
def season():
    """Two districts per classification — the shipped path, a tenth the size."""
    real = jh.load_schools

    def small(gender):
        out = []
        for grp in jh.GROUPS:
            keep = sorted({s.district for s in real(gender) if s.group == grp})[:2]
            out += [s for s in real(gender) if s.group == grp and s.district in keep]
        return out

    jh.load_schools = small
    jh._season_cache.clear()
    try:
        yield jh.run_season("boys", 2027, seed=0, salt="awards")
    finally:
        jh.load_schools = real
        jh._season_cache.clear()


def test_all_state_and_all_district_teams_are_the_same_size(season):
    """Owner: an All-State team is the size of an All-District team."""
    for g in jh.GROUPS:
        a = season["awards"][g]
        for tier in a["teams"]:
            s = [r for r in tier["players"] if r["kind"] == "singles"]
            d = [r for r in tier["players"] if r["kind"] == "doubles"]
            assert (len(s), len(d)) == (aw.TEAM_SINGLES, aw.TEAM_DOUBLES), (g, tier["name"])
        for dname, rows in a["all_district"].items():
            s = [r for r in rows if r["kind"] == "singles"]
            assert len(s) <= aw.TEAM_SINGLES and len(rows) - len(s) <= aw.TEAM_DOUBLES


def test_7a_gets_a_fourth_team_and_everyone_else_three(season):
    assert [t["name"] for t in season["awards"]["7A"]["teams"]][:4] == \
        ["First Team", "Second Team", "Third Team", "Fourth Team"]
    for g in jh.GROUPS:
        if g != "7A":
            assert len(season["awards"][g]["teams"]) == aw.AS_TIERS_DEFAULT, g


def test_honorable_mention_is_a_threshold_not_a_fixed_size(season):
    """‼️ The size is an OUTPUT. If every classification honours the same number,
    a slot count has crept back in — which is exactly what a too-loose runaway
    guard did on the first attempt (a flat 27 everywhere)."""
    sizes = [len(season["awards"][g]["honorable_mention"]) for g in jh.GROUPS]
    assert len(set(sizes)) > 1, sizes
    guard = int((aw.TEAM_SINGLES + aw.TEAM_DOUBLES) * aw.HM_MAX_MULT)
    assert max(sizes) < guard, (sizes, guard)     # the THRESHOLD must be binding


def test_honorable_mention_caps_a_school_at_two(season):
    from collections import Counter
    for g in jh.GROUPS:
        c = Counter(r["school"] for r in season["awards"][g]["honorable_mention"])
        assert not c or max(c.values()) <= aw.HM_PER_SCHOOL, (g, c.most_common(3))


def test_the_school_cap_applies_to_nothing_but_honorable_mention(season):
    """A school may take as many numbered-team places as its résumés earn."""
    from collections import Counter
    stacked = 0
    for g in jh.GROUPS:
        c = Counter(r["school"] for t in season["awards"][g]["teams"]
                    for r in t["players"])
        stacked = max(stacked, max(c.values()) if c else 0)
    assert stacked > aw.HM_PER_SCHOOL, stacked


def test_awards_are_not_an_ability_leaderboard(season):
    """The whole point of the SOP: a résumé, not a rating. No award row carries an
    ability figure, and the selections are not simply the highest-OVR players."""
    a = season["awards"]["7A"]
    rows = [r for t in a["teams"] for r in t["players"]]
    assert rows and not any("ovr" in r or "str" in r for r in rows)
    teams = [t for t in season["teams"].values() if t.school.group == "7A"]
    best_ovr = sorted((p for t in teams for p in t.roster),
                      key=lambda p: -p.current_overall())[:len(rows)]
    picked = {r["pid"] for r in rows}
    assert {p.pid for p in best_ovr} != picked


def test_every_district_gets_a_player_of_the_year(season):
    for g in jh.GROUPS:
        a = season["awards"][g]
        assert set(a["district_poy"]) == set(a["all_district"]), g
        assert a["poy"] is not None


def test_award_rows_name_the_PLAYER_not_the_school(season):
    """‼️ The awards shipped rendering a list of SCHOOLS. `_jh_deco` describes a
    school and its dict is keyed `name`, so splatting it over an award row
    overwrote every selection's player name — All-State read "Beacon Hill",
    "Belmonte West", "Serrano". The selections were individuals the whole time;
    only the display was wrong, which is the worst way for this to break because
    the data underneath looks fine."""
    schools = {s.name for s in jh.load_schools("boys")}
    for g in jh.GROUPS:
        a = season["awards"][g]
        rows = ([r for t in a["teams"] for r in t["players"]]
                + a["honorable_mention"]
                + [r for rs in a["all_district"].values() for r in rs]
                + [a["poy"]] + list(a["district_poy"].values()))
        for r in rows:
            assert r["name"] not in schools, (g, r["name"], r["school"])
            assert r["name"] != r["school"], (g, r["name"])
