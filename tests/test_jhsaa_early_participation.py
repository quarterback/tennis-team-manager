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
    real_era, real_seat_era = jh.early_era, jh.early_seat_era
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
    # The fixture plays WHOLE cohorts (the rule's first shape, and what every
    # season archived before `early_seat_era()` keeps); the per-seat cut has its
    # own tests below, off rosters alone.
    jh.early_seat_era = lambda: 9999
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
        jh.early_era, jh.early_seat_era = real_era, real_seat_era
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
        # they grew (on the unrounded grade — the salt is fresh per world, and a
        # year's growth can sit inside one rounding step of the displayed OVR),
        # and the displayed ceiling never fell
        assert q._attrs().overall_grade() > p._attrs().overall_grade()
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


# --- the per-seat cut (owner rule 2026-09: "too many middle schoolers") -------

@pytest.fixture
def seat_cut(monkeypatch):
    """Both eras live from 2027 on the REAL association, no archive needed."""
    monkeypatch.setattr(jh, "early_era", lambda: 2027)
    monkeypatch.setattr(jh, "early_seat_era", lambda: 2027)
    monkeypatch.setattr(jh, "early_pot_era", lambda: 2027)   # the ranged intake, everywhere
    jh._season_cache.clear()
    yield "share-salt"
    jh._season_cache.clear()


def _gated(gender):
    return [s for s in jh.load_schools(gender) if s.classification in GATED]


def test_early_participants_are_a_small_share_of_a_gated_roster(seat_cut):
    """A handful of a roster, not the whole next two classes: at the ranged
    intake (`EARLY_SEAT_RATE_BAND` 12-21%, owner 2026-10) about two and a half
    a gated roster, 0-4 on most of them, and some rosters with none (measured on
    the real association: share 10.2%, mean 2.49, p90 4, 7% with none)."""
    salt = seat_cut
    total = early = 0
    per_roster = []
    for gender in ("girls", "boys"):
        for s in _gated(gender):
            r = jh.build_roster(s, 2027, salt)
            n = sum(1 for p in r if p.grade < 9)
            per_roster.append(n)
            total += len(r)
            early += n
    share = early / total
    assert 0.06 <= share <= 0.15, share
    assert 1.5 <= sum(per_roster) / len(per_roster) <= 3.5
    assert sum(1 for n in per_roster if n <= 4) / len(per_roster) >= 0.85
    assert any(n == 0 for n in per_roster) and any(n >= 1 for n in per_roster)


def test_the_cut_is_per_seat_same_odds_and_grandfathered(seat_cut):
    salt = seat_cut
    s = _gated("girls")[0]
    entry = 2029
    whole = jh.early_seasons(s, entry)
    assert whole == (2027, 2028)
    n = jh._freshman_class_size(s.key, entry, s.classification, salt)
    kept = [jh.early_seat_seasons(s, entry, seat, salt) for seat in range(n)]
    for k in kept:
        assert set(k) <= set(whole)
        assert 2027 not in k or 2028 in k          # a 7th-grader plays 8th too
    assert kept == [jh.early_seat_seasons(s, entry, seat, salt) for seat in range(n)]
    # the two grades roll on their own stream against the program's intake draw
    # for THAT season (a range, per program per season), the 7th-grade draw first
    import random
    r7, r8 = (jh.early_intake_rate(s, entry - 2, salt), jh.early_intake_rate(s, entry - 1, salt))
    for rate in (r7, r8):
        assert jh.EARLY_SEAT_RATE_BAND[0] <= rate <= jh.EARLY_SEAT_RATE_BAND[1]
    hits7 = hits8 = 0
    for seat in range(4000):
        r = random.Random(f"{salt}|jhsaa-early-seat|{s.key}|{entry}|{seat}")
        a, b = r.random() < r7, r.random() < r8
        hits7 += a
        hits8 += b
    assert abs(hits7 / 4000 - r7) < 0.03 and abs(hits8 / 4000 - r8) < 0.03
    # the roster carries exactly the seats whose roll came up
    on_8th = {p.jhsaa["seat"] for p in jh.build_roster(s, 2028, salt)
              if p.grade == 8 and p.entry_year == entry}
    assert on_8th == {i for i, k in enumerate(kept) if 2028 in k}
    on_7th = {p.jhsaa["seat"] for p in jh.build_roster(s, 2027, salt)
              if p.grade == 7 and p.entry_year == entry}
    assert on_7th == {i for i, k in enumerate(kept) if 2027 in k}
    assert on_7th <= on_8th


def test_seasons_before_the_seat_era_keep_the_whole_cohort(seat_cut, monkeypatch):
    """The gate is on the SEASON: an archived whole-cohort season rebuilds
    byte-identical, and a cohort that played 7th grade whole plays 8th whole."""
    salt = seat_cut
    s = _gated("boys")[0]
    sig = lambda r: [(p.pid, p.name, p.grade, round(p.current_overall(), 9)) for p in r]
    monkeypatch.setattr(jh, "early_seat_era", lambda: 9999)
    whole_27 = sig(jh.build_roster(s, 2027, salt))
    monkeypatch.setattr(jh, "early_seat_era", lambda: 2028)
    assert sig(jh.build_roster(s, 2027, salt)) == whole_27
    # entry 2029 played 7th in 2027 (whole) -> every seat is an 8th-grader in 2028
    n = jh._freshman_class_size(s.key, 2029, s.classification, salt)
    assert all(jh.early_seat_seasons(s, 2029, seat, salt) == (2027, 2028)
               for seat in range(n))
    # entry 2030's first early season is 2028 -> rolled
    m = jh._freshman_class_size(s.key, 2030, s.classification, salt)
    assert any(jh.early_seat_seasons(s, 2030, seat, salt) != (2028, 2029)
               for seat in range(m))


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


# --- what early participation buys (owner spec 2026-10) -----------------------

def test_every_early_season_rolls_a_development_share_on_a_range():
    """Nobody lands on nothing; playing time moves the RANGE, not a multiplier;
    two identical seasons can land apart; a grade not rostered rolls nothing."""
    bench, full = [], []
    for seat in range(400):
        b = jh.early_pot_rolls("S", 2104, seat, "", {8: jh.EXPO_FLOOR}, 9)
        f = jh.early_pot_rolls("S", 2104, seat, "", {8: 1.0}, 9)
        assert set(b) == {8} and 7 not in b
        lo, hi = jh.EARLY_DEV_BANDS[8][0]
        assert lo <= b[8]["dev"] <= hi
        lo, hi = jh.EARLY_DEV_BANDS[8][1]
        assert lo <= f[8]["dev"] <= hi
        assert b == jh.early_pot_rolls("S", 2104, seat, "", {8: jh.EXPO_FLOOR}, 9)
        bench.append(b[8]["dev"]); full.append(f[8]["dev"])
    assert min(full) > 0 and len(set(full)) > 100           # a range, not a number
    assert sum(full) / len(full) > sum(bench) / len(bench)  # playing time lifts the band
    # a 7th-grade season before the build's grade rolls; the grade itself never does
    assert set(jh.early_pot_rolls("S", 2104, 1, "", {7: 1.0, 8: 1.0}, 8)) == {7}
    assert jh.early_pot_rolls("S", 2104, 1, "", {7: 1.0, 8: 1.0}, 7) == {}
    assert jh.early_pot_rolls("S", 2104, 1, "", None, 12) == {}


def test_the_accelerator_chance_is_the_players_own_draw_and_the_exception_is_rare():
    """Every early participant in every early season draws their OWN chance from
    the band, rolls against it, and a hit draws its size independently — never
    one chance for a class, school, cohort or season (owner, 2026-10)."""
    chances, acc, exc, n = [], 0, 0, 0
    for seat in range(2000):
        r = jh.early_pot_rolls("S", 2104, seat, "", {7: 0.8, 8: 0.8}, 9)
        for g, v in r.items():
            n += 1
            assert jh.EARLY_ACCEL_CHANCE[0] <= v["chance"] <= jh.EARLY_ACCEL_CHANCE[1]
            chances.append(v["chance"])
            acc += bool(v["accel"]); exc += bool(v["exc"])
            if v["accel"]:
                assert jh.EARLY_ACCEL_BAND[0] <= v["accel"] <= jh.EARLY_ACCEL_BAND[1]
            if v["exc"]:
                assert jh.EARLY_EXCEPTION_BAND[0] <= v["exc"] <= jh.EARLY_EXCEPTION_BAND[1]
    assert len(set(chances)) > 1000                    # a draw per player-season
    # two players on the same roster, same season, hold different chances
    a = jh.early_pot_rolls("S", 2104, 0, "", {8: 0.8}, 9)[8]["chance"]
    b = jh.early_pot_rolls("S", 2104, 1, "", {8: 0.8}, 9)[8]["chance"]
    assert a != b
    assert 0.15 < acc / n < 0.25          # the band's middle, 20%
    assert 0.02 < exc / n < 0.07
    # a high chance can miss and a low one can hit — the size never reads the chance
    rows = [v for seat in range(2000) for v in jh.early_pot_rolls("S", 2104, seat, "", {8: 0.8}, 9).values()]
    assert any(v["chance"] > 0.28 and not v["accel"] for v in rows)
    assert any(v["chance"] < 0.12 and v["accel"] > 0.2 for v in rows)


def test_the_rolls_run_the_career_higher_and_the_off_path_is_byte_identical():
    early = {7: 1.0, 8: 1.0}
    base = [jh.career_ability("S", 2104, 3, g, "", 60.0, early=early) for g in (9, 10, 11, 12)]
    same = [jh.career_ability("S", 2104, 3, g, "", 60.0, early=early, early_pot={})
            for g in (9, 10, 11, 12)]
    assert base == same
    lifted = [jh.career_ability("S", 2104, 3, g, "", 60.0, early=early,
                                early_pot=jh.early_pot_total(
                                    jh.early_pot_rolls("S", 2104, 3, "", early, g)))
              for g in (9, 10, 11, 12)]
    assert all(l >= b for l, b in zip(lifted, base))
    # realised over the years left, so the senior gap exceeds the freshman gap
    assert lifted[3] - base[3] > lifted[0] - base[0] > 0


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
        # the row's seat is the FINAL projection: a later mover may have pushed
        # him down the ladder, never off it, so it is at best the seat he took
        assert m["rank"] >= min(o["rank"] for o in m["options"])
        assert order[m["tier"]] >= 0


def _slate_teams(archived, data, gender):
    """Every team of `gender` with the slate's moves applied, the way the roster
    build will apply them once committed."""
    w, salt = archived["world"], archived["salt"]
    prior = wd.jhsaa_prior_for_season(2028, gender, w["id"])
    staff = wd.jhsaa_staff_for_season(2028, gender, w["id"])
    teams = {t.school.name: t for t in jh.district_teams(jh.load_schools(gender), 2028, salt,
                                                       prior=prior, staff=staff)}
    for m in [x for x in data["moves"] if x["gender"] == gender]:
        p = next(x for x in teams[m["from"]].roster if x.pid == m["pid"])
        teams[m["from"]] = jp._without(teams[m["from"]], m["pid"])
        teams[m["to"]] = jp._with(teams[m["to"]], p, prior, 2028, salt)
    return teams


def test_every_emitted_mover_holds_a_v1_seat_with_the_whole_slate_applied(archived, proposal):
    """The finding: a mover pushed off his seat by a later placement was still
    proposed to it. Now a row is emitted only if the FINAL ladder seats him."""
    for gender in ("girls", "boys"):
        teams = _slate_teams(archived, proposal, gender)
        for m in [x for x in proposal["moves"] if x["gender"] == gender]:
            r = jp.v1_rank(teams[m["to"]], m["pid"])
            assert r is not None, m
            assert m["rank"] == r + 1
    for s in proposal["stays"]:
        assert s["pid"] not in {m["pid"] for m in proposal["moves"]}
        assert "ovr" in s and "ladder" in s        # export keeps the number; the page never shows it


def test_a_redirect_is_reprojected_and_a_bad_one_is_refused(archived, proposal):
    w, salt = archived["world"], archived["salt"]
    m = next(x for x in proposal["moves"] if len(x["options"]) > 1)
    alt = next(o for o in m["options"] if o["school"] != m["to"])
    data = jp.build(w["id"], 2028, salt, {m["pid"]: {"to": alt["school"]}})
    r = next(x for x in data["moves"] if x["pid"] == m["pid"])
    assert r["to"] == alt["school"] and r["redirected"]
    teams = _slate_teams(archived, data, m["gender"])
    assert jp.v1_rank(teams[alt["school"]], m["pid"]) == r["rank"] - 1
    # two redirects onto one seat: both must still project, or the second fails
    others = [x for x in data["moves"] if x["pid"] != m["pid"] and x["gender"] == m["gender"]]
    if others:
        o2 = others[0]
        data2 = jp.build(w["id"], 2028, salt, {m["pid"]: {"to": alt["school"]},
                                               o2["pid"]: {"to": alt["school"]}})
        teams2 = _slate_teams(archived, data2, m["gender"])
        # one gender: a school NAME is shared by its boys' and girls' teams
        for x in [y for y in data2["moves"] if y["gender"] == m["gender"]]:
            assert jp.v1_rank(teams2[x["to"]], x["pid"]) is not None
    # a school outside every tier is refused, and the row says so
    home_area = teams[m["from"]].school.area
    out_of_reach = {home_area, *proposal["neighbors"].get(home_area, ())}
    far = next((s.name for s in jh.load_schools(m["gender"])
                if s.area not in out_of_reach), None)
    if far:
        data3 = jp.build(w["id"], 2028, salt, {m["pid"]: {"to": far}})
        rows = [x for x in data3["moves"] + data3["stays"] if x["pid"] == m["pid"]]
        assert rows and rows[0].get("redirect_failed") == far
        assert rows[0].get("to") != far
    # a drop never enters placement
    data4 = jp.build(w["id"], 2028, salt, {m["pid"]: {"drop": True}})
    assert m["pid"] not in {x["pid"] for x in data4["moves"]}
    assert next(x for x in data4["stays"] if x["pid"] == m["pid"])["dropped"]


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
    # ‼️ AN EDIT NEVER REBUILDS THE SLATE (owner, 2026-09: "if i remove a kid it
    # repolls for each single kid"): a drop, a redirect and an undo are overlaid
    # on the stored proposal; only "Rebuild proposal" and the commit call `build`.
    real_build = jp.build

    def no_build(*a, **k):
        raise AssertionError("an edit rebuilt the whole slate")
    jp.build = no_build
    try:
        jp.edit(w, victim["pid"], "drop")
        redirected = next((m for m in kept if len(m["options"]) > 1), None)
        if redirected:
            alt = next(o for o in redirected["options"] if o["school"] != redirected["to"])
            jp.edit(w, redirected["pid"], "to", alt["school"])
            jp.edit(w, redirected["pid"], "reset")
            assert redirected["pid"] not in jp.pending(w["id"])["edits"]
            jp.edit(w, redirected["pid"], "to", alt["school"])
    finally:
        jp.build = real_build
    final = jp.final_moves(jp.pending(w["id"]))
    assert victim["pid"] not in {m["pid"] for m in final}
    if redirected:
        r = next(m for m in final if m["pid"] == redirected["pid"])
        assert r["to"] == alt["school"] and r["redirected"]
    # the page renders the open proposal — SCOPED to the victim's sport and class,
    # grouped by origin district, and with no rating on it
    html = archived["client"].get(f"/jhsaa/portal?g={victim['gender']}"
                                  f"&group={victim['from_class']}").get_data(as_text=True)
    assert "Commit" in html and victim["name"] in html and "dropped by you" in html
    assert victim["from_district"] in html
    assert "Pot est." not in html and ">OVR<" not in html
    other_class = [m for m in moves if m["from_class"] != victim["from_class"]
                   and m["gender"] == victim["gender"]]
    if other_class:
        assert other_class[0]["name"] not in html
    for cls in GATED:                      # the rail is the three gated classes
        assert cls in html
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


def test_an_early_graders_transfer_record_moves_them_only_where_they_may_go(archived):
    """P2: transfer records apply to 7th/8th-grade rosters. A move to another
    gated program takes effect; a move to a program that cannot roster an early
    participant is ignored for that season — the player stays, never vanishes."""
    salt = archived["salt"]
    origin = _one("girls", "Group 3")
    p = next(x for x in jh.build_roster(origin, 2027, salt) if x.grade == 7)
    gated = next(s for s in jh.load_schools("girls")
                 if s.classification in GATED and s.name != origin.name)
    opened = _one("girls", OPEN)
    rec = {"entry": p.entry_year}
    assert jh.is_enrolled(rec, 2027) and jh.is_enrolled(rec, p.entry_year + 3)
    assert not jh.is_enrolled(rec, 2026) and not jh.is_enrolled(rec, p.entry_year + 4)
    try:
        ov.set_jhsaa_transfer(p.pid, origin.name, "girls", p.entry_year,
                              p.jhsaa["seat"], gated.name, 2027)
        jh.reset_schools()
        assert p.pid not in {x.pid for x in jh.build_roster(origin, 2027, salt)}
        moved = next(x for x in jh.build_roster(gated, 2027, salt) if x.pid == p.pid)
        assert moved.grade == 7 and moved.name == p.name
        ov.clear_jhsaa_transfer(p.pid)
        ov.set_jhsaa_transfer(p.pid, origin.name, "girls", p.entry_year,
                              p.jhsaa["seat"], opened.name, 2027)
        jh.reset_schools()
        assert p.pid in {x.pid for x in jh.build_roster(origin, 2027, salt)}
        assert p.pid not in {x.pid for x in jh.build_roster(opened, 2027, salt)}
    finally:
        ov.clear_jhsaa_transfer(p.pid)
        jh.reset_schools()


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
