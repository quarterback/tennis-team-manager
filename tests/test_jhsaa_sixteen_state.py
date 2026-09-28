"""The 16-team State pilot (JHSAA rule 2099) — over a REAL archived season.

In 4A, 3A, 2A, 1A and Group 3, from `jhsaa.sixteen_state_era()`, State is the
eight Zonal champions and the eight Semi-State winners and nobody else: recovery
ends at Semi-State, the Divisionals/Semi-Conference/Conference/Special
Challengers/State Specials/Metastate/Parastate do not run, the committee selects
nothing, and the draw is a plain 16 on strict seed lines from the Octofinals.
Spec: docs/reports/SPEC-jhsaa-16-team-state-pilot.md.

The suite's conftest replaces the era resolver so every OTHER suite stays on the
standing ladder; this module swaps the pilot back on for its fixture and tests
the real resolver separately.

Fixture: pilot classes sized to fill Wards (the ladder's full shape), the rest
scaled like `test_jhsaa_toc.py` so a run stays affordable.
"""
import json
import sqlite3

import pytest

from app import jhsaa as jh
from app import world as wd
from app import worldconfig as wc

REMOVED_PHASES = ("divisional", "semi_conference", "conference", "state_special",
                  "special_challenger", jh.METASTATE_PHASE, "parastate")
FORBIDDEN_FINISHES = ("Round of 32", "Round of 24", jh.PARASTATE_NAME,
                      jh.CONFERENCE_NAME, jh.STATE_SPECIAL_FINISH,
                      jh.SEMI_CONFERENCE_NAME, jh.DIVISIONAL_NAME,
                      jh.SPECIAL_CHALLENGER_FINISH, jh.METASTATE_FINISH,
                      jh.QUALIFIER_NAME, "Qualies")


def _small(real_load):
    def small(gender):
        out = []
        for grp in jh.GROUPS:
            # A GIRLS pilot class must FILL Wards (PROTECTED + WARD_FIELD) or its
            # road runs short and the full shape cannot be asserted. Everything
            # else only needs a road at all — and the BOYS pilot classes are left
            # thin on purpose: they are the real-data case of a short Semi-State.
            floor = (jh.PROTECTED + jh.WARD_FIELD
                     if gender == "girls" and grp in jh.SIXTEEN_STATE_GROUPS
                     else jh.PROTECTED + 8)
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
def pilot(tmp_path_factory):
    """One season archived with the pilot ON, plus the same girls season played
    with it OFF (for the non-pilot comparison)."""
    db = str(tmp_path_factory.mktemp("jhsaa_sixteen") / "sixteen.db")
    real_load, real_db, real_ready = jh.load_schools, wd.WORLD_DB, wd._schema_ready_for
    real_era, real_fields = jh.sixteen_state_era, dict(jh.STATE_FIELD)
    real_primed, real_prime = wd.is_primed, wd.prime
    # Non-pilot classes scaled with their pools, the `test_jhsaa_toc.py` rule.
    for grp, real in real_fields.items():
        if grp not in jh.SIXTEEN_STATE_GROUPS:
            jh.STATE_FIELD[grp] = {24: 24, 32: 16, 40: 20}[real]
    jh.load_schools = _small(real_load)
    jh._season_cache.clear()
    wd.WORLD_DB = db
    wd._schema_ready_for = None
    try:
        # ‼️ THE GATE-CLOSED SEASON IS PLAYED FIRST, before anything is archived:
        # roster generation reads archived exposure and talent pins, so a season
        # played after the archive is written is not the same season.
        w = wd.get_or_create(wd.DEFAULT_SEED)
        sy = wd.jhsaa_season_year(w)
        salt = wd.active_salt(wd.DEFAULT_SEED)
        # The comparison pair runs with no staff and no prior (the standalone
        # season): with staffs attached, two consecutive in-process seasons were
        # seen to differ in their REGULAR season, pilot or not — a separate
        # question from this pilot, noted in the AAR.
        args = dict(seed=0, salt=salt)
        jh.sixteen_state_era = lambda: 10 ** 6        # no pilot
        off = jh.run_season("girls", sy, **args)
        jh.sixteen_state_era = lambda: 0              # the pilot, from season one
        on = jh.run_season("girls", sy, **args)
        wd.run_jhsaa(wd.DEFAULT_SEED, w)
        wd.is_primed = lambda *a, **k: True
        wd.prime = lambda *a, **k: None
        from app.web.server import create_app
        yield {"db": db, "world": w, "season_year": sy, "on": on, "off": off,
               "client": create_app().test_client(),
               "arc": wd.get_jhsaa(w["id"], w["year"], "girls"),
               "arc_boys": wd.get_jhsaa(w["id"], w["year"], "boys")}
    finally:
        jh.sixteen_state_era = real_era
        jh.load_schools = real_load
        jh.STATE_FIELD.clear()
        jh.STATE_FIELD.update(real_fields)
        jh._season_cache.clear()
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready
        wd.is_primed, wd.prime = real_primed, real_prime


def _arcs(pilot):
    return (("girls", pilot["arc"]), ("boys", pilot["arc_boys"]))


# --- the gate, the tables and the draw (no season needed) --------------------------

def test_membership_is_an_explicit_tuple():
    assert jh.SIXTEEN_STATE_GROUPS == ("4A", "3A", "2A", "1A", "Group 3")
    assert set(jh.SIXTEEN_STATE_GROUPS) <= set(jh.GROUPS)


def test_the_era_is_a_pinnable_season_gate(monkeypatch):
    """The real resolver (the conftest replaces `sixteen_state_era` for every
    other suite): an explicit worldconfig value pins it, it is one of the eras
    `reset_eras` clears, and a `year` of None never consults it."""
    assert "jhsaa_sixteen_state_era" in jh.ERA_SETTINGS
    prev = wc.get("jhsaa_sixteen_state_era")
    try:
        wc.set("jhsaa_sixteen_state_era", "2099")
        jh._sixteen_state_era_cache.clear()
        resolved = jh._resolve_era("jhsaa_sixteen_state_era",
                                   jh._sixteen_state_era_cache)
        assert resolved == 2099
        monkeypatch.setattr(jh, "sixteen_state_era", lambda: resolved)
        assert not jh.sixteen_state("3A", 2098)
        assert jh.sixteen_state("3A", 2099) and jh.sixteen_state("Group 3", 2150)
        assert not jh.sixteen_state("5A", 2099)

        def boom():
            raise AssertionError("year=None must not resolve the era")
        monkeypatch.setattr(jh, "sixteen_state_era", boom)
        assert not jh.sixteen_state("3A", None)
        assert jh.state_field_size("3A") == jh.STATE_FIELD["3A"]
    finally:
        wc.set("jhsaa_sixteen_state_era", prev or "")
        jh._sixteen_state_era_cache.clear()


def test_the_tables_answer_for_the_season(monkeypatch):
    monkeypatch.setattr(jh, "sixteen_state_era", lambda: 2099)
    for g in jh.SIXTEEN_STATE_GROUPS:
        # before the era: the owner's tables, exactly as written
        assert jh.state_field_size(g, 2098) == jh.state_field_size(g) == jh.STATE_FIELD[g]
        assert jh.at_large_bids(g, 2098) == jh.AT_LARGE_BIDS[g]
        # from it: 16, no bids, no metas, no Parastate
        assert jh.state_field_size(g, 2099) == jh.SIXTEEN_STATE_FIELD == 16
        assert jh.at_large_bids(g, 2099) == 0
        assert jh.metastate_bids(g, 2099) == 0
        assert jh.parastate_byes(g, 2099) == 16
        shape = jh.recovery_shape(g, 2099)
        assert shape == {"berths": 8, "champions": 8, "super_regional": 16,
                         "semi_state": 16, "divisional": 0, "semi_conference": 0,
                         "conference": 0, "body_seats": 0}
        assert shape["champions"] + shape["semi_state"] // 2 == 16
        # the ward gate survives the missing Conference
        assert jh.sponsor_floor(g, 2099) == jh.PROTECTED + jh.WARD_FIELD
        assert g not in {x for _l, gs, _r, _b in jh.parastate_summary(2099) for x in gs}
    for g in set(jh.GROUPS) - set(jh.SIXTEEN_STATE_GROUPS):
        assert jh.state_field_size(g, 2099) == jh.state_field_size(g)
        assert jh.at_large_bids(g, 2099) == jh.at_large_bids(g)
        assert jh.recovery_shape(g, 2099) == jh.recovery_shape(g)


def test_the_table_asserts_hold_with_no_pilot_bids(monkeypatch):
    """The import-time guards bind the TABLES; a pilot class's zero bids must
    still satisfy both (bids fit inside the road; Metastate bids even)."""
    monkeypatch.setattr(jh, "sixteen_state_era", lambda: 0)
    for g in jh.GROUPS:
        assert jh.at_large_bids(g, 2099) <= jh.state_field_size(g, 2099)
        assert jh.metastate_bids(g, 2099) % 2 == 0


def test_strict_seed_lines():
    """1v16, 8v9, 4v13, 5v12 | 2v15, 7v10, 3v14, 6v11 — rank for rank; a short
    field's missing lines are the highest seeds, so the byes are the top seeds'."""
    slots = jh.seed_line_slots(list(range(1, 17)))
    pairs = [tuple(slots[i:i + 2]) for i in range(0, 16, 2)]
    assert pairs == [(1, 16), (8, 9), (4, 13), (5, 12),
                     (2, 15), (7, 10), (3, 14), (6, 11)]
    short = jh.seed_line_slots(list(range(1, 14)))            # 13 teams
    byes = [p[0] for p in (short[i:i + 2] for i in range(0, 16, 2)) if None in p]
    assert sorted(byes) == [1, 2, 3]


# --- the played season -------------------------------------------------------------

def test_every_pilot_field_is_eight_zonal_champions_then_eight_semi_state_winners(pilot):
    arc = pilot["arc"]
    for grp in jh.SIXTEEN_STATE_GROUPS:
        st = arc["brackets"][grp]
        field = st["field"]
        assert len(field) == 16, (grp, len(field))
        zc = arc["prestate"][grp]["survivors"]
        ss = arc["semi_state"][grp]["survivors"]
        assert len(zc) == 8 and len(ss) == 8
        assert set(field[:8]) == set(zc)
        assert set(field[8:]) == set(ss)
        # Epiregional order: its four winners hold lines 1-4
        assert set(field[:4]) == set(arc["epiregional"][grp]["survivors"])
        assert st["round_names"] == []


def test_the_first_round_is_the_octofinals_on_strict_lines(pilot):
    arc = pilot["arc"]
    for grp in jh.SIXTEEN_STATE_GROUPS:
        st = arc["brackets"][grp]
        assert [len(r) for r in st["rounds"]] == [8, 4, 2, 1]
        labels = [r["name"] for r in wd.jhsaa_state_rounds(st)]
        assert labels[0] == "Octofinals" and labels[1] == "Quarterfinals"
        seed = {n: i + 1 for i, n in enumerate(st["field"])}
        r1 = [tuple(sorted((seed[gm["home"]], seed[gm["away"]])))
              for gm in st["rounds"][0]]
        assert r1 == [(1, 16), (8, 9), (4, 13), (5, 12),
                      (2, 15), (7, 10), (3, 14), (6, 11)]


def test_no_removed_round_runs_in_a_pilot_class(pilot):
    for _g, arc in _arcs(pilot):
        for grp in jh.SIXTEEN_STATE_GROUPS:
            for key in ("divisional", "semi_conference", "conference",
                        "state_special", "special_challenger"):
                d = arc[key][grp] or {}
                assert not d.get("field") and not any(d.get("rounds") or ()), (grp, key)
            assert arc[jh.METASTATE_PHASE][grp] is None
            assert jh.PARASTATE_NAME not in arc["brackets"][grp]["round_names"]
            assert arc["committee"][grp] is None
            assert arc["ratings"][grp]          # TOSS/ATR and ratings still archive
    # ...and it is the pilot classes only
    for grp in set(jh.GROUPS) - set(jh.SIXTEEN_STATE_GROUPS):
        assert pilot["arc"]["committee"][grp] is not None


def test_no_pilot_dual_carries_a_removed_phase(pilot):
    w = pilot["world"]
    conn = sqlite3.connect(pilot["db"])
    try:
        for gender, arc in _arcs(pilot):
            schools = {row["school"] for grp in jh.SIXTEEN_STATE_GROUPS
                       for rows in arc["standings"][grp].values() for row in rows}
            q = ",".join("?" * len(REMOVED_PHASES))
            bad = conn.execute(
                f"SELECT school, phase FROM world_jhsaa_dual WHERE world_id=? AND"
                f" year=? AND gender=? AND phase IN ({q})",
                (w["id"], w["year"], gender, *REMOVED_PHASES)).fetchall()
            assert not [b for b in bad if b[0] in schools], bad[:5]
    finally:
        conn.close()


def test_pilot_finishes_read_the_round_the_team_lost_in(pilot):
    w = pilot["world"]
    for gender, arc in _arcs(pilot):
        rows = wd.jhsaa_history_rows(w["id"], gender)
        ss_losers = {n for grp in jh.SIXTEEN_STATE_GROUPS
                     for n in arc["semi_state"][grp]["field"]
                     if n not in arc["semi_state"][grp]["survivors"]}
        sr_losers = {n for grp in jh.SIXTEEN_STATE_GROUPS
                     for n in arc["super_regional"][grp]["field"]
                     if n not in arc["super_regional"][grp]["survivors"]}
        seen = 0
        for grp in jh.SIXTEEN_STATE_GROUPS:
            for drows in arc["standings"][grp].values():
                for row in drows:
                    name = row["school"]
                    ledger = [r for r in rows.get(name, ())
                              if r["year"] == w["year"]]
                    assert ledger, name
                    fin = ledger[0].get("state_finish") or ""
                    assert fin not in FORBIDDEN_FINISHES, (grp, name, fin)
                    if name in ss_losers:
                        assert fin == "Semi-State", (name, fin)
                    if name in sr_losers:
                        assert fin == "Super Regionals", (name, fin)
                    seen += 1
        assert seen


def test_recovery_shape_matches_the_played_season(pilot):
    sy, arc = pilot["season_year"], pilot["arc"]
    for grp in jh.SIXTEEN_STATE_GROUPS:
        shape = jh.recovery_shape(grp, sy)
        assert len(arc["super_regional"][grp]["field"]) == shape["super_regional"]
        assert len(arc["semi_state"][grp]["field"]) == shape["semi_state"]
        assert len(arc["semi_state"][grp]["survivors"]) == shape["berths"]
        for k in ("divisional", "semi_conference", "conference"):
            assert len(arc[k][grp]["field"]) == shape[k] == 0


def test_a_thin_road_on_real_data_fields_only_the_two_doors(pilot):
    """The boys' pilot classes are deliberately thin (see the fixture): whatever
    their Semi-State delivered, State is the Zonal champions plus the Semi-State
    winners and NOTHING else, any shortfall byes the TOP seeds, and no removed
    round convened to make up the difference."""
    arc = pilot["arc_boys"]
    for grp in jh.SIXTEEN_STATE_GROUPS:
        st = arc["brackets"][grp]
        zc = arc["prestate"][grp]["survivors"]
        ss = arc["semi_state"][grp]["survivors"]
        assert set(st["field"][:len(zc)]) == set(zc)
        assert set(st["field"][len(zc):]) == set(ss)
        assert len(st["field"]) <= 16
        missing = 16 - len(st["field"])
        if missing and st["rounds"]:
            seed = {n: i + 1 for i, n in enumerate(st["field"])}
            played = {seed[n] for gm in st["rounds"][0]
                      for n in (gm["home"], gm["away"])}
            assert set(range(1, missing + 1)).isdisjoint(played), grp
        for key in ("divisional", "semi_conference", "conference",
                    "state_special", "special_challenger"):
            assert not any((arc[key][grp] or {}).get("rounds") or ()), (grp, key)


def test_non_pilot_classes_match_the_same_season_without_the_pilot(pilot):
    """‼️ SCOPED IDENTITY (owner decision 2026-09). The State seeding TOSS is
    recomputed over the WHOLE gender after recovery and non-district play links
    the classes, so removing the pilot classes' later rounds can nudge a
    non-pilot class's State SEED ORDER (and everything downstream: its State
    results, records, awards, the TOC). What must not move is everything before
    that: the whole road, the State field's membership and the committee."""
    on, off = pilot["on"], pilot["off"]
    road = ("sectional", "ward", "prestate", "epiregional", "super_regional",
            "semi_state", "divisional", "semi_conference", "conference",
            "special_challenger", "state_special", jh.METASTATE_PHASE,
            "protected", "district_qualifiers", "ratings", "committee")
    dump = lambda x: json.dumps(x, sort_keys=True, default=str)  # noqa: E731
    for grp in set(jh.GROUPS) - set(jh.SIXTEEN_STATE_GROUPS):
        a, b = on["groups"][grp], off["groups"][grp]
        for k in road:
            assert dump(a.get(k)) == dump(b.get(k)), (grp, k)
        assert set(a["state"]["field"]) == set(b["state"]["field"]), grp
        assert (a["state"].get("at_large") or []) == (b["state"].get("at_large") or [])


def test_the_pilot_off_season_plays_the_standing_ladder(pilot):
    """The same code with the gate closed is the pre-pilot postseason: every
    pilot class runs its Divisionals and Conference, has a committee and crowns
    from its road plus bids."""
    off = pilot["off"]
    for grp in jh.SIXTEEN_STATE_GROUPS:
        g = off["groups"][grp]
        assert g["committee"] is not None
        assert any(g["divisional"]["rounds"])
        assert len(g["state"]["field"]) > 16


def test_a_thin_semi_state_runs_short_and_reopens_nothing(pilot, monkeypatch):
    """Two Zonals voided: Semi-State is 8 + 6 = 14 teams, 7 winners, and State
    runs 6 + 7 = 13 with byes to the top three seeds. No Divisional convenes to
    fill the three missing berths."""
    monkeypatch.setattr(jh, "sixteen_state_era", lambda: 0)
    on, sy = pilot["on"], pilot["season_year"]
    grp = "3A"
    g = on["groups"][grp]
    by_name = {n: t for n, t in on["teams"].items() if t.school.group == grp}
    pre = json.loads(json.dumps(g["prestate"]))
    pre["rounds"][1] = pre["rounds"][1][2:]                 # two Zonals never played
    champs = [by_name[gm["winner"]] for gm in pre["rounds"][1]]
    sr, ss, dv, sc, cf, quals, _dq, _atr = jh._recovery(
        grp, by_name, g["sectional"], g["ward"], pre, champs,
        [], {}, seed=5, year=sy)
    assert len(ss["field"]) == 14 and len(quals) == 7
    for arc in (dv, sc, cf):
        assert not arc["field"] and not any(arc["rounds"])
    st = jh.run_state_sixteen(champs, champs[:3], quals, None, seed=9)
    assert len(st["field"]) == 13
    seed = {n: i + 1 for i, n in enumerate(st["field"])}
    played_r1 = {seed[n] for gm in st["rounds"][0] for n in (gm["home"], gm["away"])}
    assert {1, 2, 3}.isdisjoint(played_r1)                   # the byes
    assert len(st["rounds"][0]) == 5


def test_the_bracket_page_renders_a_plain_16(pilot):
    c, w = pilot["client"], pilot["world"]
    for grp in jh.SIXTEEN_STATE_GROUPS:
        r = c.get(f"/jhsaa/bracket?g=girls&group={grp}&year={w['year']}")
        assert r.status_code == 200, grp
        html = r.get_data(as_text=True)
        assert jh.PARASTATE_NAME not in html
        assert "Octofinals" in html


def test_the_committee_page_does_not_list_pilot_classes(pilot):
    from app.web.state import jhsaa_committee_view
    view = jhsaa_committee_view(wd.DEFAULT_SEED, "girls", "3A")
    assert not set(view["groups"]) & set(jh.SIXTEEN_STATE_GROUPS)
    assert view["group"] not in jh.SIXTEEN_STATE_GROUPS
    r = pilot["client"].get("/jhsaa/committee?g=girls&group=3A")
    assert r.status_code == 200


def test_the_export_omits_the_pilot_committees(pilot):
    from app.research_export import build_jhsaa
    files = build_jhsaa(pilot["season_year"], "girls")
    committee = json.loads(files["jhsaa_committee.json"])
    assert not set(committee) & set(jh.SIXTEEN_STATE_GROUPS)
    assert committee                                     # the others still ship
    assert b"jhsaa_program_history.csv" in b"".join(k.encode() for k in files)
