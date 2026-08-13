"""The postseason LADDER, end to end — over a REAL archived season.

Sectionals -> Wards -> Regionals -> Zonals -> State (owner rule, ladder expansion)
replaced the old model of picking a fixed 24/32-team field straight off district
standings. The design invariants that model was built to satisfy:

  * EVERY team not protected plays into Sectionals — no pre-cut field.
  * Protection (a district automatic bid) skips Sectionals ONLY — a protected team
    still has to win Regionals and Zonals like anyone else; nothing shortcuts past
    them on a district title.
  * From the combined field on (Wards/Regionals/Zonals/State), the bracket is an
    EXACT power of two and every round is byes-free: every survivor won a dual to
    get there.
  * Regionals is always the round where 32 teams enter, Zonals always 16 -- the
    downstream shape doesn't vary by classification size, only how many rounds of
    Sectionals (and whether there's a Wards round at all) lead into it.

`test_jhsaa_toc.py` covers the Tournament of Champions this same way; this file is
the ladder's own counterpart, reusing its fixture pattern (two districts per
classification, so a full run stays a few seconds).
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
               "arc": wd.get_jhsaa(w["id"], w["year"], "girls")}
    finally:
        jh.load_schools = real_load
        jh._season_cache.clear()
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready
        wd.is_primed, wd.prime = real_primed, real_prime


def _groups(archived):
    """(group, sectional, state) for every classification, from the real archive."""
    arc = archived["arc"]
    for g in jh.GROUPS:
        yield g, arc["sectionals"][g], arc["brackets"][g]


# --- the byes-free promise -------------------------------------------------------

def test_the_ladder_from_wards_on_is_byes_free(archived):
    """Every round from the combined field through the Final: games*2 == alive, no
    exceptions — nobody advances on the ladder without winning a dual."""
    for g, sec, state in _groups(archived):
        alive = len(state["field"])
        for games in state["rounds"]:
            assert len(games) * 2 == alive, (g, alive, len(games))
            alive -= len(games)
        assert alive == 1


def test_the_state_field_is_always_a_power_of_two(archived):
    for g, sec, state in _groups(archived):
        n = len(state["field"])
        assert n & (n - 1) == 0, (g, n)
        assert n == jh.ladder_entry(len(sec["field"]) + n - len(sec["survivors"]))


# --- protection: skip Sectionals only, never more ---------------------------------

def test_protected_teams_never_appear_in_the_sectional_field(archived):
    """A district's automatic bids join the ladder at Wards/Regionals — they never
    play a Sectional dual at all."""
    for g, sec, state in _groups(archived):
        protected = set(state["field"]) - set(sec["survivors"])
        assert protected.isdisjoint(sec["field"]), g


def test_sectional_survivors_plus_protected_equal_the_state_field(archived):
    """Nobody is invented or dropped recombining the two halves of the ladder."""
    for g, sec, state in _groups(archived):
        protected = set(state["field"]) - set(sec["survivors"])
        assert protected | set(sec["survivors"]) == set(state["field"])
        assert len(protected) + len(sec["survivors"]) == len(state["field"])


# --- ladder stage names (world.py) -------------------------------------------------

def test_regionals_and_zonals_are_named_rounds(archived):
    assert wd._round_label(32) == "Regionals"
    assert wd._round_label(16) == "Zonals"
    assert wd._round_label(8) == "Quarterfinals"
    assert wd._round_label(64) == "Wards"


def test_jhsaa_state_rounds_uses_the_ladder_names(archived):
    for g, sec, state in _groups(archived):
        rounds = wd.jhsaa_state_rounds(state)
        names = {r["alive"]: r["name"] for r in rounds}
        if 32 in names:
            assert names[32] == "Regionals"
        if 16 in names:
            assert names[16] == "Zonals"


# --- postseason results, both halves of the ladder ---------------------------------

def test_sectional_eliminated_teams_get_a_sectionals_finish(archived):
    found_one = False
    for g, sec, state in _groups(archived):
        eliminated = set(sec["field"]) - set(sec["survivors"])
        for name in eliminated:
            r = wd.jhsaa_postseason_result(sec, state, name)
            assert r == {"made_state": False, "seed": 0, "place": 0, "champion": False,
                        "played_sectional": True, "advanced": False,
                        "finish": "Sectionals"}
            found_one = True
    assert found_one


def test_protected_teams_report_played_sectional_false(archived):
    found_one = False
    for g, sec, state in _groups(archived):
        protected = set(state["field"]) - set(sec["survivors"])
        for name in protected:
            r = wd.jhsaa_postseason_result(sec, state, name)
            assert r["made_state"] is True
            assert r["played_sectional"] is False
            found_one = True
    assert found_one


def test_the_champion_reads_champion_true(archived):
    for g, sec, state in _groups(archived):
        r = wd.jhsaa_postseason_result(sec, state, state["champion"])
        assert r["champion"] is True
        assert r["finish"] == "Champion"


# --- the duals are TELLABLE APART in the archive, same promise the TOC makes -------

def test_sectional_duals_are_archived_under_their_own_phase(archived):
    conn = sqlite3.connect(archived["db"])
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT school, opp, won FROM world_jhsaa_dual"
                        " WHERE phase='sectional' AND gender='girls'").fetchall()
    conn.close()
    arc = archived["arc"]
    played = sum(len(r) for sec in arc["sectionals"].values() for r in sec["rounds"])
    assert len(rows) == 2 * played           # a dual sits on both sides' cards


def test_sectionals_stay_out_of_the_toss_rating(archived):
    season = jh.run_season("girls", archived["arc"]["season_year"], seed=0,
                           salt=wd.active_salt(wd.DEFAULT_SEED))
    rated = jh.rating_duals(list(season["teams"].values()))
    assert not any(d.get("phase") == "sectional" for d in rated)


def test_every_dual_a_sectional_survivor_played_is_on_its_record(archived):
    """The historically-buggy invariant (131/137 balanced, `docs/AAR-jhsaa-...`):
    every dual archived on a program's SCHEDULE must also be reflected in its
    RECORD. The ladder adds a whole new postseason stage in front of the old one —
    if Sectionals duals ever landed on the schedule after the record snapshot, this
    would silently reproduce that bug for every classification at once."""
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
