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

State is 32 teams in 7A, 24 elsewhere. `ladder_scale` shrinks every number
together for pools too small for the full shape — the two-district fixture here
exercises exactly that; the full-size arithmetic is asserted proportionally.

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
            arc["super_regional"][g], arc["semi_state"][g])


# --- the fixed shape, per classification -------------------------------------------

def test_the_ladder_shape_is_fixed_and_proportional(archived):
    """Sectionals feeds Wards exactly; Wards halves; Regionals = Ward champions +
    protected and halves twice down to the Zonal champions."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
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
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
        k = jh.ladder_scale(g)
        zonal_champs = set(pre["survivors"])
        # A Semi-State bye no eligible holder can take is PLAYED OFF instead
        # (owner rule: a bye is never the ticket in), so the round may cut
        # deeper than its target and the field may run short — by exactly the
        # extra duals played, never more.
        berths = jh.state_field_size(g, k) - len(zonal_champs) - len(dq)
        natural = len(ss["field"]) - berths
        extra = max(0, len(ss["rounds"][0]) - natural)
        assert len(state["field"]) == jh.state_field_size(g, k) - extra
        assert zonal_champs.isdisjoint(dq)
        assert set(state["field"]) \
            == zonal_champs | set(dq) | set(ss["survivors"])
        # the privileged path: champions are the draw's TOP seeds
        assert set(state["field"][:len(zonal_champs)]) == zonal_champs


def test_district_champions_always_reach_state(archived):
    """The geographic-access safeguard: every district champion is in the State
    field, zonal title or not — and the guarantee list is exactly the champions
    who did not win a Zonal."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
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
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
        earned = set(state["field"]) - set(pre["survivors"]) - set(dq)
        assert earned == set(ss["survivors"]) - set(dq)
        reg_losers = {(gm["away"] if gm["winner"] == gm["home"] else gm["home"])
                      for gm in pre["rounds"][0]}
        zon_losers = {(gm["away"] if gm["winner"] == gm["home"] else gm["home"])
                      for gm in pre["rounds"][1]}
        ward_losers = {(gm["away"] if gm["winner"] == gm["home"] else gm["home"])
                       for games in ward["rounds"] for gm in games}
        assert set(sr["field"]) <= reg_losers | ward_losers
        assert set(ss["field"]) == set(sr["survivors"]) | (zon_losers - set(dq))


def test_boys_and_girls_play_the_same_format(archived):
    for g in jh.GROUPS:
        for key in ("brackets", "wards", "prestate"):
            assert len(archived["arc"][key][g]["field"]) \
                == len(archived["arc_boys"][key][g]["field"]), (key, g)


# --- protection: district champions first, enter at Regionals, nothing more --------

def test_protected_is_district_champions_first_then_toss(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
        champs = {rows[0]["school"]
                  for rows in archived["arc"]["standings"][g].values() if rows}
        assert champs <= set(protected)


def test_protected_teams_skip_sectionals_and_wards_only(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
        assert set(protected).isdisjoint(sec["field"])
        assert set(protected).isdisjoint(ward["field"])
        assert set(protected) <= set(pre["field"])   # they DO play Regionals


# --- byes only in Sectionals --------------------------------------------------------

def test_wards_regionals_and_zonals_are_byes_free(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
        for br in (ward, pre):
            alive = len(br["field"])
            for games in br["rounds"]:
                assert len(games) * 2 == alive, (g, alive, len(games))
                alive -= len(games)


def test_state_byes_belong_to_the_zonal_champions(archived):
    """A 24-team seeded draw has eight first-round byes, and those byes ARE the
    champions' privilege — every bye-taker is a Zonal champion. A full field
    (7A at 32, or a scaled pool that pads to nothing) has no byes to give and
    the privilege is the top seeding alone."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
        size = 1
        while size < len(state["field"]):
            size *= 2
        byes = size - len(state["field"])
        first_round = {n for gm in state["rounds"][0]
                       for n in (gm["home"], gm["away"])}
        sat_out = set(state["field"]) - first_round
        assert len(sat_out) == byes
        assert sat_out <= set(pre["survivors"])


# --- stage names ride the archive ---------------------------------------------------

def test_prestate_dicts_carry_their_own_round_names(archived):
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
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
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
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
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
        grp = {"sectional": sec, "ward": ward, "prestate": pre,
               "super_regional": sr, "semi_state": ss,
               "state": state, "district_qualifiers": dq}
        sec_out = set(sec["field"]) - set(sec["survivors"])
        for name in sec_out:
            # A multi-round Sectionals opens with AREAS (owner rule): the finish
            # names the round the run actually ended in, so an Area-round exit
            # says "Areas", never the final round's "Sectionals".
            last = max(i for i, games in enumerate(sec["rounds"])
                       if any(name in (gm["home"], gm["away"]) for gm in games))
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == (sec["round_names"][last], False)
        # A Ward loser is out at Wards — unless TOSS handed it a recovery chance.
        for name in set(ward["field"]) - set(ward["survivors"]) - set(sr["field"]):
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == ("Wards", False)
        # A ladder loser's year now ends at the RECOVERY stage it fell out of,
        # never at the ladder round that sent it there.
        for name in set(sr["field"]) - set(sr["survivors"]):
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == ("Super Regionals", False)
        for name in set(ss["field"]) - set(ss["survivors"]):
            r = wd.jhsaa_postseason_result(grp, name)
            assert (r["finish"], r["made_state"]) == ("Semi-State", False)
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
        for key in ("sectionals", "wards", "prestate", "super_regional", "semi_state"):
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
    """The draw preference: don't immediately replay the opponent that just sent
    you here. Byes are awarded FIRST, by TOSS from the bye-eligible teams
    (owner rule 2027-08 — no joint bye-and-pairing search), and the pairing
    method then avoids rematches wherever a rematch-free matching of the
    playing set EXISTS. In a degenerate pool (a two-team Semi-State whose two
    teams just played each other) the rematch is structurally forced and
    allowed — so this asserts no AVOIDABLE rematch, by checking every perfect
    matching of the round's playing set."""
    import itertools
    arc = archived["arc"]
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row

    def last_before(school, opp_this_round):
        sched = [r["opp"] for r in conn.execute(
            "SELECT opp FROM world_jhsaa_dual WHERE world_id=? AND year=?"
            " AND gender='girls' AND school=? ORDER BY rowid",
            (archived["world"]["id"], archived["world"]["year"], school))]
        # LAST occurrence: district opponents meet twice in the round robin, so
        # the first hit could be a March league dual rather than this round.
        for i in range(len(sched) - 1, 0, -1):
            if sched[i] == opp_this_round:
                return sched[i - 1]
        return ""

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
        for key in ("super_regional", "semi_state"):
            games = (arc[key][g].get("rounds") or [[]])[0]
            if not games:
                continue
            playing = [nm for gm in games for nm in (gm["home"], gm["away"])]
            # each team's opponent in the dual immediately before this round
            prev = {nm: last_before(nm, opp)
                    for gm in games
                    for nm, opp in ((gm["home"], gm["away"]),
                                    (gm["away"], gm["home"]))}
            hit = [(gm["home"], gm["away"]) for gm in games
                   if prev[gm["home"]] == gm["away"] or prev[gm["away"]] == gm["home"]]
            if not hit:
                continue
            # a rematch happened — is any matching of this playing set clean?
            avoidable = False
            for m in matchings(playing):
                if all(prev[a] != b and prev[b] != a for a, b in m):
                    avoidable = True
                    break
            if avoidable:
                offenders.append((g, key, hit))
    conn.close()
    assert not offenders, offenders[:5]

def test_a_bye_is_never_the_ticket_into_state(archived):
    """‼️ EVERY RECOVERY QUALIFIER'S LAST APPEARANCE IS A WIN (owner rules
    2027-08, sharpened across two reports). Byes go to the top of the TOSS
    order and the rounds only eliminate a cut, so the original shape let a
    No. 19 seed coast through BOTH rounds unplayed, and the first fix still let
    a No. 4-TOSS Zonal loser take the Semi-State bye and reach State having
    won nothing ("a team loses in zonals and gets to state without winning
    their district"). Now the Semi-State bye belongs only to a Super Regional
    game-WINNER: Super Regional bye holders and Zonal losers alike must play
    at Semi-State. Game counts are untouched — the rules only move WHO sits."""
    for g in jh.GROUPS:
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
        def byes(arc):
            played = {nm for games in arc["rounds"] for gm in games
                      for nm in (gm["home"], gm["away"])}
            return {nm for nm in arc["field"] if nm not in played}
        assert not byes(sr) & byes(ss), (g, "double bye")
        sr_winners = {gm["winner"] for games in sr["rounds"] for gm in games}
        assert byes(ss) <= sr_winners, (g, "Semi-State bye without an SR win")
        # the invariant the two rules add up to: every recovery qualifier
        # WON a recovery dual — champions and the guarantee are the only
        # other doors into State.
        earned = set(state["field"]) - set(pre["survivors"]) - set(dq)
        won = sr_winners | {gm["winner"] for games in ss["rounds"] for gm in games}
        assert earned <= won, (g, sorted(earned - won))


def test_recovery_byes_reach_the_bracket_view(archived):
    """The Road-to-State stages carry each recovery round's byes, so a lucky
    loser's path is legible on the bracket page — and nowhere else (not the
    schedule, no counters — owner rules 2027-08)."""
    from app.web.state import jhsaa_bracket_view
    for g in jh.GROUPS:
        view = jhsaa_bracket_view(wd.DEFAULT_SEED, "girls", g)
        sec, ward, pre, state, protected, dq, sr, ss = _stages(archived, g)
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
