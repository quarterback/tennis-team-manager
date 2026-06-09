import pytest

import app.gtt_seasonmode as g


@pytest.fixture
def db(tmp_path):
    g.DB_PATH = str(tmp_path / "gtt.db")
    g._schema_ready_for = None
    g._roster_cache.clear()
    yield


def test_schedule_is_double_round_robin(db):
    lid = g.create_league("GTT", seed=2026, n_teams=6)
    s = g.load_league(lid)
    # double round-robin of 6 teams -> 2*(6-1) = 10 weeks
    assert s["total_weeks"] == 10
    assert s["phase"] == "regular"
    fr = g.franchises(lid)
    assert len(fr) == 6
    # each franchise plays every week of the regular season (no byes for even N)
    conn = g._db()
    for f in fr:
        n = conn.execute("SELECT COUNT(*) c FROM gtt_duals WHERE league_id=? AND round='REG'"
                         " AND (home=? OR away=?)", (lid, f["id"], f["id"])).fetchone()["c"]
        assert n == 10
    conn.close()


def test_franchises_have_editable_identity(db):
    lid = g.create_league("GTT", seed=3, n_teams=4)
    fr = g.franchises(lid)
    for f in fr:
        assert f["name"] and f["city"] and len(f["abbrev"]) == 3


def test_advance_populates_results_and_standings(db):
    lid = g.create_league("GTT", seed=7, n_teams=4)
    r = g.advance(lid, fidelity="fast")
    assert r["phase"] == "regular" and r["played"] > 0
    table = g.standings(lid)
    assert sum(row["w"] + row["l"] for row in table) == 2 * r["played"]   # each dual = 1 W + 1 L


def test_full_season_completes_with_champion(db):
    lid = g.create_league("GTT", seed=11, n_teams=6)
    g.advance_all(lid, fidelity="fast")
    s = g.load_league(lid)
    assert s["phase"] == "complete"
    ch = g.champion(lid)
    assert ch is not None and ch["name"]
    # every regular-season dual resolved to exactly one win and one loss
    table = g.standings(lid)
    assert all(row["w"] + row["l"] == 10 for row in table)


def test_standings_sorted_by_wins_then_diff(db):
    lid = g.create_league("GTT", seed=5, n_teams=8)
    g.advance_all(lid, fidelity="fast")
    table = g.standings(lid)
    keys = [(row["w"], row["diff"]) for row in table]
    assert keys == sorted(keys, reverse=True)


def test_rename_and_relocate_are_cosmetic(db):
    lid = g.create_league("GTT", seed=9, n_teams=6)
    g.advance_all(lid, fidelity="fast")
    before = [(r["fid"], r["w"], r["l"], r["diff"]) for r in g.standings(lid)]
    fid = g.franchises(lid)[0]["id"]
    g.edit_franchise(fid, name="Totally Different", city="Elsewhere, XX", abbrev="TDX")
    after = [(r["fid"], r["w"], r["l"], r["diff"]) for r in g.standings(lid)]
    assert before == after                       # results keyed off id, not name/city
    f = next(x for x in g.franchises(lid) if x["id"] == fid)
    assert f["name"] == "Totally Different" and f["city"] == "Elsewhere, XX"


def test_results_deterministic_for_same_seed(db, tmp_path):
    lid1 = g.create_league("A", seed=42, n_teams=4)
    g.advance_all(lid1, fidelity="fast")
    s1 = [(r["w"], r["l"], r["diff"]) for r in g.standings(lid1)]
    # fresh DB, same seed -> identical franchise ids (1..4) and thus identical play
    g.DB_PATH = str(tmp_path / "gtt2.db")
    g._schema_ready_for = None
    g._roster_cache.clear()
    lid2 = g.create_league("B", seed=42, n_teams=4)
    g.advance_all(lid2, fidelity="fast")
    s2 = [(r["w"], r["l"], r["diff"]) for r in g.standings(lid2)]
    assert s1 == s2
