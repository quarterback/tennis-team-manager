"""The Non-Public team championships (10B/11B), end to end over a REAL season.

Owner rule 2026-09: private programs stay in the ordinary association for the
league season, district honours, TOSS, All-State, All-District, All-Region, the
individual flights and the JV season — and leave the public bracket when the
TEAM championship road begins, playing the same full ladder onto a 24-team State
in one of two road classes: 10B (enrollment >= `NONPUBLIC_CUT`, or a named
play-up) and 11B (below it). The TOC takes all fourteen champions plus the two
TOC Qualifier winners (9A v 8A and 10B v 11B State runners-up), a byeless sixteen.

`tests/conftest.py` keeps the split OFF for every other suite (the 16-team
pilot's idiom); this file opts in. The association is the TOC test's scaled
public subset PLUS EVERY private sponsor, because a Non-Public class is the one
class a small world cannot scale — its road needs the real 48-per-gender floor.
"""
import sqlite3

import pytest

from app import jhsaa as jh
from app import world as wd
from app.web.server import create_app


@pytest.fixture(scope="module")
def archived(tmp_path_factory):
    db = str(tmp_path_factory.mktemp("jhsaa") / "nonpublic.db")
    real_load, real_db, real_ready = jh.load_schools, wd.WORLD_DB, wd._schema_ready_for
    real_era = jh.nonpublic_era

    def small(gender):
        """The TOC fixture's cut — leagues until the PUBLIC pool clears the protected
        tier — plus every private sponsor in the gender."""
        allsch = real_load(gender)
        out = [s for s in allsch if s.private]
        for grp in jh.GROUPS:
            names = sorted({s.district for s in allsch if s.group == grp})
            keep, pool = set(), []
            for name in names:
                keep.add(name)
                pool = [s for s in allsch if s.group == grp and s.district in keep
                        and not s.private]
                if len(pool) > jh.PROTECTED + 8:
                    break
            out += pool
        return out

    real_primed, real_prime = wd.is_primed, wd.prime
    real_fields = dict(jh.STATE_FIELD)
    for grp, real in real_fields.items():
        jh.STATE_FIELD[grp] = {24: 24, 32: 16, 40: 20}[real]
    jh.load_schools = small
    jh.nonpublic_era = lambda: 0                    # the split, from season one
    jh._season_cache.clear()
    wd.WORLD_DB = db
    wd._schema_ready_for = None
    try:
        w = wd.get_or_create(wd.DEFAULT_SEED)
        wd.run_jhsaa(wd.DEFAULT_SEED, w)
        wd.is_primed = lambda *a, **k: True
        wd.prime = lambda *a, **k: None
        yield {"db": db, "world": w, "client": create_app().test_client(),
               "arc": wd.get_jhsaa(w["id"], w["year"], "girls"),
               "schools": {s.name: s for s in small("girls")}}
    finally:
        jh.load_schools = real_load
        jh.nonpublic_era = real_era
        jh.STATE_FIELD.clear()
        jh.STATE_FIELD.update(real_fields)
        jh._season_cache.clear()
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready
        wd.is_primed, wd.prime = real_primed, real_prime


def ru_of(arc, name):
    """The class whose State final `name` lost."""
    for g in jh.ROAD_GROUPS:
        if jh.state_runner_up(arc["brackets"].get(g)) == name:
            return g
    raise AssertionError(name)


def _stage_names(arc, group):
    """Every program that appears in ANY road/State key of `group`."""
    out = set()
    for key in ("sectionals", "wards", "prestate", "super_regional", "semi_state",
                "divisional", "semi_conference", "conference", "special_challenger",
                "state_special", "brackets"):
        d = (arc.get(key) or {}).get(group) or {}
        out |= set(d.get("field") or ())
        for games in d.get("rounds") or ():
            for gm in games:
                out |= {gm.get("home"), gm.get("away")}
    out |= set((arc.get("protected") or {}).get(group) or ())
    out.discard(None)
    return out


def test_the_road_map_names_every_private_and_nobody_else(archived):
    arc, schools = archived["arc"], archived["schools"]
    road = arc["road"]
    privates = {n for n, s in schools.items() if s.private}
    assert set(road) == privates
    assert set(road.values()) == set(jh.NONPUBLIC_GROUPS)


def test_privates_leave_the_public_road_and_play_exactly_one_nonpublic_one(archived):
    arc, schools = archived["arc"], archived["schools"]
    for g in jh.GROUPS:
        assert not {n for n in _stage_names(arc, g) if schools[n].private}, g
    seen = {}
    for g in jh.NONPUBLIC_GROUPS:
        names = _stage_names(arc, g)
        assert names and all(schools[n].private for n in names), g
        for n in names:
            assert n not in seen, (n, seen.get(n), g)
            seen[n] = g
    # ...and every private in the world is on one of the two roads.
    assert set(seen) == {n for n, s in schools.items() if s.private}


def test_the_bands_are_the_cut_plus_the_named_playups(archived):
    arc, schools = archived["arc"], archived["schools"]
    for name, g in arc["road"].items():
        s = schools[name]
        if name in jh.NONPUBLIC_PLAYUP:
            assert g == "10B", name
        elif s.enrollment >= jh.NONPUBLIC_CUT:
            assert g == "10B", (name, s.enrollment)
        else:
            assert g == "11B", (name, s.enrollment)
    assert {"Condotti Vanguard Academy", "Romero-Finniski"} <= {
        n for n, g in arc["road"].items() if g == "10B"}


def test_a_full_ladder_onto_a_24_team_state_and_a_16_team_toc(archived):
    arc = archived["arc"]
    for g in jh.NONPUBLIC_GROUPS:
        br = arc["brackets"][g]
        assert len(br["field"]) == 24, (g, len(br["field"]))
        assert br["champion"] in br["field"]
        # Every rung the public classes play, played here too.
        for key in ("sectionals", "wards", "prestate", "super_regional", "semi_state"):
            assert (arc[key][g] or {}).get("rounds"), (g, key)
        assert arc["committee"][g] is None                  # no at-large committee
    toc = arc["toc"]
    assert len(jh.ROAD_GROUPS) == 14
    assert {arc["brackets"][g]["champion"] for g in jh.NONPUBLIC_GROUPS} <= set(toc["field"])
    # THE TOC QUALIFIER (JHSAA rule 2026-09): the 9A/8A and 10B/11B State runners-up
    # play one dual each for the last two seats, so the TOC is a byeless sixteen.
    q = toc["qualifier"]
    games = q["rounds"][0]
    assert len(games) == 2 and q["round_names"] == [jh.TOC_QUALIFIER_NAME]
    sides = {gm["home"] for gm in games} | {gm["away"] for gm in games}
    assert sides == {jh.state_runner_up(arc["brackets"][g]) for g in ("9A", "8A", "10B", "11B")}
    assert len(toc["field"]) == 16 and len(toc["rounds"][0]) == 8
    assert all(gm["home"] and gm["away"] for gm in toc["rounds"][0])   # no byes
    assert set(q["survivors"]) <= set(toc["field"])
    losers = sides - set(q["survivors"])
    assert not losers & set(toc["field"])
    # Owner rule: a qualifier loser is treated like the other TOC entrants — a TOC
    # appearance with the finish "TOC Qualifier", ranked below everyone in the draw,
    # beside its State finalist honour.
    for name in losers:
        r = wd.jhsaa_toc_result(toc, name)
        assert r["made_toc"] and r["toc_qualifier"] and r["toc_finish"] == "TOC Qualifier"
        assert r["toc_place"] == 17 and r["toc_seed"] == 0
        assert wd.jhsaa_state_result(arc["brackets"][ru_of(arc, name)], name)["place"] == 2
    for name in q["survivors"]:
        r = wd.jhsaa_toc_result(toc, name)
        assert r["made_toc"] and r["toc_qualifier"] and r["toc_finish"] != "TOC Qualifier"


def test_the_road_shape_is_the_road_class_not_the_league_class(archived):
    """A 10B dual is 4S/5D (nine flights) and an 11B dual 1S/4D (five) whatever the
    two sides' league classes; the TOC keeps everyone at 1S/4D."""
    arc, w = archived["arc"], archived["world"]
    conn = sqlite3.connect(archived["db"])
    road = arc["road"]
    counts = {}
    for school, g in road.items():
        for phase, lines in conn.execute(
                "SELECT phase, lines FROM world_jhsaa_dual WHERE world_id=? AND year=?"
                " AND gender='girls' AND school=? AND home=1 AND COALESCE(level,'v')='v'",
                (w["id"], w["year"], school)):
            if phase in jh.POSTSEASON and phase not in jh.TOC_PHASES:
                counts.setdefault(g, set()).add(len(wd.unpack_lines(lines) or ()))
            elif phase in jh.TOC_PHASES:
                counts.setdefault("toc", set()).add(len(wd.unpack_lines(lines) or ()))
    conn.close()
    assert counts.get("10B") == {9}, counts
    assert counts.get("11B") == {5}, counts
    assert counts.get("toc", {5}) == {5}, counts


def test_a_league_title_won_by_a_private_protects_the_best_public(archived):
    arc = archived["arc"]
    road = arc["road"]
    checked = 0
    for g in jh.GROUPS:
        protected = set(arc["protected"][g])
        for rows in (arc["standings"][g] or {}).values():
            if not rows or rows[0]["school"] not in road:
                continue
            best_pub = next((r["school"] for r in rows if r["school"] not in road), None)
            if best_pub:
                assert best_pub in protected, (g, rows[0]["school"], best_pub)
                checked += 1
    assert checked, "the fixture has no league a private won — widen it"


def test_the_ledger_row_keeps_the_league_class_and_reads_the_road_class(archived):
    arc, w = archived["arc"], archived["world"]
    name, g = next(iter(arc["road"].items()))
    row = wd._season_row(arc, w["year"], name, [])
    assert row["group"] in jh.GROUPS            # standings, ranking, awards: the league
    assert row["road_group"] == g               # brackets: the road
    assert row["state_finish"]                  # every private played a road dual
    assert wd.jh_road_group(arc, name, row["group"]) == g
    # A public program resolves to its own class.
    pub = next(n for n in arc["standings"]["9A"][next(iter(arc["standings"]["9A"]))]
               if n["school"] not in arc["road"])["school"]
    assert wd.jh_road_group(arc, pub, "9A") == "9A"


def test_the_bracket_page_renders_the_nonpublic_classes(archived):
    c = archived["client"]
    for g in jh.NONPUBLIC_GROUPS:
        r = c.get(f"/jhsaa/bracket?g=girls&group={g}")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert archived["arc"]["brackets"][g]["champion"] in html
    board = wd.jhsaa_title_board(archived["world"]["id"], "girls")
    private_rows = [r for r in board["rows"] if r["school"] in archived["arc"]["road"]]
    assert sum(r["state_apps"] for r in private_rows) == 48


def test_before_the_era_nothing_moves():
    s = jh.School(name="X", city="c", county="k", area="a", classification="7A",
                  group="7A", enrollment=1600, private=True, mascot="m", colors=[],
                  district="d", gender="girls")
    real = jh.nonpublic_era
    jh.nonpublic_era = lambda: 2100
    try:
        assert jh.road_group(s, 2099) == "7A"
        assert jh.road_group(s, 2100) == "10B"
        assert jh.road_group(s, None) == "7A"
        s.enrollment = 300
        assert jh.road_group(s, 2100) == "11B"
        s.private = False
        assert jh.road_group(s, 2100) == "7A"
    finally:
        jh.nonpublic_era = real
    assert "jhsaa_nonpublic_era" in jh.ERA_SETTINGS
