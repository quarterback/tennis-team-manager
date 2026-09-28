"""EARLY PARTICIPATION + MATURITY + THE RISING-FRESHMAN PORTAL (JHSAA rule 2100).

Over a REAL archived season (the `test_jhsaa_toc` fixture shape: the association cut
to a few districts per class, every code path the real one), with the era pulled
back to the fixture's season so the mechanic is live. See
`docs/AAR-jhsaa-early-participation.md`.
"""
import collections
import os

import pytest

from app import dbpath

from app import jhsaa as jh
from app import jhsaa_portal as jp
from app import overrides as ov
from app import world as wd
from app.web import state as st
from app.web.server import create_app

GATED = jh.EARLY_CLASSES
OPEN = "5A"


@pytest.fixture(scope="module")
def archived(tmp_path_factory):
    """One JHSAA season (2027) archived with early participation LIVE from 2027."""
    db = str(tmp_path_factory.mktemp("jhsaa") / "early.db")
    real_load, real_db, real_ready = jh.load_schools, wd.WORLD_DB, wd._schema_ready_for
    real_era = jh.early_era
    # ‼️ ONE FILE for the archive (`wd.WORLD_DB`), the exposure odometer and the
    # transfer ledger (both resolve through `dbpath.resolve_db_path`): split across
    # two, the odometer reads "no world" and every early season realises as if
    # unplayed — the same hermeticity rule the root conftest enforces.
    real_env = os.environ.get("TENNIS_DB_PATH")
    os.environ["TENNIS_DB_PATH"] = db
    dbpath._resolved.clear()

    def small(gender):
        out = []
        for grp in jh.GROUPS:
            names = sorted({s.district for s in real_load(gender) if s.group == grp})
            pool, keep = [], set()
            for name in names:
                keep.add(name)
                pool = [s for s in real_load(gender)
                        if s.group == grp and s.district in keep]
                if len(pool) > jh.PROTECTED + 8:
                    break
            out += pool
        return out

    real_primed, real_prime = wd.is_primed, wd.prime
    real_fields = dict(jh.STATE_FIELD)
    for grp, real in real_fields.items():
        jh.STATE_FIELD[grp] = {24: 24, 32: 16, 40: 20}[real]
    jh.load_schools = small
    jh.early_era = lambda: 2027            # the `exchange_era` idiom
    jh._season_cache.clear()
    wd.WORLD_DB = db
    wd._schema_ready_for = None
    jh.reset_schools()                     # nothing memoised against the old path
    try:
        # Split-brained, every archive read below silently answers "no world".
        assert os.path.realpath(dbpath.resolve_db_path()) == os.path.realpath(db)
        w = wd.get_or_create(wd.DEFAULT_SEED)
        wd.run_jhsaa(wd.DEFAULT_SEED, w)
        wd.is_primed = lambda *a, **k: True
        wd.prime = lambda *a, **k: None
        yield {"db": db, "world": w, "salt": wd.active_salt(w["seed"]),
               "client": create_app().test_client()}
    finally:
        jh.load_schools = real_load
        jh.early_era = real_era
        jh.STATE_FIELD.clear()
        jh.STATE_FIELD.update(real_fields)
        jh._season_cache.clear()
        if real_env is None:
            os.environ.pop("TENNIS_DB_PATH", None)
        else:
            os.environ["TENNIS_DB_PATH"] = real_env
        dbpath._resolved.clear()
        jh.reset_schools()
        wd.WORLD_DB, wd._schema_ready_for = real_db, real_ready
        wd.is_primed, wd.prime = real_primed, real_prime


def _one(gender, cls):
    return next(s for s in jh.load_schools(gender) if s.classification == cls)


# --- who is on a roster --------------------------------------------------------

def test_gated_classes_roster_7th_and_8th_graders_and_nobody_else_does(archived):
    salt = archived["salt"]
    for cls in GATED:
        grades = collections.Counter(p.grade for p in jh.build_roster(_one("girls", cls), 2027, salt))
        assert grades[7] > 0 and grades[8] > 0, (cls, grades)
    grades = collections.Counter(p.grade for p in jh.build_roster(_one("girls", OPEN), 2027, salt))
    assert 7 not in grades and 8 not in grades


def test_an_early_participant_is_the_same_person_as_the_freshman_they_become(archived):
    salt = archived["salt"]
    s = _one("boys", "1A")
    eighth = {p.pid: p for p in jh.build_roster(s, 2027, salt) if p.grade == 8}
    ninth = {p.pid: p for p in jh.build_roster(s, 2028, salt) if p.grade == 9}
    assert eighth and set(eighth) <= set(ninth)
    for pid, p in eighth.items():
        q = ninth[pid]
        assert q.name == p.name and q.entry_year == p.entry_year == 2028
        # they grew, and the displayed ceiling never fell
        assert q.current_overall() > p.current_overall()
        assert q.ceiling_overall() >= p.ceiling_overall() - 1e-9


def test_the_gate_reads_classification_not_group(archived):
    """A 1A program playing up is still a 1A-sized school."""
    import dataclasses
    s = dataclasses.replace(_one("girls", "1A"), group="2A")
    assert jh.early_seasons(s, 2029) == (2027, 2028)
    big = dataclasses.replace(_one("girls", OPEN), group="1A")
    assert jh.early_seasons(big, 2029) == ()


def test_before_the_era_and_outside_the_gate_nothing_changes(archived):
    """Rosters that predate the era, and non-gated programs' rosters in a season
    with no archived maturity season behind it, are byte-identical with the
    mechanic on or off."""
    salt = archived["salt"]
    sig = lambda r: [(p.pid, p.name, p.grade, round(p.current_overall(), 9),
                      round(p.ceiling_overall(), 9)) for p in r]
    on = sig(jh.build_roster(_one("boys", OPEN), 2027, salt))
    live, jh.early_era = jh.early_era, (lambda: 9999)
    try:
        off_open = sig(jh.build_roster(_one("boys", OPEN), 2027, salt))
        off_gated = sig(jh.build_roster(_one("boys", "1A"), 2026, salt))
    finally:
        jh.early_era = live
    assert on == off_open
    assert sig(jh.build_roster(_one("boys", "1A"), 2026, salt)) == off_gated


def test_early_participants_dress_and_their_seasons_reach_the_archive(archived):
    """They are ordinary players to the season: some of them played (varsity or
    JV) and the odometer sees it; the career rebuild leads with the early years."""
    salt = archived["salt"]
    s = _one("girls", "2A")
    early = [p for p in jh.build_roster(s, 2027, salt) if p.grade < 9]
    units = jh.school_exposure("girls", s.name, (2027,))[2027]
    if units is None:                      # self-diagnosing: one run tells the story
        import sqlite3
        con = sqlite3.connect(archived["db"])
        n = con.execute("SELECT COUNT(*) FROM world_jhsaa_dual WHERE gender='girls'"
                        " AND year=0 AND (school=? OR opp=?)", (s.name, s.name)).fetchone()
        raise AssertionError(f"odometer None for {s.name!r}: rows={n} wid_memo={jh._expo_world}"
                             f" resolved={dbpath.resolve_db_path()} WORLD_DB={wd.WORLD_DB}"
                             f" db={archived['db']} cache_keys="
                             f"{[k for k in jh._expo_cache if k[2] == s.name]}")
    assert any(units.get(p.name, 0) > 0 for p in early)
    p = next(x for x in early if x.grade == 7)
    rows = jh.career(s.name, "girls", p.name, 2029 + 3, salt)
    assert [r["grade"] for r in rows][:3] == [7, 8, 9]


# --- maturity ------------------------------------------------------------------

def test_maturity_is_off_for_everyone_with_no_played_season():
    assert jh.maturity_events("S", 2040, 1, 12, "", {}) == {}
    assert jh.career_ability("S", 2040, 1, 12, "", 60.0) == \
        jh.career_ability("S", 2040, 1, 12, "", 60.0, bloom={})


def test_maturity_is_deterministic_gated_per_grade_and_capped():
    hits = 0
    for seat in range(400):
        ev = jh.maturity_events("S", 2040, seat, 12, "", {7: 1.0, 8: 1.0, 9: 1.0})
        assert ev == jh.maturity_events("S", 2040, seat, 12, "", {7: 1.0, 8: 1.0, 9: 1.0})
        for g, (pot, spurt) in ev.items():
            assert 0 < pot <= jh.MATURITY_POT_CAP[g]
            assert 0 < spurt <= jh.MATURITY_POT_CAP[g] * jh.MATURITY_SPURT[1]
        # a grade not played never fires; a later grade cut never fires
        assert 9 not in jh.maturity_events("S", 2040, seat, 12, "", {7: 1.0, 8: 1.0})
        assert jh.maturity_events("S", 2040, seat, 9, "", {7: 1.0, 8: 1.0, 9: 1.0}).keys() <= {7, 8}
        hits += bool(ev)
    assert 0 < hits < 400                       # some bloom, most do not


def test_playing_time_moves_the_odds_and_results_never_enter():
    """Same players, same seed: full seasons fire at least as often as bench ones."""
    full = sum(bool(jh.maturity_events("S", 2040, s, 12, "", {9: 1.0})) for s in range(600))
    bench = sum(bool(jh.maturity_events("S", 2040, s, 12, "", {9: 0.1})) for s in range(600))
    assert full > bench > 0
    # the signature has no place for a record — `played` is the only input


def test_a_reveal_lifts_pot_and_a_spurt_lifts_ovr_independently():
    base = [jh.career_ability("S", 2041, 2, g, "", 60.0) for g in (9, 10, 11, 12)]
    reveal = [jh.career_ability("S", 2041, 2, g, "", 60.0, bloom={9: (0.15, 0.0)})
              for g in (9, 10, 11, 12)]
    spurt = [jh.career_ability("S", 2041, 2, g, "", 60.0, bloom={9: (0.0, 0.03)})
             for g in (9, 10, 11, 12)]
    assert reveal[0] == base[0] and spurt[0] == base[0]     # the 9th-grade season itself
    assert all(r >= b for r, b in zip(reveal, base)) and reveal[3] > base[3]
    assert spurt[1] - base[1] == pytest.approx(0.03 * 60.0 * 1.0, abs=60.0 * 0.03)
    assert spurt[1] > base[1]


def test_the_7th_to_8th_reveal_is_capped_at_six_percent():
    assert jh.MATURITY_POT_CAP[7] == 0.06
    assert jh.MATURITY_POT_CAP[8] > jh.MATURITY_POT_CAP[7]
    assert jh.MATURITY_POT_CAP[9] >= jh.MATURITY_POT_CAP[8]


# --- the portal ----------------------------------------------------------------

@pytest.fixture(scope="module")
def proposal(archived):
    w, salt = archived["world"], archived["salt"]
    return jp.build(w["id"], 2028, salt)


def test_every_proposed_mover_had_no_v1_seat_and_every_destination_gives_one(archived, proposal):
    w, salt = archived["world"], archived["salt"]
    assert proposal["moves"], "the fixture produced nobody to move — resize it"
    for gender in ("girls", "boys"):
        schools = jh.load_schools(gender)
        prior = wd.jhsaa_prior_for_season(2028, gender, w["id"])
        staff = wd.jhsaa_staff_for_season(2028, gender, w["id"])
        teams = {t.school.name: t for t in jh.district_teams(schools, 2028, salt,
                                                           prior=prior, staff=staff)}
        for m in [x for x in proposal["moves"] if x["gender"] == gender]:
            assert m["from_class"] in GATED
            assert m["to"] != m["from"]
            assert m["tier"] in ("county", "area", "neighbor")
            assert 1 <= m["rank"] <= m["v1"]
            assert jp.v1_rank(teams[m["from"]], m["pid"]) is None
            # the player really played 8th grade for the origin
            p = next(x for x in teams[m["from"]].roster if x.pid == m["pid"])
            assert 2027 in p.jhsaa["early"] and p.grade == 9


def test_the_cascade_stops_at_the_first_tier_with_a_seat(proposal):
    order = {"county": 0, "area": 1, "neighbor": 2}
    for m in proposal["moves"]:
        tiers = {o["tier"] for o in m["options"]}
        assert tiers == {m["tier"]}, m
        assert m["rank"] == min(o["rank"] for o in m["options"])
        assert order[m["tier"]] >= 0


def test_the_hold_opens_edits_apply_and_a_commit_moves_the_player(archived):
    w = archived["world"]
    fake = {**w, "year": 1}                  # week 0 of the year whose season is 2028
    assert jp.due(fake)
    cur = jp.check_hold(fake)
    assert cur and cur["season"] == 2028 and cur["data"]["moves"]
    # the shell and both advance paths see it
    assert jp.pending(w["id"]) is not None
    with pytest.raises(wd.PortalHold):
        wd.advance_jhsaa_lab(wd.DEFAULT_SEED)
    moves = cur["data"]["moves"]
    victim, kept = moves[0], moves[1:]
    jp.edit(w, victim["pid"], "drop")
    redirected = next((m for m in kept if len(m["options"]) > 1), None)
    if redirected:
        alt = next(o for o in redirected["options"] if o["school"] != redirected["to"])
        jp.edit(w, redirected["pid"], "to", alt["school"])
    final = jp.final_moves(jp.pending(w["id"]))
    assert victim["pid"] not in {m["pid"] for m in final}
    if redirected:
        r = next(m for m in final if m["pid"] == redirected["pid"])
        assert r["to"] == alt["school"] and r["redirected"]
    # the page renders the open proposal
    html = archived["client"].get("/jhsaa/portal").get_data(as_text=True)
    assert "Commit" in html and victim["name"] in html
    res = jp.commit(w)
    assert res["ok"] and res["moves"] == len(final)
    assert jp.pending(w["id"]) is None
    m = final[0]
    rec = ov.get_jhsaa_transfer(m["pid"])
    assert rec and jh.transfer_school(rec, 2028) == m["to"]
    assert ov.get_jhsaa_transfer(victim["pid"]) is None
    salt = archived["salt"]
    dest = next(s for s in jh.load_schools(m["gender"]) if s.name == m["to"])
    origin = next(s for s in jh.load_schools(m["gender"]) if s.name == m["from"])
    assert m["pid"] in {p.pid for p in jh.build_roster(dest, 2028, salt)}
    assert m["pid"] not in {p.pid for p in jh.build_roster(origin, 2028, salt)}
    # and the 8th-grade season they already played is untouched
    assert m["pid"] in {p.pid for p in jh.build_roster(origin, 2027, salt)}
    assert [x["pid"] for x in jp.applied(w["id"])] == [x["pid"] for x in final]
    # released: the lab advance no longer holds on the portal
    assert not jp.due(fake)


def test_pages_render_for_a_7th_grader(archived):
    salt = archived["salt"]
    s = _one("girls", "Group 3")
    p = next(x for x in jh.build_roster(s, 2027, salt) if x.grade == 7)
    c = archived["client"]
    r = c.get(f"/jhsaa/player/{s.name}/{p.pid}?g=girls")
    assert r.status_code == 200 and p.name in r.get_data(as_text=True)
    r = c.get(f"/jhsaa/school/{s.name}?g=girls")
    assert r.status_code == 200
    # The page's roster snippet is the top SIX by OVR; the full roster model
    # carries the early grades and labels them by grade, not class year.
    view = st.jhsaa_school_view(wd.DEFAULT_SEED, "girls", s.name)
    grades = {row["grade"] for row in view["roster"]}
    assert {7, 8} <= grades
    assert st._JH_CLASS_YEAR[7] == "7th" and st._JH_CLASS_YEAR[8] == "8th"
