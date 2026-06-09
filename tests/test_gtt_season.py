import os

import pytest

import app.gtt_seasonmode as g


@pytest.fixture
def db(tmp_path):
    p = str(tmp_path / "gtt.db")
    os.environ["TENNIS_DB_PATH"] = p     # align honors/world to the same temp DB
    g.DB_PATH = p
    g._schema_ready_for = None
    yield


def _active(lid, fid, gender):
    conn = g._db()
    n = conn.execute("SELECT COUNT(*) c FROM gtt_players WHERE league_id=? AND fid=?"
                     " AND gender=? AND status='active'", (lid, fid, gender)).fetchone()["c"]
    conn.close()
    return n


def test_schedule_is_double_round_robin(db):
    lid = g.create_league("GTT", seed=2026, n_teams=6)
    s = g.load_league(lid)
    assert s["total_weeks"] == 10 and s["phase"] == "regular" and s["current_year"] == 0
    assert len(g.franchises(lid)) == 6


def test_founding_rosters_are_stocked(db):
    lid = g.create_league("GTT", seed=4, n_teams=4)
    for f in g.franchises(lid):
        assert _active(lid, f["id"], "m") == g.TARGET_MEN
        assert _active(lid, f["id"], "w") == g.TARGET_WOMEN


def test_franchises_have_editable_identity(db):
    lid = g.create_league("GTT", seed=3, n_teams=4)
    for f in g.franchises(lid):
        assert f["name"] and f["city"] and len(f["abbrev"]) == 3


def test_full_season_completes_with_champion_and_mvp(db):
    lid = g.create_league("GTT", seed=11, n_teams=6)
    g.advance_all(lid, fidelity="fast")
    s = g.load_league(lid)
    assert s["phase"] == "complete"
    assert g.champion(lid) is not None and g.champion(lid)["name"]
    assert g.mvp(lid) is not None
    assert all(row["w"] + row["l"] == 10 for row in g.standings(lid))


def test_standings_sorted_by_wins_then_diff(db):
    lid = g.create_league("GTT", seed=5, n_teams=8)
    g.advance_all(lid, fidelity="fast")
    keys = [(r["w"], r["diff"]) for r in g.standings(lid)]
    assert keys == sorted(keys, reverse=True)


def test_rename_and_relocate_are_cosmetic(db):
    lid = g.create_league("GTT", seed=9, n_teams=6)
    g.advance_all(lid, fidelity="fast")
    before = [(r["fid"], r["w"], r["l"], r["diff"]) for r in g.standings(lid)]
    fid = g.franchises(lid)[0]["id"]
    g.edit_franchise(fid, name="Totally Different", city="Elsewhere, XX", abbrev="TDX")
    after = [(r["fid"], r["w"], r["l"], r["diff"]) for r in g.standings(lid)]
    assert before == after
    f = next(x for x in g.franchises(lid) if x["id"] == fid)
    assert f["name"] == "Totally Different" and f["city"] == "Elsewhere, XX"


def test_results_deterministic_for_same_seed(db, tmp_path):
    lid1 = g.create_league("A", seed=42, n_teams=4)
    g.advance_all(lid1, fidelity="fast")
    s1 = [(r["w"], r["l"], r["diff"]) for r in g.standings(lid1)]
    p2 = str(tmp_path / "gtt2.db")
    os.environ["TENNIS_DB_PATH"] = p2
    g.DB_PATH = p2
    g._schema_ready_for = None
    lid2 = g.create_league("B", seed=42, n_teams=4)
    g.advance_all(lid2, fidelity="fast")
    s2 = [(r["w"], r["l"], r["diff"]) for r in g.standings(lid2)]
    assert s1 == s2


def test_multiseason_offseason_ages_and_refills(db):
    lid = g.create_league("GTT", seed=7, n_teams=4)
    g.advance_all(lid, fidelity="fast")          # finish season 0
    assert g.load_league(lid)["phase"] == "complete"
    g.advance(lid, fidelity="fast")              # off-season -> season 1
    s = g.load_league(lid)
    assert s["current_year"] == 1 and s["phase"] == "regular"
    # rosters still field a legal lineup after aging/retirement + draft
    for f in g.franchises(lid):
        assert _active(lid, f["id"], "m") >= 3 and _active(lid, f["id"], "w") >= 3
    # a second full season also completes cleanly
    g.advance_all(lid, fidelity="fast")
    assert g.load_league(lid)["phase"] == "complete" and g.champion(lid) is not None


def test_honors_stamped_to_pid_and_visible_on_player_page(db):
    import app.honors as honors
    lid = g.create_league("GTT", seed=13, n_teams=4)
    g.advance_all(lid, fidelity="fast")
    m = g.mvp(lid)
    # the MVP honor is stamped to the real pid in the shared honors table
    career = honors.career(m["pid"], "player")
    assert any(h["award"] == "gtt_mvp" for h in career)
    # and the player page surfaces the career timeline
    detail = g.player_detail(lid, m["pid"])
    labels = [a["label"] for grp in detail["career_honors"] for a in grp["awards"]]
    assert any("MVP" in lbl for lbl in labels)
