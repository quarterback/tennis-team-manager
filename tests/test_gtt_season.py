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


def test_p4_str_feed_rates_pros_with_prior_continuity(db):
    lid = g.create_league("GTT", seed=21, n_teams=4)
    # Preseason: no results -> empty corpus, views fall back to the profile prior.
    assert g.league_player_str(lid) == {}
    fid = g.franchises(lid)[0]["id"]
    pre = {p["pid"]: p["str"] for p in g.franchise_roster(lid, fid)}
    assert all(v > 0 for v in pre.values())

    g.advance_all(lid, fidelity="fast")
    live = g.league_player_str(lid)
    assert live, "season results must produce a rated population"
    # Reliability builds with a full season of matches.
    assert any(rel > 0.5 for (_s, rel) in live.values())
    # Rank sanity: a clearly better record rates above a clearly worse one.
    recs = g.player_records(lid)
    played = [r for r in recs.values() if r["w"] + r["l"] >= 6 and r["pid"] in live]
    best = max(played, key=lambda r: r["w"] / (r["w"] + r["l"]))
    worst = min(played, key=lambda r: r["w"] / (r["w"] + r["l"]))
    assert live[best["pid"]][0] > live[worst["pid"]][0]
    # The live value is what the views surface.
    d = g.player_detail(lid, best["pid"])
    assert d["str"] == round(live[best["pid"]][0], 1)


def test_roster_carries_a_reserve_beyond_the_lineup(db):
    lid = g.create_league("GTT", seed=4, n_teams=4)
    assert g.TARGET_MEN == g.LINEUP_MEN + g.RESERVE_MEN
    assert g.TARGET_WOMEN == g.LINEUP_WOMEN + g.RESERVE_WOMEN
    roster = g.franchise_roster(lid, g.franchises(lid)[0]["id"])
    men = [p for p in roster if p["gender"] == "m"]
    women = [p for p in roster if p["gender"] == "w"]
    assert len(men) == g.TARGET_MEN and len(women) == g.TARGET_WOMEN
    # the top LINEUP_* are starters, the rest are flagged reserves
    assert sum(p["reserve"] for p in men) == g.RESERVE_MEN
    assert sum(p["reserve"] for p in women) == g.RESERVE_WOMEN


def test_founding_free_agent_pool_seeds_the_wire(db):
    lid = g.create_league("GTT", seed=4, n_teams=4)
    fas = g.free_agents(lid)
    assert sum(p["gender"] == "m" for p in fas) == g.WAIVER_POOL_MEN
    assert sum(p["gender"] == "w" for p in fas) == g.WAIVER_POOL_WOMEN


def test_add_drop_is_gender_locked_and_keeps_rosters_whole(db):
    lid = g.create_league("GTT", seed=2026, n_teams=8)
    g.advance_all(lid, fidelity="fast")
    # every franchise still fields exactly its per-gender roster target — a drop is
    # always matched by an add of the SAME gender (no trades, gender-locked).
    for f in g.franchises(lid):
        assert _active(lid, f["id"], "m") == g.TARGET_MEN
        assert _active(lid, f["id"], "w") == g.TARGET_WOMEN
    tx = g.transactions(lid)
    assert tx, "a full season should produce some add/drop activity"
    for t in tx:
        # ability-driven: a free agent is only signed when it clears the cut player
        # by the margin (never a lateral or downgrade move).
        assert t["add_str"] >= t["drop_str"] + g.WAIVER_MARGIN


def test_add_drop_never_cuts_a_franchise_starter(db):
    lid = g.create_league("GTT", seed=2026, n_teams=8)
    g.advance_all(lid, fidelity="fast")
    live = g.league_player_str(lid)
    # No dropped player was, at the time, a top-LINEUP starter for its club: only
    # the fringe is ever at risk, so franchise players stay put.
    for t in g.transactions(lid):
        roster = g.franchise_roster(lid, t["fid"])
        # the dropped player has already left this roster, so reconstruct the
        # gender group it belonged to and confirm the cut player wasn't a starter.
        same = sorted([p for p in roster if p["gender"] == t["gender"]],
                      key=lambda x: -x["str"])
        lineup_n = g.LINEUP_MEN if t["gender"] == "m" else g.LINEUP_WOMEN
        # the signed replacement sits somewhere; the cut player's STR was below the
        # weakest retained starter (margin enforced), so it was reserve-tier.
        starters = same[:lineup_n]
        assert all(s["str"] >= t["drop_str"] for s in starters)


def test_add_drop_is_deterministic(db, tmp_path):
    lid1 = g.create_league("A", seed=77, n_teams=6)
    g.advance_all(lid1, fidelity="fast")
    tx1 = [(t["week"], t["fid"], t["gender"], t["add_pid"], t["drop_pid"])
           for t in g.transactions(lid1)]
    p2 = str(tmp_path / "gtt2.db")
    os.environ["TENNIS_DB_PATH"] = p2
    g.DB_PATH = p2
    g._schema_ready_for = None
    g._str_cache.clear()
    lid2 = g.create_league("B", seed=77, n_teams=6)
    g.advance_all(lid2, fidelity="fast")
    tx2 = [(t["week"], t["fid"], t["gender"], t["add_pid"], t["drop_pid"])
           for t in g.transactions(lid2)]
    assert tx1 == tx2


def test_gtt_intake_uses_persisted_world_graduates_with_d1_mix_and_slack(db):
    from app import world
    from app.development import generate_prospect
    import json, random

    world.WORLD_DB = g.DB_PATH
    world._schema_ready_for = None
    world.init_schema()
    conn = g._db()
    wid = conn.execute("INSERT INTO world (seed, year, week) VALUES (?,?,?)", (2026, 1, 0)).lastrowid

    def pdata(pid_seed, gender, talent):
        p = generate_prospect(random.Random(pid_seed), f"Grad {pid_seed}", "USA",
                              gender=gender, talent=talent)
        p.class_year = "Sr"
        return p.pid, json.dumps(world.prospect_to_dict(p))

    rows = []
    for i in range(24):
        gender = "men" if i % 2 == 0 else "women"
        pid, data = pdata(i, gender, 70 - i * 0.2)
        rows.append((wid, 0, "D1", gender, pid, 80.0 - i, 78.0 - i, data))
    # One genuinely pro-caliber small-school graduate and one who fails the bar.
    good_pid, good_data = pdata(100, "men", 66)
    rows.append((wid, 0, "D2", "men", good_pid, g.NON_D1_MIN_STR + 3,
                 g.NON_D1_MIN_OVR + 3, good_data))
    bad_pid, bad_data = pdata(101, "women", 40)
    rows.append((wid, 0, "D3", "women", bad_pid, g.NON_D1_MIN_STR - 1,
                 g.NON_D1_MIN_OVR + 8, bad_data))
    conn.executemany("INSERT INTO world_graduates VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

    lid = g.create_league("Pipeline", seed=2026, n_teams=4)
    league = g.load_league(lid)
    conn = g._db()
    before = conn.execute("SELECT COUNT(*) c FROM gtt_players WHERE league_id=?", (lid,)).fetchone()["c"]
    g._intake(conn, league, {"m": 11, "w": 10})
    after = conn.execute("SELECT COUNT(*) c FROM gtt_players WHERE league_id=?", (lid,)).fetchone()["c"]
    college = conn.execute("SELECT pid, fid, origin, data FROM gtt_players WHERE league_id=? "
                           "AND origin='college'", (lid,)).fetchall()
    conn.commit()
    conn.close()

    assert after - before == 25  # 21 open spots + four free-agent slack signings.
    assert any(r["pid"] == good_pid and r["fid"] is None for r in college)
    assert all(r["pid"] != bad_pid for r in college)
    assert sum(1 for r in college if r["pid"] == good_pid) == 1
    assert len(college) == 25
