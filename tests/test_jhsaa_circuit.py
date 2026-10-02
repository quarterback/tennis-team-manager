"""The CIRCUIT round (owner rule 2026-10) — over a REAL archived season.

In a `CIRCUIT_GROUPS` class, from `jhsaa.circuit_era()`, the Super Regionals and
Semi-State are ONE stage in two rounds over a field of 32: the 24 already in
recovery plus the next 8 on seeding ATR, dealt into eight Circuits of four by where
the programs are; each Circuit plays two semifinals (the Super Regionals, by name
and lane) and a final (the Circuit round). The eight Circuit champions qualify for
State with no bye. A 16-team State pilot class on the Circuit crowns from 24.

The suite's conftest replaces the era resolver so every OTHER suite stays on the
standing pair; this module swaps the Circuit on for its fixture.

Fixture (owner's smoke): one class from each of 1A, Group 2, Group 3, 10B and 11B
sized to fill Wards AND the Circuit's 32 in BOTH genders; every other class scaled
like `test_jhsaa_toc.py`. The Non-Public split is on (10B/11B are road classes).
"""
import pytest

from app import jhsaa as jh
from app import world as wd

SMOKE = ("1A", "Group 2", "Group 3", "10B", "11B")
#: Enough programs that the road fills (PROTECTED + WARD_FIELD), the Circuit's
#: eight extras come from the Ward/Sectional losers, and the Conference still has
#: a reservoir after them.
FLOOR = jh.PROTECTED + jh.WARD_FIELD + 12


def _small(real_load):
    def small(gender):
        out = []
        for grp in jh.GROUPS + jh.NONPUBLIC_GROUPS:
            floor = FLOOR if grp in SMOKE else jh.PROTECTED + 8
            names = sorted({s.district for s in real_load(gender) if s.group == grp})
            pool, keep = [], set()
            for name in names:
                keep.add(name)
                pool = [s for s in real_load(gender)
                        if s.group == grp and s.district in keep]
                if len(pool) > floor:
                    break
            out += pool
        return out
    return small


@pytest.fixture(scope="module")
def season(tmp_path_factory):
    db = str(tmp_path_factory.mktemp("jhsaa") / "circuit.db")
    real_load, real_db, real_ready = jh.load_schools, wd.WORLD_DB, wd._schema_ready_for
    real_primed, real_prime = wd.is_primed, wd.prime
    real_circ, real_pilot, real_np = jh.circuit_era, jh.sixteen_state_era, jh.nonpublic_era
    real_fields = dict(jh.STATE_FIELD)
    for grp, real in real_fields.items():
        if grp not in SMOKE:
            jh.STATE_FIELD[grp] = {24: 24, 32: 16, 40: 20}[real]
    jh.load_schools = _small(real_load)
    jh._season_cache.clear()
    jh.reset_schools()
    wd.WORLD_DB = db
    wd._schema_ready_for = None
    try:
        jh.circuit_era = lambda: 0              # the Circuit, from season one
        jh.sixteen_state_era = lambda: 0        # 1A / Group 3 are pilot classes
        jh.nonpublic_era = lambda: 0            # 10B / 11B are road classes
        w = wd.get_or_create(wd.DEFAULT_SEED)
        wd.run_jhsaa(wd.DEFAULT_SEED, w)
        wd.is_primed = lambda *a, **k: True
        wd.prime = lambda *a, **k: None
        yield {"db": db, "world": w,
               "arcs": {g: wd.get_jhsaa(w["id"], w["year"], g) for g in ("girls", "boys")},
               "season_year": wd.jhsaa_season_year(w)}
    finally:
        jh.load_schools = real_load
        jh.circuit_era, jh.sixteen_state_era, jh.nonpublic_era = real_circ, real_pilot, real_np
        jh.STATE_FIELD.clear()
        jh.STATE_FIELD.update(real_fields)
        jh._season_cache.clear()
        jh.reset_schools()
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready
        wd.is_primed, wd.prime = real_primed, real_prime


def _zonal_champs(arc, g):
    pre = arc["prestate"][g]
    return {gm["winner"] for gm in pre["rounds"][1]}


@pytest.mark.parametrize("gender", ["girls", "boys"])
@pytest.mark.parametrize("group", SMOKE)
def test_eight_circuits_of_four_and_twenty_four_duals(season, gender, group):
    arc = season["arcs"][gender]
    sr, ci = arc["super_regional"][group], arc["circuit"][group]
    circuits = sr["circuits"]
    assert len(circuits) == 8 and all(len(c) == 4 for c in circuits)
    assert ci["circuits"] == circuits
    assert len(sr["rounds"][0]) == 16 and len(ci["rounds"][0]) == 8
    assert sr["round_names"] == ["Super Regionals"] and ci["round_names"] == [jh.CIRCUIT_NAME]
    # Semi-State does not convene in a Circuit class.
    assert arc["semi_state"][group]["rounds"] == [[]]


@pytest.mark.parametrize("gender", ["girls", "boys"])
@pytest.mark.parametrize("group", SMOKE)
def test_no_team_in_two_circuits_and_no_zonal_champion_in_any(season, gender, group):
    arc = season["arcs"][gender]
    circuits = arc["super_regional"][group]["circuits"]
    names = [n for c in circuits for n in c]
    assert len(names) == len(set(names)) == 32
    assert not (set(names) & _zonal_champs(arc, group))


@pytest.mark.parametrize("gender", ["girls", "boys"])
@pytest.mark.parametrize("group", SMOKE)
def test_each_circuit_plays_one_v_four_two_v_three_then_a_final(season, gender, group):
    arc = season["arcs"][gender]
    sr, ci = arc["super_regional"][group], arc["circuit"][group]
    for ix, c in enumerate(sr["circuits"], start=1):
        semis = [gm for gm in sr["rounds"][0] if gm["circuit"] == ix]
        assert [(gm["home"], gm["away"]) for gm in semis] == [(c[0], c[3]), (c[1], c[2])]
        final = [gm for gm in ci["rounds"][0] if gm["circuit"] == ix]
        assert len(final) == 1 and final[0]["unit"] == f"Circuit {ix}"
        assert {final[0]["home"], final[0]["away"]} == {gm["winner"] for gm in semis}
    assert all(gm["unit"].startswith("Super Regional ") for gm in sr["rounds"][0])


@pytest.mark.parametrize("gender", ["girls", "boys"])
@pytest.mark.parametrize("group", SMOKE)
def test_every_circuit_champion_is_in_the_state_field_without_a_bye(season, gender, group):
    arc = season["arcs"][gender]
    champs = set(arc["circuit"][group]["survivors"])
    field = arc["brackets"][group]["field"]
    assert len(champs) == 8 and champs <= set(field)
    # No Zonal privilege and no bye BY RIGHT: the Epiregional winners hold bye
    # lines ahead of every Circuit champion, and a Circuit champion sits on one
    # only as one of the merit four (`state_seed_order` — the best of everyone
    # else on seeding ATR, the same door a Semi-State winner had), never by title.
    seeds = {n: i + 1 for i, n in enumerate(field)}
    epi = arc["epiregional"][group]
    epi_winners = {gm["winner"] for gm in epi["rounds"][0]}
    assert all(seeds[n] <= jh.STATE_BYES for n in epi_winners)
    on_bye = [n for n in champs if seeds[n] <= jh.STATE_BYES]
    assert len(on_bye) <= jh.STATE_BYES - len(epi_winners)
    assert not (champs & _zonal_champs(arc, group))


@pytest.mark.parametrize("gender", ["girls", "boys"])
def test_a_pilot_class_on_the_circuit_crowns_from_twenty_four(season, gender):
    arc = season["arcs"][gender]
    for group in ("1A", "Group 3"):
        assert jh.sixteen_state(group, season["season_year"])
        assert jh.state_field_size(group, season["season_year"]) == jh.CIRCUIT_PILOT_FIELD
        field = arc["brackets"][group]["field"]
        assert len(field) == 24
        zc = _zonal_champs(arc, group)
        cc = set(arc["circuit"][group]["survivors"])
        assert zc <= set(field) and cc <= set(field)
        # The last eight come through the 24-field tail 1A/10B/11B already run.
        tail = (set(arc["divisional"][group]["survivors"])
                | set((arc.get("state_special") or {}).get(group, {}).get("survivors") or ()))
        assert set(field) == zc | cc | tail


def test_the_circuit_is_an_explicit_season_gated_switch():
    assert isinstance(jh.CIRCUIT_GROUPS, tuple)
    assert jh.circuit("1A", None) is False
    assert jh.circuit("9A", 2200) is False
    assert "jhsaa_circuit_era" in jh.ERA_SETTINGS
    assert jh.CIRCUIT_PHASE in jh.POSTSEASON
    assert jh.POSTSEASON.index(jh.CIRCUIT_PHASE) == jh.POSTSEASON.index("super_regional") + 1


def test_the_projected_shape_matches_the_played_season(season):
    sy = season["season_year"]
    for group in SMOKE:
        shape = jh.recovery_shape(group, sy)
        assert shape["super_regional"] == 32 and shape[jh.CIRCUIT_PHASE] == 16
        assert shape["semi_state"] == 0
        arc = season["arcs"]["girls"]
        assert len(arc["super_regional"][group]["field"]) == shape["super_regional"]
        assert len(arc["circuit"][group]["field"]) == shape[jh.CIRCUIT_PHASE]


def test_no_forbidden_name_for_the_stage():
    for word in ("Section", "Regional", "Zonal", "Divisional", "Conference"):
        assert word not in jh.CIRCUIT_NAME
    assert jh._RECOVERY_UNITS[jh.CIRCUIT_PHASE] == "Circuit"


def test_a_circuit_title_is_a_team_honour_apart_from_state(season):
    arc = season["arcs"]["girls"]
    group = "Group 2"
    champ = arc["circuit"][group]["survivors"][0]
    rows = wd.jhsaa_school_seasons(season["world"]["id"], "girls", champ)
    row = next(r for r in rows if r["year"] == season["world"]["year"])
    assert f"{group} Circuit Champion" in row["team_honors"]
    assert any(u.startswith("Circuit ") for u in row["unit_wins"])
    assert not any("State Champion" in h for h in row["team_honors"] if "Circuit" in h)


def test_the_coefficient_prices_the_circuit_below_regionals():
    from app import jhsaa_coefficient as jcf
    pts = jcf.road_points()
    assert pts[jh.CIRCUIT_NAME] == 0.25 < pts[jh._STAGE_NAMES["regional"]]
    assert "circuit" in jcf._ROAD_KEYS


def test_the_title_board_counts_circuit_titles():
    cols = [c[0] for c in wd.jhsaa_title_stages()]
    assert jh.CIRCUIT_NAME in cols
    assert cols.index(jh.CIRCUIT_NAME) == cols.index("Super Regionals") + 1
