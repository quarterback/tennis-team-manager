"""The postseason, end to end — over a REAL archived season.

Three decoupled mechanisms (owner spec):

  1. Sectionals — broad access and field reduction. Every non-protected team
     enters; byes/play-ins as needed; the only fixed requirement is the output,
     exactly the Ward field.
  2. The pre-state ladder — fixed shape for every classification, both genders:
     Wards 32→16, Regionals 32→16 (Ward champions + protected), Zonals 16→8.
     Protected entrants (district champions first, then best cutoff TOSS) enter
     at Regionals. Zonal champions qualify for State automatically.
  3. Wild cards — after Zonals, TOSS is recomputed over all pre-state results;
     the top non-champions join the Zonal champions in a fresh 16-team State
     draw (R16 → QF → SF → Final).

`ladder_scale` shrinks every number together for pools too small for the full
shape — the two-district fixture here exercises exactly that; the full-size
arithmetic is asserted proportionally, not as absolute 16/32s.

Fixture pattern shared with `test_jhsaa_toc.py` (two districts per
classification, so a run stays a few seconds).
"""
import sqlite3

import pytest

from app import jhsaa as jh
from app import world as wd


@pytest.fixture(scope="module")
def archived(tmp_path_factory):
    """A world with one JHSAA season archived, on a database of its own."""
    db = str(tmp_path_factory.mktemp("jhsaa_ladder") / "ladder.db")
    real_load, real_db, real_ready = jh.load_schools, wd.WORLD_DB, wd._schema_ready_for

    def small(gender):
        """Two districts per classification — a real association, a tenth the size."""
        out = []
        for grp in jh.GROUPS:
            keep = sorted({s.district for s in real_load(gender) if s.group == grp})[:2]
            out += [s for s in real_load(gender)
                    if s.group == grp and s.district in keep]
        return out

    real_primed, real_prime = wd.is_primed, wd.prime
    jh.load_schools = small
    jh._season_cache.clear()
    wd.WORLD_DB = db
    wd._schema_ready_for = None
    try:
        w = wd.get_or_create(wd.DEFAULT_SEED)
        wd.run_jhsaa(wd.DEFAULT_SEED, w)
        wd.is_primed = lambda *a, **k: True
        wd.prime = lambda *a, **k: None
        yield {"db": db, "world": w,
               "arc": wd.get_jhsaa(w["id"], w["year"], "girls"),
               "arc_boys": wd.get_jhsaa(w["id"], w["year"], "boys")}
    finally:
        jh.load_schools = real_load
        jh._season_cache.clear()
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready
        wd.is_primed, wd.prime = real_primed, real_prime


def _stages(archived, g):
    arc = archived["arc"]
    return (arc["sectionals"][g], arc["wards"][g], arc["prestate"][g],
            arc["brackets"][g], arc["protected"][g], arc["wildcards"][g])


# --- the fixed shape, per classification -------------------------------------------

def test_the_ladder_shape_is_fixed_and_proportional(archived):
    """Sectionals feeds Wards exactly; Wards halves; Regionals = Ward champions +
    protected and halves twice down to the Zonal champions."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, wc = _stages(archived, g)
        k = jh.ladder_scale(g)
        assert len(ward["field"]) == jh.WARD_FIELD // k
        assert len(sec["survivors"]) == len(ward["field"])
        assert len(ward["survivors"]) == len(ward["field"]) // 2
        assert len(pre["field"]) == len(ward["survivors"]) + len(protected)
        assert len(pre["field"]) == jh.WARD_FIELD // k          # Regionals re-fills to 32
        assert len(pre["survivors"]) == len(pre["field"]) // 4  # two rounds: 32 -> 8
        assert set(pre["field"]) == set(ward["survivors"]) | set(protected)


def test_the_state_field_is_zonal_champions_plus_wildcards(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, wc = _stages(archived, g)
        k = jh.ladder_scale(g)
        zonal_champs = set(pre["survivors"])
        assert len(wc) == jh.WILDCARDS // k
        assert zonal_champs.isdisjoint(wc)
        assert set(state["field"]) == zonal_champs | set(wc)


def test_boys_and_girls_play_the_same_format(archived):
    for g in jh.GROUPS:
        for key in ("brackets", "wards", "prestate"):
            assert len(archived["arc"][key][g]["field"]) \
                == len(archived["arc_boys"][key][g]["field"]), (key, g)


# --- protection: district champions first, enter at Regionals, nothing more --------

def test_protected_is_district_champions_first_then_toss(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, wc = _stages(archived, g)
        champs = {rows[0]["school"]
                  for rows in archived["arc"]["standings"][g].values() if rows}
        assert champs <= set(protected)


def test_protected_teams_skip_sectionals_and_wards_only(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, wc = _stages(archived, g)
        assert set(protected).isdisjoint(sec["field"])
        assert set(protected).isdisjoint(ward["field"])
        assert set(protected) <= set(pre["field"])   # they DO play Regionals


# --- byes only in Sectionals --------------------------------------------------------

def test_wards_regionals_zonals_and_state_are_byes_free(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, wc = _stages(archived, g)
        for br in (ward, pre, state):
            alive = len(br["field"])
            for games in br["rounds"]:
                assert len(games) * 2 == alive, (g, alive, len(games))
                alive -= len(games)


# --- stage names ride the archive ---------------------------------------------------

def test_prestate_dicts_carry_their_own_round_names(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, wc = _stages(archived, g)
        assert ward["round_names"] == ["Wards"]
        assert pre["round_names"] == ["Regionals", "Zonals"]
        # A multi-round Sectionals opens with Areas; the last round is always the
        # one named Sectionals (owner rule).
        names = sec["round_names"]
        if names:
            assert names[-1] == "Sectionals"
            assert all(n == "Areas" for n in names[:-1])
        rounds = wd.jhsaa_state_rounds(pre)
        assert [r["name"] for r in rounds] == ["Regionals", "Zonals"]


def test_every_prestate_dual_is_a_numbered_unit(archived):
    """Owner rule: every pre-state dual is a numbered unit within its class and
    gender — Area 1, Section 1, Ward 1, Regional 1, restarting at 1 per stage per
    classification; Zonals letter A, B, C…"""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, wc = _stages(archived, g)
        for i, games in enumerate(sec["rounds"]):
            prefix = "Area" if i < len(sec["rounds"]) - 1 else "Section"
            assert [gm["unit"] for gm in games] \
                == [f"{prefix} {j + 1}" for j in range(len(games))]
        for games in ward["rounds"]:
            assert [gm["unit"] for gm in games] \
                == [f"Ward {j + 1}" for j in range(len(games))]
        assert [gm["unit"] for gm in pre["rounds"][0]] \
            == [f"Regional {j + 1}" for j in range(len(pre["rounds"][0]))]
        assert [gm["unit"] for gm in pre["rounds"][1]] \
            == [f"Zonal {chr(65 + j)}" for j in range(len(pre["rounds"][1]))]


# --- postseason results across every stage ------------------------------------------

def test_finishes_name_the_stage_a_run_ended_at(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, wc = _stages(archived, g)
        grp = {"sectional": sec, "ward": ward, "prestate": pre,
               "state": state, "wildcards": wc}
        sec_out = set(sec["field"]) - set(sec["survivors"])
        for name in sec_out:
            # A multi-round Sectionals opens with AREAS (owner rule): the finish
            # names the round the run actually ended in, so an Area-round exit
            # says "Areas", never the final round's "Sectionals".
            last = max(i for i, games in enumerate(sec["rounds"])
                       if any(name in (gm["home"], gm["away"]) for gm in games))
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == (sec["round_names"][last], False)
        ward_out = set(ward["field"]) - set(ward["survivors"])
        for name in ward_out:
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == ("Wards", False)
        for name in set(pre["field"]) - set(pre["survivors"]) - set(state["field"]):
            r = wd.jhsaa_postseason_result(grp, name)
            assert r["finish"] in ("Regionals", "Zonals")
            assert not r["made_state"]
        for name in wc:
            r = wd.jhsaa_postseason_result(grp, name)
            assert r["made_state"] and r["wildcard"]
        champ = wd.jhsaa_postseason_result(grp, state["champion"])
        assert champ["champion"] and champ["finish"] == "Champion"


# --- the archive keeps the stages apart ---------------------------------------------

def test_each_stage_is_archived_under_its_own_phase(archived):
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row
    for phase, key in (("ward", "wards"), ("sectional", "sectionals")):
        rows = conn.execute("SELECT COUNT(*) c FROM world_jhsaa_dual"
                            " WHERE phase=? AND gender='girls'", (phase,)).fetchone()
        played = sum(len(r) for d in archived["arc"][key].values()
                     for r in d["rounds"])
        assert rows["c"] == 2 * played, phase       # a dual sits on both sides' cards
    for phase, rd in (("regional", 0), ("zonal", 1)):
        rows = conn.execute("SELECT COUNT(*) c FROM world_jhsaa_dual"
                            " WHERE phase=? AND gender='girls'", (phase,)).fetchone()
        played = sum(len(d["rounds"][rd]) for d in archived["arc"]["prestate"].values()
                     if len(d["rounds"]) > rd)
        assert rows["c"] == 2 * played, phase
    conn.close()


def test_prestate_stages_stay_out_of_the_cutoff_toss(archived):
    season = jh.run_season("girls", archived["arc"]["season_year"], seed=0,
                           salt=wd.active_salt(wd.DEFAULT_SEED))
    teams = list(season["teams"].values())
    cutoff = jh.rating_duals(teams)
    n_regular = sum(1 for t in teams for d in t.schedule
                    if d["home"] and d["phase"] not in jh.POSTSEASON)
    assert len(cutoff) == n_regular


def test_state_seeds_are_pure_post_zonal_toss(archived):
    """Seeds 1-16 are post-Zonal TOSS order across the WHOLE field — a Zonal
    champion gets no seeding guarantee, and a wild card with the better résumé
    seeds above it."""
    season = jh.run_season("girls", archived["arc"]["season_year"], seed=0,
                           salt=wd.active_salt(wd.DEFAULT_SEED))
    post = jh.power_index(list(season["teams"].values()), prestate=True)
    for g in jh.GROUPS:
        field = archived["arc"]["brackets"][g]["field"]
        assert field == sorted(field, key=lambda n: (-post[n].pi_raw, n))


def test_the_wildcard_recompute_sees_prestate_duals(archived):
    season = jh.run_season("girls", archived["arc"]["season_year"], seed=0,
                           salt=wd.active_salt(wd.DEFAULT_SEED))
    teams = list(season["teams"].values())
    cutoff = jh.rating_duals(teams)
    post = jh.rating_duals(teams, prestate=True)
    assert len(post) > len(cutoff)


def test_every_archived_record_covers_every_dual_played(archived):
    """The historically-buggy invariant: every dual on a program's schedule is
    reflected in its record — now with four new stages in front of State."""
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row
    for gender in ("girls", "boys"):
        arc = wd.get_jhsaa(archived["world"]["id"], archived["world"]["year"], gender)
        for g in jh.GROUPS:
            for dname, rows in arc["standings"][g].items():
                for r in rows:
                    school = r["school"]
                    sched = conn.execute(
                        "SELECT COUNT(*) c, SUM(won) w FROM world_jhsaa_dual"
                        " WHERE gender=? AND school=?", (gender, school)).fetchone()
                    wins, losses = (int(x) for x in r["record"].split("-"))
                    assert sched["c"] == wins + losses, (gender, school, r["record"])
                    assert sched["w"] == wins, (gender, school, r["record"])
    conn.close()
