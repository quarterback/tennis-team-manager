"""JHSAA SPLIT SQUADS (rule 2097) — see `docs/AAR-jhsaa-split-squads.md`.

Deep, top-tier programs split their JV into V2/V3 squads that take non-district
dates against other programs' varsity. These pin the two gates, the year gate,
the formats, the pairing exclusions, the rating discount, the exclusion from the
nine computer ratings and the JV seeding record, and the archive columns."""
import random
import sqlite3

import pytest

from app import jhsaa as jh
from app import rating
from app import world as wd
from app import jhsaa_ratings as jr


# --- helpers -----------------------------------------------------------------

_REAL = None


def _real():
    global _REAL
    if _REAL is None:
        _REAL = jh.load_schools("girls")
    return _REAL


def _school(name, group="5A", district="Alpha League"):
    import dataclasses
    return dataclasses.replace(_real()[0], name=name, group=group,
                               classification=group, district=district, source="")


_POOL: list = []


def _players(n, offset):
    """`n` distinct real players, a different slice per `offset`."""
    i = 0
    while len(_POOL) < offset + n:
        for p in jh.build_roster(_real()[i], 2097, ""):
            if all(q.pid != p.pid for q in _POOL):
                _POOL.append(p)
        i += 1
    return list(_POOL[offset:offset + n])


_OFFSETS = {}


def _team(name, n=40, group="5A", district="Alpha League"):
    off = _OFFSETS.setdefault(name, sum(60 for _ in _OFFSETS))
    return jh.TeamSeason(school=_school(name, group, district), roster=_players(n, off))


@pytest.fixture
def tiers(monkeypatch):
    """Put named programs in chosen tiers without touching the seed file."""
    table = {}
    monkeypatch.setattr(jh, "program_band",
                        lambda school, entry=None: table.get(getattr(school, "name", school), "average"))
    return table


# --- 1. the gates ------------------------------------------------------------

def test_eligible_tiers_are_one_constant_and_never_volatile():
    assert jh.SQUAD_TIERS == ("power", "elite", "dynasty")
    assert not any(k.startswith("volatile") for k in jh.SQUAD_TIERS)
    keys = {t["key"] for t in jh.band_tiers()}
    assert set(jh.SQUAD_TIERS) <= keys


def test_both_gates_must_pass(tiers, monkeypatch):
    t = _team("Deep")
    for tier, depth, want in (("elite", 18, ["V2", "V3"]), ("elite", 17, ["V2"]),
                              ("dynasty", 11, ["V2"]), ("power", 10, []),
                              ("very_strong", 30, []), ("volatile_wide", 30, [])):
        tiers["Deep"] = tier
        monkeypatch.setattr(jh, "squad_depth", lambda ts, d=depth: d)
        assert jh.squad_eligible(t) == want, (tier, depth)


def test_depth_gate_counts_healthy_players_below_the_varsity_eleven(tiers):
    t = _team("Deep", n=11 + 18)
    tiers["Deep"] = "elite"
    assert jh.squad_depth(t) == 18
    assert jh.squad_eligible(t) == ["V2", "V3"]
    t.injuries[jh.jv_pool(t)[0].pid] = 3          # one hurt: 17 healthy
    assert jh.squad_depth(t) == 17
    assert jh.squad_eligible(t) == ["V2"]


def test_squad_pools_are_disjoint_slices_of_the_jv():
    t = _team("Deep", n=11 + 18)
    v2, v3 = jh.squad_pool(t, "V2"), jh.squad_pool(t, "V3")
    assert len(v2) == 11 and len(v3) == 7
    assert not {p.pid for p in v2} & {p.pid for p in v3}
    varsity = {p.pid for p in jh._order(t)[:11]}
    assert not varsity & {p.pid for p in v2 + v3}


# --- 2. year gate --------------------------------------------------------------

def test_nothing_is_fielded_before_2097(tiers):
    t = _team("Deep", n=11 + 18)
    tiers["Deep"] = "dynasty"
    assert jh.field_squads([t], 2096) == [] and t.squads == []
    got = jh.field_squads([t], jh.SPLIT_SQUAD_FROM)
    assert [s.squad for s in got] == ["V2", "V3"] and t.squads == got


# --- 3. formats ----------------------------------------------------------------

def test_squad_formats():
    v2, v3 = jh.SQUAD_FORMATS["V2"], jh.SQUAD_FORMATS["V3"]
    assert (v2.n_singles, v2.n_doubles) == (3, 4)
    assert (v3.n_singles, v3.n_doubles) == (3, 2)


@pytest.mark.parametrize("squad,courts", [("V2", 7), ("V3", 5)])
def test_a_squad_dual_plays_the_squad_format_and_credits_only_the_v1(squad, courts):
    host, sq_school = _team("Host", n=30), _team("Deep", n=11 + 18,
                                                  district="Beta League")
    sq = jh.SquadTeam(team=sq_school, squad=squad)
    jh.play_squad_dual(host, sq, seed=7)
    v1_row, sq_row = host.schedule[-1], sq.schedule[-1]
    assert len(v1_row["lines"]) == courts == len(sq_row["lines"])
    assert v1_row["opp_squad"] == squad and v1_row["level"] == "v"
    assert sq_row["squad"] == squad and sq_row["level"] == "jv"
    assert v1_row["won"] != sq_row["won"] and not v1_row["tied"]
    assert host.wins + host.losses == 1
    fmt = jh.SQUAD_FORMATS[squad]
    assert sum(sum(r[:2]) for r in host.records.values()) == fmt.n_singles + 2 * fmt.n_doubles
    # The squad's school is untouched: no record, no matches, no schedule, no W-L.
    assert sq_school.records == {} and sq_school.matches == {}
    assert sq_school.schedule == [] and sq_school.wins == sq_school.losses == 0
    assert sq.wins + sq.losses == 1


def test_the_v1_gets_no_rest_or_rotation_relief():
    """`_squad_v1_lineup` dresses the healthy top of the ladder, every time."""
    t = _team("Host", n=30)
    top = {p.pid for p in jh._order(t)[:11]}
    for seed in range(20):
        got = jh._squad_v1_lineup(t, jh.SQUAD_FORMATS["V2"], random.Random(seed))
        assert {p.pid for p in got} == top


# --- 4. pairing ----------------------------------------------------------------

def _pairs_seen(pool, n=80):
    seen = set()
    for seed in range(n):
        owed = {id(t): 3 for t in pool}
        played = {id(t): set() for t in pool}
        for x, y in jh._nondistrict_pairs(pool, random.Random(seed), owed, played):
            xs, ys = jh._is_squad(x), jh._is_squad(y)
            if xs or ys:
                assert x.school.name != y.school.name                  # never own school
                if xs != ys:                                           # squad v V1:
                    assert x.school.group != y.school.group            # never own class
            else:                                                      # V1 v V1: never league
                assert (x.school.group, x.school.district) != (y.school.group, y.school.district)
            seen.add(frozenset(((x.school.name, xs), (y.school.name, ys))))
    return seen


def test_pairing_rules():
    a = _team("A", district="L1", group="9A")
    b = _team("B", district="L1", group="9A")          # a's league mate
    g = _team("G", district="L9", group="9A")          # same class, other league
    c = _team("C", district="L2", group="1A")          # far smaller class
    e = _team("E", district="L4", group="5A")
    sa, sb, se = (jh.SquadTeam(team=t, squad="V2") for t in (a, b, e))
    seen = _pairs_seen([a, b, g, c, e, sa, sb, se])
    # A squad never meets a V1 in its own class, league mate or not...
    for v1 in ("B", "G"):
        assert frozenset({("A", True), (v1, False)}) not in seen
    # ...but may meet another program's squad, and a V1 of any other class.
    assert frozenset({("A", True), ("B", True)}) in seen
    assert frozenset({("A", True), ("C", False)}) in seen
    # V1s have no class gate either (owner rule 2097).
    assert any(not any(sq for _, sq in p) and {n for n, _ in p} == {"A", "C"} for p in seen)


def test_squad_vs_squad_is_jv_on_both_sides():
    x, y = _team("X", n=30), _team("Y", n=30, district="Beta")
    sx, sy = jh.SquadTeam(team=x, squad="V2"), jh.SquadTeam(team=y, squad="V3")
    jh.play_squad_dual(sx, sy, seed=4)
    r1, r2 = sx.schedule[-1], sy.schedule[-1]
    assert r1["level"] == r2["level"] == "jv" and r1["shape"] == "3S/2D"
    assert (r1["squad"], r1["opp_squad"]) == ("V2", "V3") and r1["won"] != r2["won"]
    assert x.records == {} and y.records == {} and x.schedule == y.schedule == []


# --- 5. rating discounts ---------------------------------------------------------

def test_discount_values():
    assert jh.SQUAD_DISCOUNT == {"V2": 0.61, "V3": 0.39}


def _duals(factor=None):
    lines = [{"slot": "S1", "home_won": True, "home_games": 12, "away_games": 3}]
    out = [{"home": "X", "away": "Y", "home_won": True, "lines": lines},
           {"home": "Y", "away": "Z", "home_won": True, "lines": lines},
           {"home": "Z", "away": "X", "home_won": False, "lines": lines}]
    sq = {"home": "V1", "away": "X", "home_won": True, "lines": lines}
    if factor is not None:
        sq.update(squad_side="away", squad_factor=factor)
    return out + [sq, {"home": "V1", "away": "Z", "home_won": False, "lines": lines}]


def test_toss_reads_the_squads_school_at_the_discount_and_never_rates_the_squad():
    plain = rating.compute_ratings(_duals())            # as if V1 beat X's varsity
    v2 = rating.compute_ratings(_duals(0.61))
    v3 = rating.compute_ratings(_duals(0.39))
    # X's own record never sees the squad dual.
    assert (v2["X"].wins, v2["X"].losses) == (2, 0)
    assert (plain["X"].wins, plain["X"].losses) == (2, 1)
    # The V1 keeps the win, against a discounted opponent.
    assert (v2["V1"].wins, v2["V1"].losses) == (1, 1)
    assert v3["V1"].pi_raw < v2["V1"].pi_raw


def test_factor_one_is_bit_for_bit_the_old_arithmetic():
    duals = _duals()[:3]
    a = rating.compute_ratings(duals)
    b = rating.compute_ratings([{**d, "squad_factor": 1.0} for d in duals])
    assert {k: v.pi_raw for k, v in a.items()} == {k: v.pi_raw for k, v in b.items()}


def test_oowp_reads_the_squads_school_at_the_discount():
    a, x = _team("A", district="L1"), _team("X", district="L2")
    x.wins, x.losses = 8, 2
    a.schedule.append({"opp": "X", "phase": "regular", "opp_squad": "V2"})
    x.schedule.append({"opp": "A", "phase": "regular"})
    a.wins = 1
    oowp = jh.district_oowp([a, x])
    # X's opponents' win% is A's (1.0); A's opponents' opponents is X's owp × 0.61.
    assert oowp["A"] == pytest.approx(1.0 * 0.61)


def test_rating_duals_marks_the_squad_side_from_the_v1_row():
    host = _team("Host", n=30)
    sq = jh.SquadTeam(team=_team("Deep", n=29, district="Beta"), squad="V3")
    jh.play_squad_dual(sq, host, seed=3)                # the squad hosts
    rows = jh.rating_duals([host])
    assert len(rows) == 1
    r = rows[0]
    assert r["home"] == "Deep" and r["away"] == "Host"
    assert r["squad_side"] == "home" and r["squad_factor"] == 0.39


# --- 6. the nine computer ratings exclude squad duals ----------------------------

def test_computer_ratings_exclude_squad_duals():
    host, other = _team("Host", n=30), _team("Deep", n=29, district="Beta")
    jh.play_squad_dual(host, jh.SquadTeam(team=other, squad="V2"), seed=5)
    assert jr.dual_rows([host, other]) == []
    jh.play_dual(host, other, seed=9)
    assert len(jr.dual_rows([host, other])) == 1


# --- 7. JV seeding record excludes squad results ---------------------------------

def test_squad_results_stay_out_of_the_jv_seeding_record():
    t = _team("Deep", n=29)
    sq = jh.SquadTeam(team=t, squad="V2", wins=3, losses=1,
                      schedule=[{"opp": "H", "squad": "V2", "level": "jv",
                                 "won": True, "played": ["a"]}])
    jvt = jh.JVTeam(team=t, wins=5, losses=2)
    jh._fold_squads({"Deep": jvt}, [sq])
    assert (jvt.wins, jvt.losses) == (5, 2)             # what JV Regions/State seed on
    assert (jvt.squad_wins, jvt.squad_losses) == (3, 1)
    assert jvt.schedule[-1]["squad"] == "V2"            # ...but on the JV tab
    # the aggregate JV record shown on the tab folds both (the archive fold)
    rows = [{"level": "jv", "won": True}] * 5 + [{"level": "jv", "won": False}] * 2
    rows += [{"level": "jv", "won": True, "squad": "V2"}] * 3 + [{"level": "jv", "won": False, "squad": "V2"}]
    assert wd.jhsaa_jv_record(rows) == (8, 3, 0)


def test_jv_state_seeds_on_the_record_that_excludes_squads():
    from app import jhsaa_jv_state as js
    import inspect
    src = inspect.getsource(js)
    assert "squad_wins" not in src                      # never read by the draw


# --- 8. archive ----------------------------------------------------------------

def test_archive_columns_and_both_rows_keep_the_box_score(tmp_path, monkeypatch):
    db = str(tmp_path / "sq.db")
    monkeypatch.setattr(wd, "WORLD_DB", db)
    monkeypatch.setattr(wd, "_schema_ready_for", None)
    wd.init_schema()
    cols = {r[1]: r[4] for r in sqlite3.connect(db).execute(
        "PRAGMA table_info(world_jhsaa_dual)")}
    assert cols["squad"] == "''" and cols["opp_squad"] == "''"
    v1 = {"home": False, "opp_squad": "V2", "lines": [{"slot": "S1"}]}
    sq = {"home": True, "squad": "V2", "lines": [{"slot": "S1"}]}
    assert wd.unpack_lines(wd._archive_lines(v1)) == [{"slot": "S1"}]
    assert wd.unpack_lines(wd._archive_lines(sq)) == [{"slot": "S1"}]
    assert wd._archive_lines({"home": False, "lines": [{"slot": "S1"}]}) is None


def test_old_database_gains_the_columns(tmp_path, monkeypatch):
    db = str(tmp_path / "old.db")
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE world_jhsaa_dual (world_id INTEGER, year INTEGER,"
              " gender TEXT, school TEXT, opp TEXT, home INTEGER, phase TEXT,"
              " pf REAL, pa REAL, won INTEGER, district INTEGER)")
    c.execute("INSERT INTO world_jhsaa_dual VALUES (1,1,'girls','A','B',1,'regular',4,3,1,0)")
    c.commit(); c.close()
    monkeypatch.setattr(wd, "WORLD_DB", db)
    monkeypatch.setattr(wd, "_schema_ready_for", None)
    wd.init_schema()
    row = sqlite3.connect(db).execute(
        "SELECT squad, opp_squad FROM world_jhsaa_dual").fetchone()
    assert row == ("", "")


def test_the_match_key_separates_a_squad_dual_and_matches_from_both_rows():
    v1 = {"school": "A", "opp": "B", "home": True, "phase": "regular",
          "district": 0, "level": "v", "opp_squad": "V2"}
    sq = {"school": "B", "opp": "A", "home": False, "phase": "regular",
          "district": 0, "level": "jv", "squad": "V2"}
    plain = {"school": "A", "opp": "B", "home": True, "phase": "regular",
             "district": 0, "level": "v"}
    assert wd.jh_match_key(v1) == wd.jh_match_key(sq) == ("sq", "regular", 0, "A", "B#V2")
    assert wd.jh_match_key(plain) == ("v", "regular", 0, "A", "B")
    assert len(wd.jh_match_key(v1)) == 5


# --- 9. pre-2097 identity -------------------------------------------------------

def _small_season(year, monkeypatch, tiers_on):
    import hashlib, json
    if tiers_on:
        monkeypatch.setattr(jh, "program_band", lambda school, entry=None: "dynasty")
    names = sorted(jh.districts("girls", "5A"))[:3]
    by_group = {"5A": {d: jh.district_teams(jh.districts("girls", "5A")[d], year, "")
                       for d in names}}
    every, power = jh.play_regular_season(by_group, year, "girls", "")
    h = hashlib.sha256()
    for t in every:
        h.update(json.dumps([t.school.name, t.wins, t.losses, t.records, t.schedule],
                            sort_keys=True, default=str).encode())
    h.update(json.dumps(sorted((n, r.pi_raw) for n, r in power.items())).encode())
    return h.hexdigest(), every


def test_before_2097_the_season_is_identical_whoever_would_qualify(monkeypatch):
    """Every program forced into a squad tier changes NOTHING in a 2096 season —
    the year gate is the whole gate. (The digest-vs-main comparison lives in the
    AAR; this pins the gate itself.)"""
    base, _ = _small_season(2096, monkeypatch, tiers_on=False)
    forced, every = _small_season(2096, monkeypatch, tiers_on=True)
    assert base == forced
    assert not any(t.squads for t in every)
    assert not any(d.get("opp_squad") for t in every for d in t.schedule)


def test_from_2097_squads_play_and_never_a_same_class_v1(monkeypatch):
    """A one-class fixture: every V1 is in the squads' own class, so squads may
    only meet each other."""
    _, every = _small_season(2097, monkeypatch, tiers_on=True)
    assert not any(d.get("opp_squad") for t in every for d in t.schedule)
    rows = [r for t in every for s in t.squads for r in s.schedule]
    assert rows and all(r["opp_squad"] and r["level"] == "jv" for r in rows)

def _insert(db, rows):
    c = sqlite3.connect(db)
    c.executemany(
        "INSERT INTO world_jhsaa_dual (world_id, year, gender, school, opp, home,"
        " phase, pf, pa, won, district, lines, level, tied, shape, played, tiebreak,"
        " squad, opp_squad) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit(); c.close()


def test_archived_squad_dual_dates_schedules_and_head_to_head(tmp_path, monkeypatch):
    db = str(tmp_path / "arc.db")
    monkeypatch.setattr(wd, "WORLD_DB", db)
    monkeypatch.setattr(wd, "_schema_ready_for", None)
    wd.init_schema()
    wd._JH_CAL_CACHE.clear()
    ln = [{"slot": "S1", "home": ["Ann"], "away": ["Bea"], "score": "6-1, 6-1",
           "home_won": True}]
    pk = wd.pack_lines(ln)
    _insert(db, [
        # A (V1, home) beat B's V2 — the V1 row and the squad's JV row
        (1, 70, "girls", "A", "B", 1, "regular", 5, 2, 1, 0, pk, "v", 0, "3S/4D",
         "[]", "[]", "", "V2"),
        (1, 70, "girls", "B", "A", 0, "regular", 2, 5, 0, 0, pk, "jv", 0, "3S/4D",
         '["Bea"]', "[]", "V2", ""),
        # ...and A's varsity also met B's varsity, same phase
        (1, 70, "girls", "A", "B", 1, "regular", 4, 3, 1, 0, pk, "v", 0, "",
         "[]", "[]", "", ""),
        (1, 70, "girls", "B", "A", 0, "regular", 3, 4, 0, 0, None, "v", 0, "",
         "[]", "[]", "", ""),
    ])
    dates = wd.jhsaa_match_dates(1, 70, "girls", 2097)
    assert ("sq", "regular", 0, "A", "B#V2") in dates      # its own identity + date
    assert ("v", "regular", 0, "A", "B") in dates
    # Head-to-head between the two VARSITIES sees one meeting, not the squad dual.
    monkeypatch.setattr(wd, "_relabel", lambda x: x, raising=False)
    meets = wd.jhsaa_prior_meetings(1, "girls", "A", "B")
    assert len(meets) == 1
    # B's schedule: the squad row is JV, carries its own box score and its label.
    rows = wd.jhsaa_schedule(1, 70, "girls", "B")
    sq = [r for r in rows if r.get("squad")]
    assert len(sq) == 1 and sq[0]["level"] == "jv" and sq[0]["lines"] == ln
    assert wd.jhsaa_jv_record(rows) == (0, 1, 0)             # aggregate JV record
