"""The postseason, end to end — over a REAL archived season.

The qualification structure (owner spec 2027-08, expanded State fields):

  1. Sectionals (Areas when multi-round) — broad access and field reduction.
     Every non-protected team enters; byes/play-ins as needed; the only fixed
     requirement is the output, exactly the Ward field.
  2. The ladder — fixed shape for every classification, both genders:
     Wards 32→16, Regionals 32→16 (Ward champions + protected), Zonals 16→8.
     Protected entrants (district champions first, then best cutoff TOSS) enter
     at Regionals. Zonal champions qualify for State automatically WITH the
     privileged path: they are the State draw's top seeds, so its byes are theirs.
  3. The district guarantee — a district champion has State ACCESS even if it
     loses in the ladder; access only, no bye, no extra berth if it won a Zonal.
  4. The recovery rounds — Super Regionals → Semi-State. Every remaining berth
     is EARNED ON COURT by the loser pool (Regional losers, joined at Semi-State
     by Zonal losers; 7A adds the best-TOSS Ward losers as bodies, another
     chance to play, never a berth). No berth is handed out by a TOSS recompute
     — the wild-card model is retired.

State is 24 teams in the three largest classes and 40 in the five smaller ones
(owner table 2027-08) — a 40 being a 24 with a Qualifiers Round in front of it.
`ladder_scale` shrinks every number together for pools too small for the full
shape — the two-district fixture here exercises exactly that; the full-size
arithmetic is asserted proportionally and pinned on synthetic draws below.

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
            arc["brackets"][g], arc["protected"][g],
            arc["district_qualifiers"][g],
            arc["super_regional"][g], arc["semi_state"][g], arc["divisional"][g])


# --- the fixed shape, per classification -------------------------------------------

def test_the_ladder_shape_is_fixed_and_proportional(archived):
    """Sectionals feeds Wards exactly; Wards halves; Regionals = Ward champions +
    protected and halves twice down to the Zonal champions."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        k = jh.ladder_scale(g)
        assert len(ward["field"]) == jh.WARD_FIELD // k
        assert len(sec["survivors"]) == len(ward["field"])
        assert len(ward["survivors"]) == len(ward["field"]) // 2
        assert len(pre["field"]) == len(ward["survivors"]) + len(protected)
        assert len(pre["field"]) == jh.WARD_FIELD // k          # Regionals re-fills to 32
        assert len(pre["survivors"]) == len(pre["field"]) // 4  # two rounds: 32 -> 8
        assert set(pre["field"]) == set(ward["survivors"]) | set(protected)


def test_the_state_field_is_champions_guarantees_and_recovery_survivors(archived):
    """Three ways in and no others: Zonal champions (top seeds), the district
    guarantee, and the Semi-State survivors — sized to the classification's
    State field, with the champions seeded first."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        k = jh.ladder_scale(g)
        zonal_champs = set(pre["survivors"])
        # ‼️ THE STATE FIELD IS FIXED (owner patch 2027-08): recovery conforms
        # to it — bye shortages are solved upstream with Ward-loser bodies,
        # never by extra duals, a deeper cut, or a short field.
        assert len(state["field"]) == jh.state_field_size(g, k)
        assert zonal_champs.isdisjoint(dq)
        assert set(state["field"]) \
            == zonal_champs | set(dq) | set(ss["survivors"]) | set(dv["survivors"])
        # the privileged path: champions are the draw's TOP seeds
        assert set(state["field"][:len(zonal_champs)]) == zonal_champs


def test_zonal_champions_are_the_top_seeds_byes_or_not(archived):
    """‼️ WINNING A ZONAL BUYS SEEDS 1-8 (owner clarification 2027-08). This is a
    SEEDING guarantee in its own right, not a side effect of byes. In a 24-team
    field the top eight seeds also collect the eight first-round byes, so the
    rule LOOKS like a bye rule — but 7A's field is 32, a power of two with no
    byes at all, and the guarantee there is purely that the Zonal champions are
    seeded 1-8. Asserted for BOTH shapes, so a change that ties the privilege to
    byes fails on the no-bye classification."""
    checked_bye_free = False
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        champs = list(pre["survivors"])
        field = state["field"]
        # the champions hold the top seed slots, in TOSS order among themselves
        assert set(field[:len(champs)]) == set(champs), g
        # ...and nobody else is seeded above one
        assert not (set(field[len(champs):]) & set(champs)), g
        n = len(field)
        if n and n & (n - 1) == 0:            # a power of two: no first-round byes
            checked_bye_free = True
        if state.get("round_names"):
            # an EXPANDED field's main draw is a full power of two with no byes
            # at all — the champions' top seeding there is pure guarantee, which
            # is exactly the case this assertion exists to keep honest
            checked_bye_free = True
    assert checked_bye_free, "no bye-free draw in the fixture — the no-bye case is untested"


def test_district_champions_always_reach_state(archived):
    """The geographic-access safeguard: every district champion is in the State
    field, zonal title or not — and the guarantee list is exactly the champions
    who did not win a Zonal."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        champs = {rows[0]["school"]
                  for rows in archived["arc"]["standings"][g].values() if rows}
        assert champs <= set(state["field"])
        assert set(dq) == champs - set(pre["survivors"])


def test_recovery_berths_are_earned_on_court(archived):
    """Nobody reaches State from the couch: every non-champion, non-guaranteed
    entrant survived Semi-State, and the recovery fields are drawn only from
    teams that lost in the ladder (Regional/Zonal losers, plus Ward losers where
    the arithmetic needs bodies)."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        earned = set(state["field"]) - set(pre["survivors"]) - set(dq)
        assert earned == (set(ss["survivors"]) | set(dv["survivors"])) - set(dq)
        reg_losers = {(gm["away"] if gm["winner"] == gm["home"] else gm["home"])
                      for gm in pre["rounds"][0]}
        zon_losers = {(gm["away"] if gm["winner"] == gm["home"] else gm["home"])
                      for gm in pre["rounds"][1]}
        ward_losers = {(gm["away"] if gm["winner"] == gm["home"] else gm["home"])
                       for games in ward["rounds"] for gm in games}
        # Bodies are walked back down the ladder as needed (owner rule 2027-08):
        # Regional losers, then Ward, then Sectional, then Area losers — deep
        # enough that the pool always contests its berths two-deep, so no bye
        # ever lands on a team that did not earn it.
        sec_losers = {(gm["away"] if gm["winner"] == gm["home"] else gm["home"])
                      for games in sec["rounds"] for gm in games}
        assert set(sr["field"]) <= reg_losers | ward_losers | sec_losers
        # Semi-State = Super Regional winners + Zonal losers + readmitted Super
        # Regional losers; the Divisional Round is drawn from Semi-State losers.
        assert set(ss["field"]) <= set(sr["field"]) | (zon_losers - set(dq))
        assert set(sr["survivors"]) <= set(ss["field"])
        assert set(dv["field"]) <= set(ss["field"]) - set(ss["survivors"])


def test_boys_and_girls_play_the_same_format(archived):
    for g in jh.GROUPS:
        for key in ("brackets", "wards", "prestate"):
            assert len(archived["arc"][key][g]["field"]) \
                == len(archived["arc_boys"][key][g]["field"]), (key, g)


# --- protection: district champions first, enter at Regionals, nothing more --------

def test_protected_is_district_champions_first_then_toss(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        champs = {rows[0]["school"]
                  for rows in archived["arc"]["standings"][g].values() if rows}
        assert champs <= set(protected)


def test_protected_teams_skip_sectionals_and_wards_only(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        assert set(protected).isdisjoint(sec["field"])
        assert set(protected).isdisjoint(ward["field"])
        assert set(protected) <= set(pre["field"])   # they DO play Regionals


# --- byes only in Sectionals --------------------------------------------------------

def test_wards_regionals_and_zonals_are_byes_free(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        for br in (ward, pre):
            alive = len(br["field"])
            for games in br["rounds"]:
                assert len(games) * 2 == alive, (g, alive, len(games))
                alive -= len(games)


def test_state_byes_belong_to_the_zonal_champions(archived):
    """A 24-team seeded draw has eight first-round byes, and those byes ARE the
    champions' privilege — every bye-taker is a Zonal champion. An EXPANDED field
    (the 40s and their scaled images) sharpens the same privilege into a DOUBLE
    BYE: the champions appear in none of the qualifying rounds, and the fresh
    main draw they enter is a full power of two with no byes at all."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        names = state.get("round_names") or []
        champs = set(pre["survivors"])
        if names:
            # the double bye: no champion in any qualifying round...
            for rd in state["rounds"][:len(names)]:
                played = {n for gm in rd for n in (gm["home"], gm["away"])}
                assert not (played & champs), g
            # ...and the main draw pairs EVERYONE alive — champions plus the
            # last qualifying round's winners — so nobody byes into it either.
            alive = champs | {gm["winner"] for gm in state["rounds"][len(names) - 1]}
            first_main = {n for gm in state["rounds"][len(names)]
                          for n in (gm["home"], gm["away"])}
            assert first_main == alive, g
            continue
        size = 1
        while size < len(state["field"]):
            size *= 2
        byes = size - len(state["field"])
        first_round = {n for gm in state["rounds"][0]
                       for n in (gm["home"], gm["away"])}
        sat_out = set(state["field"]) - first_round
        assert len(sat_out) == byes
        assert sat_out <= champs


# --- stage names ride the archive ---------------------------------------------------

def test_prestate_dicts_carry_their_own_round_names(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        assert ward["round_names"] == ["Wards"]
        assert pre["round_names"] == ["Regionals", "Zonals"]
        assert sr["round_names"] == ["Super Regionals"]
        assert ss["round_names"] == ["Semi-State"]
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
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
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
        assert [gm["unit"] for gm in sr["rounds"][0]] \
            == [f"Super Regional {j + 1}" for j in range(len(sr["rounds"][0]))]
        assert [gm["unit"] for gm in ss["rounds"][0]] \
            == [f"Semi-State {j + 1}" for j in range(len(ss["rounds"][0]))]


# --- postseason results across every stage ------------------------------------------

def test_finishes_name_the_stage_a_run_ended_at(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        grp = {"sectional": sec, "ward": ward, "prestate": pre,
               "super_regional": sr, "semi_state": ss, "divisional": dv,
               "state": state, "district_qualifiers": dq}
        # Sectional/Area losers can be pulled back in as recovery BODIES, and a
        # recovery run supersedes the round that sent them there — so only the
        # ones that stayed out name a Sectionals/Areas finish.
        sec_out = (set(sec["field"]) - set(sec["survivors"])
                   - set(sr["field"]) - set(ss["field"]) - set(dv["field"]))
        for name in sec_out:
            # A multi-round Sectionals opens with AREAS (owner rule): the finish
            # names the round the run actually ended in, so an Area-round exit
            # says "Areas", never the final round's "Sectionals".
            last = max(i for i, games in enumerate(sec["rounds"])
                       if any(name in (gm["home"], gm["away"]) for gm in games))
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == (sec["round_names"][last], False)
        # A Ward loser is out at Wards — unless TOSS handed it a recovery chance.
        for name in (set(ward["field"]) - set(ward["survivors"])
                     - set(sr["field"]) - set(ss["field"]) - set(dv["field"])):
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == ("Wards", False)
        # A ladder loser's year ends at the RECOVERY stage it fell out of, never
        # at the ladder round that sent it there — and a Super Regional loser
        # readmitted to Semi-State goes further still, so only the ones that
        # stopped there name "Super Regionals".
        for name in set(sr["field"]) - set(sr["survivors"]) - set(ss["field"]):
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == ("Super Regionals", False)
        # ...and a Semi-State loser drawn into the Divisional Round goes further
        # still, so only the ones that stopped there name "Semi-State".
        for name in set(ss["field"]) - set(ss["survivors"]) - set(dv["field"]):
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == ("Semi-State", False)
        for name in set(dv["field"]) - set(dv["survivors"]):
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == (jh.DIVISIONAL_NAME, False)
        for name in dq:
            r = wd.jhsaa_postseason_result(grp, name)
            assert r["made_state"] and r["district_qualifier"]
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
    for phase, key in (("super_regional", "super_regional"),
                       ("semi_state", "semi_state")):
        rows = conn.execute("SELECT COUNT(*) c FROM world_jhsaa_dual"
                            " WHERE phase=? AND gender='girls'", (phase,)).fetchone()
        played = sum(len(r) for d in archived["arc"][key].values()
                     for r in d["rounds"])
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


def test_state_seeds_are_champions_first_then_recovery_toss(archived):
    """Zonal champions are the draw's top seeds (TOSS-ordered among themselves);
    the district-guarantee and Semi-State qualifiers follow together in
    post-recovery TOSS order — the guarantee buys access, never seeding."""
    season = jh.run_season("girls", archived["arc"]["season_year"], seed=0,
                           salt=wd.active_salt(wd.DEFAULT_SEED))
    post = jh.power_index(list(season["teams"].values()), prestate=True)
    for g in jh.GROUPS:
        field = archived["arc"]["brackets"][g]["field"]
        zc = archived["arc"]["prestate"][g]["survivors"]
        head, tail = field[:len(zc)], field[len(zc):]
        assert head == sorted(head, key=lambda n: (-post[n].pi_raw, n))
        assert tail == sorted(tail, key=lambda n: (-post[n].pi_raw, n))


def test_the_postseason_recompute_sees_prestate_duals(archived):
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


# --- TEAM honours (owner rule 2027-08) ----------------------------------------------
#
# Every non-state postseason dual is a named, numbered UNIT, and winning one is an
# honour the program keeps — in ROMAN numerals ("Region IX", "Ward IV"; Zonals keep
# their letters). Reaching State is an honour of its own. Before this, only state
# champions and TOC sides carried anything.

def test_roman_numeral_unit_honours():
    assert [wd._roman(n) for n in (1, 4, 5, 9, 14, 40)] \
        == ["I", "IV", "V", "IX", "XIV", "XL"]
    assert wd._unit_honour("Regional 9") == "Region IX"
    assert wd._unit_honour("Ward 4") == "Ward IV"
    assert wd._unit_honour("Super Regional 2") == "Super Region II"
    assert wd._unit_honour("Zonal C") == "Zone C"       # letters stay letters


def test_every_unit_win_becomes_a_team_honour(archived):
    """A program's unit-win honours are exactly the units it won, ladder order —
    led by the district title when the program won its district (owner rule
    2027-08: the title sits with the zone/ward/section chips)."""
    arc = archived["arc"]
    champs = {g: {rows[0]["school"]: dname
                  for dname, rows in arc["standings"][g].items() if rows}
              for g in jh.GROUPS}
    for g in jh.GROUPS:
        won = {}
        for key in ("sectionals", "wards", "prestate", "super_regional",
                    "semi_state", "divisional"):
            for games in (arc[key][g].get("rounds") or ()):
                for gm in games:
                    won.setdefault(gm["winner"], []).append(wd._unit_honour(gm["unit"]))
        for school, units in won.items():
            row = next(r for r in wd.jhsaa_school_seasons(
                archived["world"]["id"], "girls", school)
                if r["year"] == archived["world"]["year"])
            title = [champs[g][school]] if school in champs[g] else []
            assert row["unit_wins"] == title + units, school
            assert row["honoured"]


def test_reaching_state_is_itself_an_honour(archived):
    """The report: only champions and TOC sides earned anything. Every State
    entrant now carries an honoured season with a finish to show for it."""
    arc = archived["arc"]
    for g in jh.GROUPS:
        for school in arc["brackets"][g]["field"]:
            row = next(r for r in wd.jhsaa_school_seasons(
                archived["world"]["id"], "girls", school)
                if r["year"] == archived["world"]["year"])
            assert row["made_state"] and row["honoured"] and row["state_finish"]


def test_recovery_draws_never_replay_the_team_that_just_eliminated_you(archived):
    """The draw PREFERENCE: don't immediately replay the opponent that just sent
    you here. "Just" means the previous STAGE, read off the archived arcs — the
    same thing `_pair_penalty` sees — not the previous row in the dual table,
    whose order across phases is an archiving detail.

    Asserted as no AVOIDABLE rematch: with byes gone every field is paired whole,
    so a degenerate pool (a two-team round whose teams just played each other)
    forces one. Every perfect matching is checked before calling it a fault."""
    arc = archived["arc"]

    def opp_map(stage, rounds=None):
        m = {}
        for ix, games in enumerate(stage.get("rounds") or ()):
            if rounds is not None and ix not in rounds:
                continue
            for gm in games:
                m[gm["home"]] = gm["away"]
                m[gm["away"]] = gm["home"]
        return m

    def matchings(items):
        if not items:
            yield []
            return
        a = items[0]
        for k in range(1, len(items)):
            for m in matchings(items[1:k] + items[k + 1:]):
                yield [(a, items[k])] + m

    offenders = []
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        reg, zon = opp_map(pre, {0}), opp_map(pre, {1})
        sr_opp, ss_opp = opp_map(sr), opp_map(ss)
        ward_opp, sec_opp = opp_map(ward), opp_map(sec)
        # where each round's entrants came from, nearest stage first
        sources = {
            "super_regional": (sr, [reg, ward_opp, sec_opp]),
            "semi_state": (ss, [sr_opp, zon]),
            jh.DIVISIONAL_NAME: (dv, [ss_opp]),
        }
        for label, (stage, maps) in sources.items():
            games = (stage.get("rounds") or [[]])[0]
            if not games:
                continue
            field = [nm for gm in games for nm in (gm["home"], gm["away"])]
            prev = {}
            for nm in field:
                for m in maps:
                    if nm in m:
                        prev[nm] = m[nm]
                        break
            hit = [(gm["home"], gm["away"]) for gm in games
                   if prev.get(gm["home"]) == gm["away"]
                   or prev.get(gm["away"]) == gm["home"]]
            if not hit:
                continue
            if any(all(prev.get(a) != b and prev.get(b) != a for a, b in m)
                   for m in matchings(field)):
                offenders.append((g, label, hit))
    assert not offenders, offenders[:5]

def test_no_recovery_round_has_a_bye(archived):
    """‼️ NOBODY REACHES STATE ON A BYE (owner rule 2027-08 — the goal the whole
    recovery design serves: "my goal is ultimately to keep people from earning
    their way to state with a bye, basically that's what i don't want").

    Three reports were the same bug: a No. 19 seed byed through both recovery
    rounds; a No. 4-TOSS Zonal loser took the Semi-State bye and reached State
    having won nothing; and the arithmetic kept manufacturing byes nobody could
    legitimately hold. The rounds used to be CUTS sized to whatever the pool
    happened to be, which left byes over. Now every recovery round pairs its
    ENTIRE field and the Divisional Round absorbs the leftover berths, so a bye
    is not disallowed — it cannot occur. This asserts the structural fact, not
    a rule about who may hold one."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        for name, arc in (("Super Regionals", sr), ("Semi-State", ss),
                          (jh.DIVISIONAL_NAME, dv)):
            played = {nm for games in arc["rounds"] for gm in games
                      for nm in (gm["home"], gm["away"])}
            assert set(arc["field"]) == played, (g, name, "bye in recovery")
        # ...so every recovery qualifier won its LAST dual, and the only other
        # doors into State are a Zonal title and the district guarantee.
        earned = set(state["field"]) - set(pre["survivors"]) - set(dq)
        won = {gm["winner"] for arc in (ss, dv)
               for games in arc["rounds"] for gm in games}
        assert earned <= won, (g, sorted(earned - won))

def test_recovery_byes_reach_the_bracket_view(archived):
    """The Road-to-State stages carry each recovery round's byes, so a lucky
    loser's path is legible on the bracket page — and nowhere else (not the
    schedule, no counters — owner rules 2027-08)."""
    from app.web.state import jhsaa_bracket_view
    for g in jh.GROUPS:
        view = jhsaa_bracket_view(wd.DEFAULT_SEED, "girls", g)
        sec, ward, pre, state, protected, dq, sr, ss, dv = _stages(archived, g)
        by_stage = {st["name"]: st for st in view["stages"]}
        for arc, name in ((sr, "Super Regionals"), (ss, "Semi-State")):
            played = {nm for games in arc["rounds"] for gm in games
                      for nm in (gm["home"], gm["away"])}
            expect = [nm for nm in arc["field"] if nm not in played]
            got = [b["name"] for b in by_stage[name].get("byes", [])]
            assert got == expect, (g, name)


def test_district_title_leads_the_units_honour_line(archived):
    """The district title sits ON the units line, first — with the zone/ward/
    section chips, not only as a ledger badge (owner rule 2027-08: the honours
    panel said "Region V · Zone C" while the header counted "1 district title")."""
    standings = archived["arc"]["standings"]
    checked = 0
    for g in jh.GROUPS:
        for dname, rows in standings[g].items():
            if not rows:
                continue
            champ = rows[0]["school"]
            for srow in wd.jhsaa_school_seasons(archived["world"]["id"], "girls", champ):
                if srow["year"] != archived["world"]["year"]:
                    continue
                assert srow["unit_wins"][:1] == [dname], (g, dname, champ)
                checked += 1
            # and the runner-up must NOT carry it
            if len(rows) > 1:
                for srow in wd.jhsaa_school_seasons(archived["world"]["id"], "girls",
                                                    rows[1]["school"]):
                    if srow["year"] == archived["world"]["year"]:
                        assert dname not in srow["unit_wins"]
    assert checked


# --- the expanded field and its identities (no fixture: data + synthetic draws) -----

def test_display_names_are_unique_identities():
    """‼️ A display name IS the archive's identity — it keys `run_season`'s teams
    dict, `world_jhsaa_dual.school`, the school routes and the pid space. Two
    schools sharing one name silently merge into one archive slot while the
    standings carry both rows, so a program's record stops covering the duals it
    played. This shipped once: the prep-network rebuild split an over-cap campus
    and the display collapse dropped the "North", so BOTH halves emitted as
    "Jefferson Science" — and the season archived a third school that was
    neither. `scripts/import_jhsaa.py::build` now refuses to emit a collision;
    this pins the data that is already checked in."""
    for g in jh.GENDERS:
        names = [s.name for s in jh.load_schools(g)]
        dupes = {n for n in names if names.count(n) > 1}
        assert not dupes, dupes


def test_an_expanded_field_is_a_24_with_qualies_in_front():
    """The owner's field table (2027-08): the three largest classes crown from 24;
    the five smaller ones crown from 40 — and a 40 IS a 24 with a Qualifiers
    Round in front of it. The Zonal champions take a DOUBLE bye to the
    Octofinals; everyone else plays the Qualies and then the First Round, and
    the eight who survive both join them in a fresh draw. After the Qualies
    exactly 24 are alive — the other classes' bracket — so both shapes converge
    and there is one championship from the Octofinals down."""
    teams = jh.district_teams(jh.load_schools("girls")[:40], 2027, "")
    br = jh.run_state(teams, seed=99, champions=8)
    rounds = wd.jhsaa_state_rounds(br)
    assert [(r["name"], r["alive"], len(r["games"])) for r in rounds] == [
        ("Qualifiers Round", 40, 16), ("First Round", 24, 8),
        ("Octofinals", 16, 8), ("Quarterfinals", 8, 4),
        ("Semifinals", 4, 2), ("Championship", 2, 1)]
    assert br["round_names"] == ["Qualifiers Round", "First Round"]
    champs = {t.school.name for t in teams[:8]}
    prelim = {n for rd in rounds[:2] for gm in rd["games"]
              for n in (gm["home"], gm["away"])}
    octo = {n for gm in rounds[2]["games"] for n in (gm["home"], gm["away"])}
    assert not (champs & prelim) and champs <= octo       # the double bye
    assert br["champion"] in {t.school.name for t in teams}
    # the 24-team shape is untouched: one fixed draw whose byes are the champions
    br24 = jh.run_state(teams[:24], seed=99, champions=8)
    assert not br24["round_names"]
    assert [(r["alive"], len(r["games"])) for r in wd.jhsaa_state_rounds(br24)] \
        == [(24, 8), (16, 8), (8, 4), (4, 2), (2, 1)]
